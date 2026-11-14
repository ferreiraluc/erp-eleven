import com.android.apksig.ApkSigner;
import com.android.apksig.ApkVerifier;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.security.PrivateKey;
import java.security.cert.X509Certificate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.List;

/** Local-only APK signer using Google's Apache-2.0 apksig library.
 * No network, credential command-line values, or private key output.
 */
public final class SignAndroidRelease {
    private static ApkVerifier.Result verify(Path apk) throws Exception {
        var result = new ApkVerifier.Builder(apk.toFile()).build().verify();
        if (!result.isVerified() || !result.isVerifiedUsingV2Scheme() || !result.isVerifiedUsingV3Scheme()) {
            throw new IllegalArgumentException("APK signature verification failed");
        }
        return result;
    }

    private static String sha256(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }

    private static void report(Path apk, ApkVerifier.Result result) throws Exception {
        var digest = MessageDigest.getInstance("SHA-256");
        try (InputStream stream = Files.newInputStream(apk)) {
            byte[] buffer = new byte[1024 * 1024];
            int length;
            while ((length = stream.read(buffer)) != -1) digest.update(buffer, 0, length);
        }
        System.out.println("APK verified: v2=" + result.isVerifiedUsingV2Scheme()
            + " v3=" + result.isVerifiedUsingV3Scheme());
        System.out.println("APK SHA-256: " + HexFormat.of().formatHex(digest.digest()));
        System.out.println("APK bytes: " + Files.size(apk));
        for (var certificate : result.getSignerCertificates()) {
            // Certificate fingerprints are public identity, never private keys.
            System.out.println("Signing certificate SHA-256: " + sha256(certificate.getEncoded()));
        }
    }

    private static void sign(Path input, Path output, Path store, Path passwordFile) throws Exception {
        if (!Files.isRegularFile(input) || Files.exists(output) || input.toAbsolutePath().equals(output.toAbsolutePath())) {
            throw new IllegalArgumentException("Input missing or output already exists");
        }
        char[] password = Files.readString(passwordFile).replaceFirst("\\r?\\n$", "").toCharArray();
        if (password.length == 0) throw new IllegalArgumentException("Empty password file");
        var keyStore = KeyStore.getInstance("PKCS12");
        List<ApkSigner.SignerConfig> signers = new ArrayList<>();
        X509Certificate expectedCertificate = null;
        try {
            try (InputStream stream = Files.newInputStream(store)) { keyStore.load(stream, password); }
            var aliases = keyStore.aliases();
            while (aliases.hasMoreElements()) {
                String alias = aliases.nextElement();
                if (!keyStore.isKeyEntry(alias)) continue;
                var key = keyStore.getKey(alias, password);
                if (!(key instanceof PrivateKey privateKey)) throw new IllegalArgumentException("Not a signing key");
                var certificates = Arrays.stream(keyStore.getCertificateChain(alias))
                    .map(certificate -> (X509Certificate) certificate).toList();
                expectedCertificate = certificates.getFirst();
                signers.add(new ApkSigner.SignerConfig.Builder("ELEVEN", privateKey, certificates).build());
            }
        } finally { Arrays.fill(password, '\0'); }
        if (signers.size() != 1) throw new IllegalArgumentException("PKCS12 must contain exactly one signing key");
        Path temporary = Files.createTempFile(output.toAbsolutePath().getParent(), "eleven-sign-", ".apk");
        try {
            new ApkSigner.Builder(signers).setInputApk(input.toFile()).setOutputApk(temporary.toFile())
                .setDebuggableApkPermitted(false).setV1SigningEnabled(false)
                .setV2SigningEnabled(true).setV3SigningEnabled(true).setV4SigningEnabled(false)
                .setAlignmentPreserved(true).setOtherSignersSignaturesPreserved(false)
                .setCreatedBy("Eleven private distribution").build().sign();
            var result = verify(temporary);
            if (result.getSignerCertificates().size() != 1 ||
                !Arrays.equals(result.getSignerCertificates().getFirst().getEncoded(), expectedCertificate.getEncoded())) {
                throw new IllegalArgumentException("Unexpected signer identity");
            }
            Files.move(temporary, output);
            report(output, result);
        } finally { Files.deleteIfExists(temporary); }
    }

    public static void main(String[] args) {
        if (args.length == 1 && args[0].equals("--help")) {
            System.out.println("sign INPUT.apk OUTPUT.apk STORE.p12 PASSWORD_FILE\nverify SIGNED.apk");
            return;
        }
        try {
            if (args.length == 2 && args[0].equals("verify")) {
                report(Path.of(args[1]), verify(Path.of(args[1])));
            } else if (args.length == 5 && args[0].equals("sign")) {
                sign(Path.of(args[1]), Path.of(args[2]), Path.of(args[3]), Path.of(args[4]));
            } else { throw new IllegalArgumentException("Use --help"); }
        } catch (Exception error) {
            // Avoid printing exception detail: keystore providers may include sensitive context.
            System.err.println("Local signing/verification failed (" + error.getClass().getSimpleName() + "). No upload was performed.");
            System.exit(1);
        }
    }
}
