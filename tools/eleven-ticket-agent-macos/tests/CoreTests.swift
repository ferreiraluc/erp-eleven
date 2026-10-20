import Foundation
import CoreGraphics
import CryptoKit

func check(_ condition: @autoclosure () -> Bool, _ message: String) {
    if !condition() { fatalError(message) }
}
func rejects(_ operation: () throws -> Void) {
    do { try operation(); fatalError("Expected failure") } catch { }
}

final class FakeERP: ERPConnection {
    var calls: [String] = []
    var claimKeys: [String] = []
    var acknowledgements: [String] = []
    var failClaim = false
    var failResult = false
    var pdf = Data("%PDF-synthetic".utf8)
    var job = Job(id: UUID(), sha256: String(repeating: "a", count: 64), profile: "tickets",
                  paper_mode: "continuous", paper_width_mm: 80, paper_height_mm: 100)
    func call(_ path: String, method: String, body: Data?) throws -> (Int, Data) {
        calls.append(path)
        if path.hasPrefix("claim?") {
            claimKeys.append(path)
            if failClaim { failClaim=false; throw AgentError.http(0) }
            return (200, try JSONEncoder().encode(job))
        }
        if path.hasSuffix("/pdf") { return (200, pdf) }
        if path.hasSuffix("/result") {
            let value = try JSONSerialization.jsonObject(with: body!) as! [String: Any]
            acknowledgements.append(value["status"] as! String)
            if failResult { failResult=false; throw AgentError.http(0) }
            return (200, Data())
        }
        fatalError("Unexpected ERP path")
    }
}
final class FakePrinter: PrinterConnection {
    var sends = 0
    var fail = false
    func send(_ data: Data) throws {
        sends += 1
        if fail { throw AgentError.offline }
    }
}

