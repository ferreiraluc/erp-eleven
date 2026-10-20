import Foundation
import CoreGraphics
import CryptoKit
import Security
import Darwin

let agentVersion = "2026.10.20.1"
let serverURL = "https://erp-eleven-backend.onrender.com/api/printing/agent/"
let keychainService = "com.eleven.tickets.escpos"

enum AgentError: Error, CustomStringConvertible {
    case invalidConfig, journal, pdf, offline, http(Int), protocolMismatch, credential
    var description: String {
        switch self {
        case .invalidConfig: return "configuracao_invalida"
        case .journal: return "diario_invalido_preserve_os_arquivos"
        case .pdf: return "pdf_invalido"
        case .offline: return "impressora_indisponivel_aguardando_reconexao"
        case .http(let code): return "erp_http_\(code)"
        case .protocolMismatch: return "perfil_ou_trabalho_incompativel"
        case .credential: return "credencial_indisponivel_no_chaves"
        }
    }
}

struct Config: Codable {
    var printerIP = "192.168.123.100"
    var localIP = "192.168.123.10"
    var port: UInt16 = 9100
    var cut = true
    func validate() throws {
        func privateIP(_ value: String) -> Bool {
            let p = value.split(separator: ".", omittingEmptySubsequences: false)
            guard p.count == 4, p.allSatisfy({ Int($0).map { (0...255).contains($0) } == true }),
                  p.map({String(Int($0)!)}).joined(separator: ".") == value else { return false }
            let n = p.map { Int($0)! }
            return n[0] == 10 || (n[0] == 172 && (16...31).contains(n[1])) || (n[0] == 192 && n[1] == 168)
        }
        guard privateIP(printerIP), privateIP(localIP), printerIP != localIP, port == 9100 else {
            throw AgentError.invalidConfig
        }
    }
}

struct Job: Codable {
    let id: UUID
    let sha256: String
    let profile: String
    let paper_mode: String
    let paper_width_mm: Int
    let paper_height_mm: Int
    func validate() throws {
        guard profile == "tickets", paper_mode == "continuous", paper_width_mm == 80,
              (50...991).contains(paper_height_mm), sha256.count == 64,
              sha256.allSatisfy({ $0.isHexDigit }) else { throw AgentError.protocolMismatch }
    }
}

struct Journal: Codable {
    var claimKey: UUID
    var job: Job?
    var phase = "claiming"
    var diagnostic: String?
    var deviceID: UUID?
    // Dispatch is never repeated after this boundary, including after a crash.
    mutating func recover() throws {
        guard ["claiming", "preparing", "sending", "submitted", "uncertain", "failed"].contains(phase),
              (phase == "claiming") == (job == nil) else { throw AgentError.journal }
        try job?.validate()
        if phase == "sending" { phase = "uncertain"; diagnostic = "network_interrupted" }
    }
}

func durableWrite(_ data: Data, to url: URL) throws {
    let temporary = url.appendingPathExtension("tmp")
    let fd = Darwin.open(temporary.path, O_WRONLY | O_CREAT | O_TRUNC | O_NOFOLLOW, 0o600)
    guard fd >= 0 else { throw AgentError.journal }
    defer { Darwin.close(fd) }
    try data.withUnsafeBytes { bytes in
        var offset = 0
        while offset < data.count {
            let written = Darwin.write(fd, bytes.baseAddress!.advanced(by: offset), data.count-offset)
            if written < 0 && errno == EINTR { continue }
            guard written > 0 else { throw AgentError.journal }
            offset += written
        }
    }
    guard fsync(fd) == 0, fcntl(fd, F_FULLFSYNC) == 0,
          rename(temporary.path, url.path) == 0 else { throw AgentError.journal }
    let dir = Darwin.open(url.deletingLastPathComponent().path, O_RDONLY)
    guard dir >= 0 else { throw AgentError.journal }
    defer { Darwin.close(dir) }
    _ = fsync(dir)
}

