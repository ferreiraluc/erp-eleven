import Foundation
import Capacitor
import Security

@objc(ElevenSecureStoragePlugin)
public class ElevenSecureStoragePlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "ElevenSecureStoragePlugin"
    public let jsName = "ElevenSecureStorage"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "get", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "set", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "remove", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "getVolatileSession", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "setVolatileSession", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "clearVolatileSession", returnType: CAPPluginReturnPromise)
    ]

    // Process memory survives a WebView reload but not app/process termination.
    private static var volatileSession: String?
    private static let volatileLock = NSLock()

    private func query(_ call: CAPPluginCall) -> [String: Any]? {
        guard let key = call.getString("key"), ["session", "notification-installation"].contains(key) else {
            call.reject("Unsupported secure storage key", "INVALID_KEY")
            return nil
        }
        return [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: (Bundle.main.bundleIdentifier ?? "com.elevenparispy.erp") + ".secure-storage.v1",
            kSecAttrAccount as String: key,
            kSecAttrSynchronizable as String: false
        ]
    }

    @objc func get(_ call: CAPPluginCall) {
        guard var attributes = query(call) else { return }
        attributes[kSecReturnData as String] = true
        attributes[kSecMatchLimit as String] = kSecMatchLimitOne
        var found: CFTypeRef?
        let status = SecItemCopyMatching(attributes as CFDictionary, &found)
        if status == errSecItemNotFound {
            call.resolve(["value": NSNull()])
        } else if status == errSecSuccess, let data = found as? Data, data.count <= 32768,
                  let value = String(data: data, encoding: .utf8) {
            call.resolve(["value": value])
        } else {
            call.reject("Secure storage is unavailable", "SECURE_STORAGE_UNAVAILABLE")
        }
    }

    @objc func set(_ call: CAPPluginCall) {
        guard let attributes = query(call) else { return }
        guard let value = call.getString("value"), let data = value.data(using: .utf8), data.count <= 32768 else {
            call.reject("Invalid secure storage value", "INVALID_VALUE")
            return
        }
        let update: [String: Any] = [
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        ]
        var status = SecItemUpdate(attributes as CFDictionary, update as CFDictionary)
        if status == errSecItemNotFound {
            var create = attributes
            update.forEach { create[$0.key] = $0.value }
            status = SecItemAdd(create as CFDictionary, nil)
        }
        if status == errSecSuccess { call.resolve() }
        else { call.reject("Secure storage is unavailable", "SECURE_STORAGE_UNAVAILABLE") }
    }

    @objc func remove(_ call: CAPPluginCall) {
        guard let attributes = query(call) else { return }
        let status = SecItemDelete(attributes as CFDictionary)
        if status == errSecSuccess || status == errSecItemNotFound { call.resolve() }
        else { call.reject("Secure storage is unavailable", "SECURE_STORAGE_UNAVAILABLE") }
    }
    @objc func getVolatileSession(_ call: CAPPluginCall) {
        Self.volatileLock.lock()
        let value = Self.volatileSession
        Self.volatileLock.unlock()
        if let value = value { call.resolve(["value": value]) }
        else { call.resolve(["value": NSNull()]) }
    }

    @objc func setVolatileSession(_ call: CAPPluginCall) {
        guard let value = call.getString("value"), value.utf8.count <= 32768 else {
            call.reject("Invalid secure storage value", "INVALID_VALUE")
            return
        }
        Self.volatileLock.lock()
        Self.volatileSession = value
        Self.volatileLock.unlock()
        call.resolve()
    }

    @objc func clearVolatileSession(_ call: CAPPluginCall) {
        Self.volatileLock.lock()
        Self.volatileSession = nil
        Self.volatileLock.unlock()
        call.resolve()
    }

}
