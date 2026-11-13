package com.elevenparispy.erp;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.security.GeneralSecurityException;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Fixed-purpose secrets only. Ciphertext is private app data; the AES key never
 * leaves AndroidKeyStore. Backup of app data is disabled in AndroidManifest. */
@CapacitorPlugin(name = "ElevenSecureStorage")
public class ElevenSecureStoragePlugin extends Plugin {
    private static final String ALIAS = "eleven.secure-storage.v1";
    private static final String PREFS = "eleven_secure_storage";
    // Shared by WebView reloads, never written to disk and lost with the process.
    private static volatile String volatileSession = null;

    private String validKey(PluginCall call) {
        String key = call.getString("key");
        if (!"session".equals(key) && !"notification-installation".equals(key)) {
            call.reject("Unsupported secure storage key", "INVALID_KEY");
            return null;
        }
        return key;
    }

    private SharedPreferences preferences() {
        return getContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private SecretKey encryptionKey(boolean create) throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (store.containsAlias(ALIAS)) return (SecretKey) store.getKey(ALIAS, null);
        if (!create) throw new GeneralSecurityException("Secure key unavailable");
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setRandomizedEncryptionRequired(true)
            .setKeySize(256)
            .build());
        return generator.generateKey();
    }

    private byte[] context(String key) {
        return ("ElevenSecureStorage:v1:" + key).getBytes(StandardCharsets.UTF_8);
    }

    @PluginMethod
    public synchronized void get(PluginCall call) {
        String key = validKey(call);
        if (key == null) return;
        try {
            String encoded = preferences().getString(key, null);
            JSObject result = new JSObject();
            if (encoded == null) {
                result.put("value", org.json.JSONObject.NULL);
            } else {
                if (encoded.length() > 50000) throw new GeneralSecurityException("Invalid record");
                String[] parts = encoded.split(":", -1);
                if (parts.length != 3 || !"v1".equals(parts[0])) throw new GeneralSecurityException("Invalid record");
                byte[] iv = Base64.decode(parts[1], Base64.NO_WRAP);
                if (iv.length != 12) throw new GeneralSecurityException("Invalid nonce");
                Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
                cipher.init(Cipher.DECRYPT_MODE, encryptionKey(false), new GCMParameterSpec(128, iv));
                cipher.updateAAD(context(key));
                byte[] plain = cipher.doFinal(Base64.decode(parts[2], Base64.NO_WRAP));
                result.put("value", new String(plain, StandardCharsets.UTF_8));
            }
            call.resolve(result);
        } catch (Exception ignored) {
            // Never log credentials, ciphertext or provider exception payloads.
            call.reject("Secure storage is unavailable", "SECURE_STORAGE_UNAVAILABLE");
        }
    }

    @PluginMethod
    public synchronized void set(PluginCall call) {
        String key = validKey(call);
        if (key == null) return;
        String value = call.getString("value");
        if (value == null || value.getBytes(StandardCharsets.UTF_8).length > 32768) {
            call.reject("Invalid secure storage value", "INVALID_VALUE");
            return;
        }
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, encryptionKey(true));
            cipher.updateAAD(context(key));
            String encoded = "v1:" + Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP) + ":"
                + Base64.encodeToString(cipher.doFinal(value.getBytes(StandardCharsets.UTF_8)), Base64.NO_WRAP);
            if (!preferences().edit().putString(key, encoded).commit()) throw new GeneralSecurityException("Write failed");
            call.resolve();
        } catch (Exception ignored) {
            call.reject("Secure storage is unavailable", "SECURE_STORAGE_UNAVAILABLE");
        }
    }

    @PluginMethod
    public synchronized void remove(PluginCall call) {
        String key = validKey(call);
        if (key == null) return;
        try {
            if (!preferences().edit().remove(key).commit()) throw new GeneralSecurityException("Remove failed");
            call.resolve();
        } catch (Exception ignored) {
            call.reject("Secure storage is unavailable", "SECURE_STORAGE_UNAVAILABLE");
        }
    }
    @PluginMethod
    public void getVolatileSession(PluginCall call) {
        JSObject result = new JSObject();
        String value = volatileSession;
        result.put("value", value == null ? org.json.JSONObject.NULL : value);
        call.resolve(result);
    }

    @PluginMethod
    public void setVolatileSession(PluginCall call) {
        String value = call.getString("value");
        if (value == null || value.getBytes(StandardCharsets.UTF_8).length > 32768) {
            call.reject("Invalid secure storage value", "INVALID_VALUE");
            return;
        }
        volatileSession = value;
        call.resolve();
    }

    @PluginMethod
    public void clearVolatileSession(PluginCall call) {
        volatileSession = null;
        call.resolve();
    }

}