@main struct Tests {
    static func main() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent("eleven-mac-tests-"+UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        for scenario in ["normal", "offline", "claim_lost", "result_lost", "partial_send", "restart", "corrupt", "wrong_device", "invalid_pdf", "journal_write_failed"] {
            let folder = root.appendingPathComponent(scenario)
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
            let erp = FakeERP(), printer = FakePrinter()
            var offline = scenario == "offline"
            var opens = 0
            let worker = Worker(root: folder, erp: erp, openPrinter: {
                opens += 1
                if offline { throw AgentError.offline }
                return printer
            }, render: { _, _ in
                if scenario == "invalid_pdf" { throw AgentError.pdf }
                return Data([1,2,3])
            }, log: {_ in})
            worker.deviceID = UUID()
            switch scenario {
            case "offline":
                rejects { try worker.tick() }
                check(erp.calls.isEmpty && printer.sends == 0, "Offline must not claim/drop a ticket")
                offline = false; try worker.tick()
                check(printer.sends == 1, "Reconnect must resume")
            case "claim_lost":
                erp.failClaim = true
                rejects { try worker.tick() }; try worker.tick()
                check(erp.claimKeys.count == 2 && erp.claimKeys[0] == erp.claimKeys[1], "Claim identity lost")
                check(printer.sends == 1, "Claim response retry printed twice")
            case "result_lost":
                erp.failResult = true
                rejects { try worker.tick() }; try worker.tick()
                check(printer.sends == 1 && opens == 1, "Result retry must not reconnect/print again")
                check(erp.acknowledgements == ["submitted","submitted"], "Result must be idempotent")
            case "partial_send":
                printer.fail = true; erp.failResult = true
                rejects { try worker.tick() }; try worker.tick()
                check(printer.sends == 1 && erp.acknowledgements == ["uncertain","uncertain"], "Partial write repeated")
            case "restart":
                var state = Journal(claimKey: UUID(), job: erp.job)
                state.phase = "sending"; try worker.save(state); try worker.tick()
                check(opens == 0 && printer.sends == 0 && erp.acknowledgements == ["uncertain"], "Restart must never dispatch again")
            case "corrupt":
                try durableWrite(Data("broken".utf8), to: worker.journalURL)
                rejects { try worker.tick() }
                check(erp.calls.isEmpty && opens == 0, "Corrupt journal must fail closed")
                check(try! Data(contentsOf: worker.journalURL) == Data("broken".utf8), "Corrupt journal overwritten")
            case "wrong_device":
                try worker.save(Journal(claimKey: UUID(), deviceID: UUID()))
                rejects { try worker.tick() }
                check(erp.calls.isEmpty && printer.sends == 0, "Foreign journal accepted")
            case "invalid_pdf":
                try worker.tick()
                check(printer.sends == 0 && erp.acknowledgements == ["failed"], "Invalid PDF printed")
            case "journal_write_failed":
                try FileManager.default.createDirectory(at: worker.journalURL.appendingPathExtension("tmp"), withIntermediateDirectories: true)
                rejects { try worker.tick() }
                check(printer.sends == 0 && erp.calls.isEmpty, "Dispatched without durable journal")
            default:
                try worker.tick()
                check(printer.sends == 1 && erp.acknowledgements == ["submitted"], "Normal dispatch")
                check(!FileManager.default.fileExists(atPath: worker.journalURL.path), "Acked journal not released")
                check(!FileManager.default.fileExists(atPath: folder.appendingPathComponent(erp.job.id.uuidString+".pdf").path), "Temporary PDF retained")
            }
            print("PASS \(scenario)")
        }
        for host in ["8.8.8.8", "127.0.0.1", "printer.example", "192.168.123.999", "192.168.123.010", "http://192.168.1.1", "::1"] {
            var config = Config(); config.printerIP=host
            rejects { try config.validate() }
        }
        var config = Config(); config.port=443
        rejects { try config.validate() }
        try Config().validate()
        print("PASS private-network-only configuration")

        // Asymmetric PDF tests byte order/orientation rather than reproducing the
        // renderer implementation. A black bar near the top must print first.
        let buffer = NSMutableData()
        var box = CGRect(x: 0, y: 0, width: 80*72/25.4, height: 100*72/25.4)
        let context = CGContext(consumer: CGDataConsumer(data: buffer)!, mediaBox: &box, nil)!
        context.beginPDFPage(nil)
        context.setFillColor(gray: 0, alpha: 1)
        context.fill(CGRect(x: 8, y: box.height-30, width: box.width-16, height: 10))
        context.endPDFPage(); context.closePDF()
        let pdf = buffer as Data
        let job = Job(id: UUID(), sha256: SHA256.hash(data: pdf).map({String(format:"%02x",$0)}).joined(),
                      profile: "tickets", paper_mode: "continuous", paper_width_mm: 80, paper_height_mm: 100)
        let raster = try escposRaster(pdf, job: job, cut: true)
        let rows = try unpack(raster)
        let blackRows = rows.enumerated().filter { $0.element.contains(where: {$0 != 0}) }.map(\.offset)
        check(!blackRows.isEmpty && blackRows.max()! < rows.count/3, "PDF upside down or missing")
        check(raster.suffix(4) == Data([0x1d,0x56,0x42,0]), "One final cut required")
        check(try! escposRaster(pdf, job: job, cut: false).suffix(3) == Data([0x1b,0x64,0x04]), "Optional cutter")
        rejects { _ = try escposRaster(Data("%PDF-wrong".utf8), job: job, cut: true) }
        print("PASS raster bands, orientation, integrity and final cut")
        if CommandLine.arguments.count == 4 {
            let fixture = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))
            let height = Int(CommandLine.arguments[2])!
            let fixtureJob = Job(id:UUID(), sha256:SHA256.hash(data:fixture).map({String(format:"%02x",$0)}).joined(),
                                 profile:"tickets", paper_mode:"continuous", paper_width_mm:80,paper_height_mm:height)
            let result = try escposRaster(fixture, job: fixtureJob, cut:true)
            let lines = try unpack(result)
            var image = Data("P5\n576 \(lines.count)\n255\n".utf8)
            for line in lines { for byte in line { for bit in 0..<8 { image.append(byte & UInt8(0x80 >> bit) == 0 ? 255 : 0) } } }
            try image.write(to: URL(fileURLWithPath: CommandLine.arguments[3]))
            print("PASS ERP PDF raster fixture: \(result.count) ESC/POS bytes, \(lines.count) rows")
        }
        print("All tests use synthetic data and fake transports. No Keychain, production API, printer or launchd operations.")
    }
    static func unpack(_ data: Data) throws -> [[UInt8]] {
        let bytes = [UInt8](data)
        check(Array(bytes.prefix(5)) == [0x1b,0x40,0x1b,0x61,0x01], "Raster header")
        var offset = 5, rows: [[UInt8]] = []
        while offset+8 < bytes.count && Array(bytes[offset..<offset+4]) == [0x1d,0x76,0x30,0] {
            let width = Int(bytes[offset+4])+256*Int(bytes[offset+5])
            let height = Int(bytes[offset+6])+256*Int(bytes[offset+7])
            check(width == 72 && height <= 128, "Invalid band bounds")
            offset += 8
            check(offset+width*height <= bytes.count, "Truncated image")
            for _ in 0..<height {
                rows.append(Array(bytes[offset..<offset+width])); offset += width
            }
        }
        check(Array(bytes[offset..<offset+3]) == [0x1b,0x64,0x04], "Missing final feed")
        check(bytes.count-offset == 7, "Unexpected commands or duplicate cut")
        return rows
    }
}