func credential(_ replacement: String? = nil) throws -> String {
    let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                               kSecAttrService as String: keychainService, kSecAttrAccount as String: "device"]
    if let replacement = replacement {
        guard (32...256).contains(replacement.utf8.count),
              replacement.allSatisfy({ $0.isASCII && ($0.isLetter || $0.isNumber || $0 == "-" || $0 == "_") }) else {
            throw AgentError.credential
        }
        let data = Data(replacement.utf8)
        let result = SecItemUpdate(query as CFDictionary, [kSecValueData as String: data] as CFDictionary)
        if result == errSecItemNotFound {
            var create = query
            create[kSecValueData as String] = data
            create[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
            guard SecItemAdd(create as CFDictionary, nil) == errSecSuccess else { throw AgentError.credential }
        } else if result != errSecSuccess { throw AgentError.credential }
        return replacement
    }
    var read = query
    read[kSecReturnData as String] = true
    read[kSecMatchLimit as String] = kSecMatchLimitOne
    var result: CFTypeRef?
    guard SecItemCopyMatching(read as CFDictionary, &result) == errSecSuccess,
          let data = result as? Data, let value = String(data: data, encoding: .utf8), value.count >= 32 else {
        throw AgentError.credential
    }
    return value
}

// Redirects must never carry the device credential to another server.
final class NoRedirect: NSObject, URLSessionTaskDelegate {
    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest,
                    completionHandler: @escaping (URLRequest?) -> Void) { completionHandler(nil) }
}

protocol ERPConnection {
    func call(_ path: String, method: String, body: Data?) throws -> (Int, Data)
}

final class ERP: ERPConnection {
    let token: String
    let session: URLSession
    init(token: String) {
        self.token = token
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 20
        config.timeoutIntervalForResource = 30
        config.httpMaximumConnectionsPerHost = 1
        session = URLSession(configuration: config, delegate: NoRedirect(), delegateQueue: nil)
    }
    func call(_ path: String, method: String = "POST", body: Data? = nil) throws -> (Int, Data) {
        guard let url = URL(string: serverURL+path), url.host == "erp-eleven-backend.onrender.com",
              url.scheme == "https" else { throw AgentError.invalidConfig }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("Bearer "+token, forHTTPHeaderField: "Authorization")
        if let body = body {
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        let done = DispatchSemaphore(value: 0)
        var answer: (Int, Data)?
        let task = session.dataTask(with: request) { data, response, error in
            if error == nil, let response = response as? HTTPURLResponse {
                answer = (response.statusCode, data ?? Data())
            }
            done.signal()
        }
        task.resume()
        guard done.wait(timeout: .now()+35) == .success else { task.cancel(); throw AgentError.http(0) }
        guard let answer = answer, (200...299).contains(answer.0) else { throw AgentError.http(answer?.0 ?? 0) }
        guard answer.1.count <= 5*1024*1024 else { throw AgentError.pdf }
        return answer
    }
}

protocol PrinterConnection: AnyObject {
    func send(_ data: Data) throws
}

final class TCPPrinter: PrinterConnection {
    private var fd: Int32 = -1
    init(config: Config) throws {
        try config.validate()
        fd = socket(AF_INET, SOCK_STREAM, 0)
        guard fd >= 0 else { throw AgentError.offline }
        do {
            var one: Int32 = 1
            guard setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &one, socklen_t(MemoryLayout.size(ofValue: one))) == 0 else { throw AgentError.offline }
            var local = sockaddr_in()
            local.sin_len = UInt8(MemoryLayout<sockaddr_in>.size); local.sin_family = sa_family_t(AF_INET)
            guard inet_pton(AF_INET, config.localIP, &local.sin_addr) == 1 else { throw AgentError.invalidConfig }
            let bound = withUnsafePointer(to: &local) { $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.bind(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
            }}
            guard bound == 0 else { throw AgentError.offline }
            var address = sockaddr_in()
            address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size); address.sin_family = sa_family_t(AF_INET)
            address.sin_port = config.port.bigEndian
            guard inet_pton(AF_INET, config.printerIP, &address.sin_addr) == 1 else { throw AgentError.invalidConfig }
            guard fcntl(fd, F_SETFL, O_NONBLOCK) == 0 else { throw AgentError.offline }
            let connected = withUnsafePointer(to: &address) { $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.connect(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
            }}
            if connected != 0 {
                guard errno == EINPROGRESS else { throw AgentError.offline }
                var wait = pollfd(fd: fd, events: Int16(POLLOUT), revents: 0)
                guard poll(&wait, 1, 5000) > 0 else { throw AgentError.offline }
                var error: Int32 = 0; var length = socklen_t(MemoryLayout.size(ofValue: error))
                guard getsockopt(fd, SOL_SOCKET, SO_ERROR, &error, &length) == 0, error == 0 else { throw AgentError.offline }
            }
            guard fcntl(fd, F_SETFL, 0) == 0 else { throw AgentError.offline }
            var timeout = timeval(tv_sec: 10, tv_usec: 0)
            guard setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, socklen_t(MemoryLayout.size(ofValue: timeout))) == 0 else { throw AgentError.offline }
        } catch {
            Darwin.close(fd)
            fd = -1
            throw error
        }
    }
    deinit { if fd >= 0 { Darwin.close(fd) } }
    func send(_ data: Data) throws {
        // Conservative: any failure after dispatch begins is uncertain, even if
        // send() reports zero bytes. Never retry a partially transmitted receipt.
        try data.withUnsafeBytes { bytes in
            var offset = 0
            let deadline = Date().addingTimeInterval(120)
            while offset < data.count {
                guard Date() < deadline else { throw AgentError.offline }
                let count = Darwin.send(fd, bytes.baseAddress!.advanced(by: offset), min(4096, data.count-offset), 0)
                if count < 0 && errno == EINTR { continue }
                guard count > 0 else { throw AgentError.offline }
                offset += count
            }
        }
    }
}

