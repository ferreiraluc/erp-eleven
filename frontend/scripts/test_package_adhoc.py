"""Offline checks for rejecting unsafe/uninstallable Ad Hoc exports.

Synthetic profiles exercise validation only; they are never emitted as IPA files
or accepted as signed release artifacts. Real signing is checked by macOS tools.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import stat
import json
import plistlib
import subprocess
from unittest.mock import patch
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location("package_adhoc", Path(__file__).with_name("package-adhoc.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AdHocValidationTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 13, tzinfo=timezone.utc)
        self.info = {"CFBundleIdentifier": "com.elevenparispy.erp", "CFBundleSupportedPlatforms": ["iPhoneOS"],
                     "CFBundleShortVersionString": "1.0.1", "CFBundleVersion": "2"}
        self.entitlements = {"get-task-allow": False, "application-identifier": "TEAM123.com.elevenparispy.erp",
                             "com.apple.developer.team-identifier": "TEAM123"}
        self.profile = {"ExpirationDate": self.now + timedelta(days=30), "ProvisionedDevices": ["private-test-device"],
                        "ApplicationIdentifierPrefix": ["TEAM123"], "TeamIdentifier": ["TEAM123"],
                        "Entitlements": deepcopy(self.entitlements), "Name": "private profile name"}

    def validate(self):
        return module.validate_profile(self.info, self.profile, self.entitlements,
                                       expected_bundle_id="com.elevenparispy.erp", now=self.now)

    def test_public_metadata_uses_signed_app_identity_and_omits_devices(self):
        result = self.validate()
        self.assertEqual(result, {"status": "ready", "version": "1.0.1", "build": "2",
                                  "bundleId": "com.elevenparispy.erp", "expiresAt": "2026-12-13T00:00:00Z"})
        self.assertNotIn("private", str(result))

    def test_rejects_expired_enterprise_store_and_debug_profiles(self):
        for change in ({"ExpirationDate": self.now}, {"ProvisionsAllDevices": True},
                       {"ProvisionedDevices": []}, {"ProvisionedDevices": None}):
            with self.subTest(change=change):
                original = deepcopy(self.profile)
                self.profile.update(change)
                with self.assertRaises(module.InvalidPackage):
                    self.validate()
                self.profile = original
        self.profile["Entitlements"]["get-task-allow"] = True
        with self.assertRaises(module.InvalidPackage):
            self.validate()

    def test_rejects_resigned_development_and_identity_mismatch(self):
        for field, value in (("get-task-allow", True), ("application-identifier", "TEAM123.some.other.app"),
                             ("com.apple.developer.team-identifier", "OTHERTEAM")):
            with self.subTest(field=field):
                original = deepcopy(self.entitlements)
                self.entitlements[field] = value
                with self.assertRaises(module.InvalidPackage):
                    self.validate()
                self.entitlements = original
        self.profile["Entitlements"]["application-identifier"] = "TEAM123.*"
        with self.assertRaises(module.InvalidPackage):
            self.validate()

    def test_rejects_simulator_wrong_bundle_and_invalid_versions(self):
        for field, value in (("CFBundleSupportedPlatforms", ["iPhoneSimulator"]),
                             ("CFBundleIdentifier", "com.elevenparispy.erp.pilot"),
                             ("CFBundleVersion", "../../invalid")):
            with self.subTest(field=field):
                original = deepcopy(self.info)
                self.info[field] = value
                with self.assertRaises(module.InvalidPackage):
                    self.validate()
                self.info = original

    def test_handles_naive_apple_plist_expiry_as_utc(self):
        self.profile["ExpirationDate"] = datetime(2026, 12, 1)
        self.assertEqual(self.validate()["expiresAt"], "2026-12-01T00:00:00Z")

    def test_only_stable_https_urls_without_secrets(self):
        self.assertEqual(module.https_url("https://elevenparispy.com/download/ios/Eleven.ipa", ".ipa"),
                         "https://elevenparispy.com/download/ios/Eleven.ipa")
        for bad in ("http://example.com/a.ipa", "https://user:secret@example.com/a.ipa",
                    "https://example.com/a.ipa?token=secret", "https://example.com/a.ipa#secret",
                    "https://example.com/a.html", "https://example.com/a.ipa\n"):
            with self.subTest(url=bad), self.assertRaises(module.InvalidPackage):
                module.https_url(bad, ".ipa")

    def test_archive_traversal_and_symlink_are_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for path in ("../outside", "/absolute", "Payload/../escape", "Payload\\escape"):
                with self.subTest(path=path):
                    with zipfile.ZipFile(root / "test.ipa", "w") as archive:
                        archive.writestr(path, b"bad")
                    with self.assertRaises(module.InvalidPackage):
                        module.unpack(root / "test.ipa", root / "unpacked")
            symlink = zipfile.ZipInfo("Payload/App.app/link")
            symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(root / "test.ipa", "w") as archive:
                archive.writestr(symlink, b"/etc/passwd")
            with self.assertRaises(module.InvalidPackage):
                module.unpack(root / "test.ipa", root / "unpacked")
            self.assertFalse((root / "unpacked").exists())

    def test_verified_export_writes_matching_manifest_without_private_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = deepcopy(self.profile)
            profile["ExpirationDate"] = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30)
            profile["DeveloperCertificates"] = [b"synthetic-signer-certificate"]
            with zipfile.ZipFile(root / "test.ipa", "w") as archive:
                archive.writestr("Payload/App.app/Info.plist", plistlib.dumps(self.info))
                archive.writestr("Payload/App.app/embedded.mobileprovision", b"synthetic-profile-for-unit-test")

            def simulate_apple_tools(args):
                if args[0].endswith("security"):
                    return plistlib.dumps(profile)
                if "--entitlements" in args:
                    return plistlib.dumps(self.entitlements)
                if "--extract-certificates" in args:
                    Path(f"{args[-2]}0").write_bytes(b"synthetic-signer-certificate")
                return b""

            with patch.object(module.sys, "platform", "darwin"), patch.object(module, "verified_profile", return_value=profile), patch.object(module, "apple_tool", side_effect=simulate_apple_tools):
                metadata = module.package(root / "test.ipa", "https://example.com/Eleven.ipa",
                                          "https://example.com/manifest.plist", root / "public")
            manifest = plistlib.loads((root / "public/manifest.plist").read_bytes())
            self.assertEqual(manifest["items"][0]["metadata"]["bundle-version"], "2")
            self.assertEqual(manifest["items"][0]["metadata"]["bundle-identifier"], metadata["bundleId"])
            self.assertEqual(manifest["items"][0]["assets"][0]["url"], metadata["url"])
            public_json = (root / "public/ios-release.json").read_text()
            self.assertEqual(json.loads(public_json), metadata)
            self.assertNotIn("private-test-device", public_json)
            self.assertNotIn("DeveloperCertificates", public_json)
            self.assertEqual(set(p.name for p in (root / "public").iterdir()), {"manifest.plist", "ios-release.json"})

    @unittest.skipUnless(Path("/usr/bin/openssl").is_file(), "OpenSSL required for CMS regression")
    def test_cms_without_signers_or_self_signed_cms_cannot_publish(self):
        def der(tag, content):
            length = len(content)
            encoded = bytes([length]) if length < 128 else bytes([0x80 | ((length.bit_length() + 7) // 8)]) + length.to_bytes((length.bit_length() + 7) // 8, "big")
            return bytes([tag]) + encoded + content

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            # Two deliberately unrelated test CAs: trusting the first must never
            # allow the second to impersonate Apple's profile-signing identity.
            for name, subject in (("trusted", "/CN=Offline unit test CA"),
                                  ("forged", "/O=Apple Inc./CN=Apple iPhone OS Provisioning Profile Signing")):
                subprocess.run(["/usr/bin/openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                                "-keyout", str(root / f"{name}.key"), "-out", str(root / f"{name}.pem"),
                                "-days", "1", "-subj", subject], check=True, capture_output=True)
            payload = plistlib.dumps(self.profile)
            (root / "payload.plist").write_bytes(payload)
            oid_data = bytes.fromhex("06092a864886f70d010701")
            oid_signed = bytes.fromhex("06092a864886f70d010702")
            # A SignedData container with a plist and EMPTY signerInfos. Apple's
            # cms -D accepts this as decoded content, not as an authenticated profile.
            unsigned_cms = der(0x30, oid_signed + der(0xa0, der(0x30,
                bytes.fromhex("0201013100") + der(0x30, oid_data + der(0xa0, der(4, payload))) + der(0x31, b""))))
            (root / "unsigned.cms").write_bytes(unsigned_cms)
            subprocess.run(["/usr/bin/openssl", "cms", "-sign", "-binary", "-nodetach", "-outform", "DER",
                            "-in", str(root / "payload.plist"), "-signer", str(root / "forged.pem"),
                            "-inkey", str(root / "forged.key"), "-out", str(root / "forged.cms")],
                           check=True, capture_output=True)
            # Positive control for the real verifier: a test-only trust override
            # proves the CMS command can validate this signed payload. Production
            # never accepts a caller-provided root or a root inside the profile.
            (root / "valid-check").mkdir()
            with patch.object(module, "apple_profile_roots", return_value=(root / "forged.pem").read_bytes()):
                self.assertEqual(module.verified_profile(root / "forged.cms", root / "valid-check"), plistlib.loads(payload))
                tampered = (root / "forged.cms").read_bytes().replace(b"private profile name", b"altered profile name")
                (root / "tampered.cms").write_bytes(tampered)
                (root / "tampered-check").mkdir()
                with self.assertRaises(module.InvalidPackage):
                    module.verified_profile(root / "tampered.cms", root / "tampered-check")
            real_tool = module.apple_tool
            def only_mock_app_signature(args):
                return b"" if args[0] == "/usr/bin/codesign" else real_tool(args)

            for profile_name in ("unsigned", "forged"):
                with self.subTest(profile=profile_name):
                    with zipfile.ZipFile(root / "test.ipa", "w") as archive:
                        archive.writestr("Payload/App.app/Info.plist", plistlib.dumps(self.info))
                        archive.writestr("Payload/App.app/embedded.mobileprovision", (root / f"{profile_name}.cms").read_bytes())
                    with patch.object(module.sys, "platform", "darwin"), \
                            patch.object(module, "apple_profile_roots", return_value=(root / "trusted.pem").read_bytes()), \
                            patch.object(module, "apple_tool", side_effect=only_mock_app_signature):
                        with self.assertRaises(module.InvalidPackage):
                            module.package(root / "test.ipa", "https://example.com/a.ipa",
                                           "https://example.com/manifest.plist", root / "public")
                    self.assertFalse((root / "public").exists())

    def test_unsigned_input_does_not_create_public_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with zipfile.ZipFile(root / "test.ipa", "w") as archive:
                archive.writestr("Payload/App.app/Info.plist", b"not-signed")
            with self.assertRaises(module.InvalidPackage):
                module.package(root / "test.ipa", "https://example.com/a.ipa",
                               "https://example.com/manifest.plist", root / "public")
            self.assertFalse((root / "public").exists())


if __name__ == "__main__":
    unittest.main()
