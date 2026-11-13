import Capacitor

final class ElevenBridgeViewController: CAPBridgeViewController {
    override func capacitorDidLoad() {
        bridge?.registerPluginInstance(ElevenSecureStoragePlugin())
    }
}