func escposRaster(_ pdf: Data, job: Job, cut: Bool) throws -> Data {
    try job.validate()
    guard pdf.count <= 5*1024*1024, pdf.starts(with: Data("%PDF-".utf8)),
          SHA256.hash(data: pdf).map({String(format:"%02x", $0)}).joined() == job.sha256,
          let provider = CGDataProvider(data: pdf as CFData), let document = CGPDFDocument(provider),
          !document.isEncrypted, document.numberOfPages == 1, let page = document.page(at: 1) else { throw AgentError.pdf }
    let box = page.getBoxRect(.mediaBox)
    guard abs(box.width*25.4/72-80) < 1, abs(box.height*25.4/72-Double(job.paper_height_mm)) <= 1,
          page.rotationAngle == 0 else { throw AgentError.pdf }
    // 576 printable dots (72 mm) on an 80 mm roll. Fit the entire PDF so neither
    // margins, accents nor barcode are clipped. No font/code-page dependencies.
    let width = 576, height = Int(ceil(box.height/box.width*576))
    guard height > 0, height <= 8000 else { throw AgentError.pdf }
    var pixels = [UInt8](repeating: 255, count: width*height)
    try pixels.withUnsafeMutableBytes { buffer in
        guard let context = CGContext(data: buffer.baseAddress, width: width, height: height,
              bitsPerComponent: 8, bytesPerRow: width, space: CGColorSpaceCreateDeviceGray(),
              bitmapInfo: CGImageAlphaInfo.none.rawValue) else { throw AgentError.pdf }
        context.setFillColor(gray: 1, alpha: 1); context.fill(CGRect(x: 0, y: 0, width: width, height: height))
        context.scaleBy(x: CGFloat(width)/box.width, y: CGFloat(height)/box.height)
        context.translateBy(x: -box.minX, y: -box.minY)
        context.drawPDFPage(page)
    }
    var output = Data([0x1b, 0x40, 0x1b, 0x61, 0x01]) // initialize, center
    let bytesPerRow = width/8
    for top in stride(from: 0, to: height, by: 128) {
        let rows = min(128, height-top)
        output.append(contentsOf: [0x1d, 0x76, 0x30, 0, UInt8(bytesPerRow), 0, UInt8(rows & 255), UInt8(rows >> 8)])
        for y in top..<(top+rows) {
            for x in stride(from: 0, to: width, by: 8) {
                var byte: UInt8 = 0
                for bit in 0..<8 where pixels[y*width+x+bit] < 180 { byte |= UInt8(0x80 >> bit) }
                output.append(byte)
            }
        }
    }
    output.append(contentsOf: [0x1b, 0x64, 0x04]) // feed clear of cutter
    if cut { output.append(contentsOf: [0x1d, 0x56, 0x42, 0]) } // partial cut, once
    return output
}

