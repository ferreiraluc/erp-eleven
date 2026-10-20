import Foundation
import Darwin

umask(0o077)
let root = FileManager.default.homeDirectoryForCurrentUser
    .appendingPathComponent("Library/Application Support/ElevenTickets")
let configURL = root.appendingPathComponent("config.json")
var stopped = false
signal(SIGTERM) { _ in stopped = true }
signal(SIGINT) { _ in stopped = true }

func log(_ line: String) {
    let url = root.appendingPathComponent("agent.log")
    let entry = ISO8601DateFormatter().string(from: Date())+" agente=\(agentVersion) "+line+"\n"
    do {
        if let attributes = try? FileManager.default.attributesOfItem(atPath: url.path),
           (attributes[.size] as? NSNumber)?.intValue ?? 0 > 65536 {
            let old = url.appendingPathExtension("1")
            if FileManager.default.fileExists(atPath: old.path) { try FileManager.default.removeItem(at: old) }
            try FileManager.default.moveItem(at: url, to: old)
        }
        if !FileManager.default.fileExists(atPath: url.path) {
            FileManager.default.createFile(atPath: url.path, contents: nil, attributes: [.posixPermissions: 0o600])
        }
        let handle = try FileHandle(forWritingTo: url)
        defer { try? handle.close() }
        try handle.seekToEnd(); try handle.write(contentsOf: Data(entry.utf8))
    } catch { } // journal writes, unlike diagnostic logs, must fail closed
}

do {
    try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
    let lock = Darwin.open(root.appendingPathComponent("agent.lock").path, O_CREAT | O_RDWR | O_NOFOLLOW, 0o600)
    guard lock >= 0, flock(lock, LOCK_EX | LOCK_NB) == 0 else {
        print("O agente já está aberto. Use Parar.command antes de configurar."); exit(1)
    }
    defer { Darwin.close(lock) }
    let mode = CommandLine.arguments.dropFirst().first ?? "--run"
    var config = Config()
    if FileManager.default.fileExists(atPath: configURL.path) {
        config = try JSONDecoder().decode(Config.self, from: Data(contentsOf: configURL))
    }
    if mode == "--configure" {
        print("Eleven Tickets macOS \(agentVersion) | 3nStar RPT006W | 80 mm")
        print("Impressora: \(config.printerIP):9100 | Ethernet do iMac: \(config.localIP)")
        print("No ERP: PDV → Tickets → Preparar 3nStar no Mac. Não use a credencial da Zebra.")
        print("Cole a credencial exclusiva do Mac. Enter mantém a credencial existente.")
        guard let raw = getpass("Credencial (oculta): ") else { throw AgentError.credential }
        let token = String(cString: raw).trimmingCharacters(in: .whitespacesAndNewlines)
        _ = try credential(token.isEmpty ? nil : token)
        try config.validate()
        try durableWrite(JSONEncoder().encode(config), to: configURL)
        print("Credencial guardada no Chaves do macOS. Configuração preserva o diário e não imprime.")
    } else if mode == "--check" {
        try config.validate()
        _ = try credential()
        let printer = try TCPPrinter(config: config)
        withExtendedLifetime(printer) { print("TCP local acessível. Nenhum byte de impressão foi enviado.") }
        print("A conferência do papel deve ser feita no teste autorizado pelo ERP.")
    } else if mode == "--version" {
        print(agentVersion)
    } else if mode == "--run" {
        try config.validate()
        guard FileManager.default.fileExists(atPath: configURL.path) else { throw AgentError.invalidConfig }
        let erp = ERP(token: try credential())
        let worker = Worker(root: root, erp: erp, openPrinter: { try TCPPrinter(config: config) },
                            render: { try escposRaster($0, job: $1, cut: config.cut) }, log: log)
        var heartbeat = Date.distantPast
        var previousError = ""
        log("iniciado perfil=tickets protocolo=escpos_tcp")
        while !stopped {
            let pause: Int = autoreleasepool {
                do {
                    if Date().timeIntervalSince(heartbeat) >= 30 {
                        let body = try JSONSerialization.data(withJSONObject: [
                            "name": "3nStar RPT006W · iMac", "profile": "tickets", "driver": "escpos_tcp"])
                        let response = try erp.call("connect", body: body).1
                        guard let data = try JSONSerialization.jsonObject(with: response) as? [String: Any],
                              data["driver"] as? String == "escpos_tcp", data["profile"] as? String == "tickets",
                              data["paper_width_mm"] as? Int == 80, data["paper_height_mm"] as? Int == 0,
                              let id = data["id"] as? String, let deviceID = UUID(uuidString: id) else {
                            throw AgentError.protocolMismatch
                        }
                        worker.deviceID = deviceID
                        heartbeat = Date()
                    }
                    try worker.tick()
                    if !previousError.isEmpty { log("fila_retomada"); previousError = "" }
                    return 3
                } catch {
                    let reason = (error as? AgentError)?.description ?? "erro_local_preserve_o_diario"
                    if reason != previousError { log("pausa=\(reason) nova_tentativa=30s"); previousError = reason }
                    return 30
                }
            }
            for _ in 0..<pause where !stopped { sleep(1) }
        }
        log("encerrado")
    } else { throw AgentError.invalidConfig }
} catch {
    let message = (error as? AgentError)?.description ?? "erro_local_preserve_o_diario"
    log("falha=\(message)")
    print("Eleven Tickets: \(message). Consulte Diagnostico.command; não apague o diário.")
    exit(1)
}