final class Worker {
    let root: URL
    let erp: ERPConnection
    let openPrinter: () throws -> PrinterConnection
    let render: (Data, Job) throws -> Data
    let log: (String) -> Void
    var deviceID: UUID?
    var journalURL: URL { root.appendingPathComponent("journal.json") }
    init(root: URL, erp: ERPConnection, openPrinter: @escaping () throws -> PrinterConnection,
         render: @escaping (Data, Job) throws -> Data, log: @escaping (String)->Void) {
        self.root=root; self.erp=erp; self.openPrinter=openPrinter; self.render=render; self.log=log
    }
    func save(_ journal: Journal) throws { try durableWrite(JSONEncoder().encode(journal), to: journalURL) }
    func tick() throws {
        var state: Journal?
        if FileManager.default.fileExists(atPath: journalURL.path) {
            do {
                state = try JSONDecoder().decode(Journal.self, from: Data(contentsOf: journalURL))
                let interrupted = state!.phase == "sending"
                try state!.recover()
                if interrupted { try save(state!) }
            } catch { throw AgentError.journal } // never overwrite a corrupt dispatch journal
        }
        if let state = state, ["submitted", "uncertain", "failed"].contains(state.phase) {
            try acknowledge(state)
            return
        }
        // Offline at this point is safe to retry: no print bytes have been sent.
        let printer = try openPrinter()
        if state == nil {
            state = Journal(claimKey: UUID(), deviceID: deviceID)
            try save(state!)
        }
        if let expected = state!.deviceID, let current = deviceID, expected != current { throw AgentError.protocolMismatch }
        if state!.phase == "claiming" {
            let path = "claim?continuous_tickets=true&driver=escpos_tcp&claim_key="+state!.claimKey.uuidString
            let (status, body) = try erp.call(path, method: "POST", body: nil)
            if status == 204 {
                // Unused key stays durable while idle: no disk writes every 3s.
                return
            }
            let job = try JSONDecoder().decode(Job.self, from: body)
            try job.validate()
            state!.job = job; state!.phase = "preparing"
            try save(state!)
        }
        guard let job = state!.job else { throw AgentError.journal }
        let pdfURL = root.appendingPathComponent(job.id.uuidString+".pdf")
        let pdf: Data
        if FileManager.default.fileExists(atPath: pdfURL.path) { pdf = try Data(contentsOf: pdfURL) }
        else {
            pdf = try erp.call("jobs/\(job.id.uuidString)/pdf", method: "GET", body: nil).1
            try durableWrite(pdf, to: pdfURL)
        }
        let bytes: Data
        do { bytes = try render(pdf, job) }
        catch {
            state!.phase = "failed"; state!.diagnostic = "invalid_pdf"; try save(state!)
            try acknowledge(state!); return
        }
        state!.phase = "sending"
        try save(state!) // fsync BEFORE the first byte; failures must not dispatch
        do {
            try printer.send(bytes)
            state!.phase = "submitted"; state!.diagnostic = "network_accepted"
        } catch {
            state!.phase = "uncertain"; state!.diagnostic = "network_interrupted"
        }
        try save(state!)
        try acknowledge(state!)
    }
    func acknowledge(_ state: Journal) throws {
        guard let job = state.job else { throw AgentError.journal }
        let body = try JSONSerialization.data(withJSONObject: [
            "status": state.phase, "diagnostic": ["code": state.diagnostic ?? "network_interrupted",
                "agent_version": agentVersion, "duration_ms": 0] as [String: Any]
        ])
        _ = try erp.call("jobs/\(job.id.uuidString)/result", method: "POST", body: body)
        log("trabalho=\(job.id.uuidString) estado=\(state.phase)")
        let pdfURL = root.appendingPathComponent(job.id.uuidString+".pdf")
        if FileManager.default.fileExists(atPath: pdfURL.path) { try FileManager.default.removeItem(at: pdfURL) }
        // If deletion is interrupted, the next result POST is idempotent; the
        // saved terminal state cannot dispatch again.
        try FileManager.default.removeItem(at: journalURL)
    }
}
