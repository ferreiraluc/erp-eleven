#!/usr/bin/env python3
"""Validate an exported Ad Hoc IPA on macOS; emit public installation metadata.

This does not sign, upload, register devices, or publish anything. Never copy the
embedded profile or device identifiers into the output directory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import plistlib
import re
import stat
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
import zipfile

MAX_UNPACKED_BYTES = 1024 * 1024 * 1024
MAX_PLIST_BYTES = 4 * 1024 * 1024


class InvalidPackage(ValueError):
    pass


def https_url(value: str, extension: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
            parsed.password or parsed.fragment or parsed.query or
            not parsed.path.lower().endswith(extension) or
            any(ord(c) < 33 for c in value)):
        raise InvalidPackage(f"Use uma URL HTTPS estável terminada em {extension}, sem credenciais, query ou fragmento.")
    return value


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def validate_profile(info: dict, profile: dict, entitlements: dict, *, expected_bundle_id: str,
                     now: datetime | None = None) -> dict:
    """Validate metadata only; cryptographic verification is a separate mandatory step."""
    if not all(isinstance(value, dict) for value in (info, profile, entitlements)):
        raise InvalidPackage("Metadados de assinatura inválidos.")
    now = utc(now or datetime.now(timezone.utc))
    bundle_id = info.get("CFBundleIdentifier")
    if bundle_id != expected_bundle_id or not re.fullmatch(r"[A-Za-z0-9.-]+", bundle_id or ""):
        raise InvalidPackage("O bundle ID não corresponde ao aplicativo esperado.")
    if info.get("CFBundleSupportedPlatforms") != ["iPhoneOS"]:
        raise InvalidPackage("O pacote deve ser para iPhone/iPad físico, não simulador.")
    version, build = info.get("CFBundleShortVersionString"), info.get("CFBundleVersion")
    if not all(isinstance(v, str) and re.fullmatch(r"[0-9]+(?:\.[0-9]+){0,2}", v) for v in (version, build)):
        raise InvalidPackage("Versão ou número de build inválido no Info.plist.")
    expiration = profile.get("ExpirationDate")
    if not isinstance(expiration, datetime) or utc(expiration) <= now:
        raise InvalidPackage("O perfil de provisionamento está ausente ou vencido.")
    devices = profile.get("ProvisionedDevices")
    if not isinstance(devices, list) or not devices or not all(isinstance(d, str) and d for d in devices):
        raise InvalidPackage("O perfil Ad Hoc precisa incluir aparelhos registrados.")
    if profile.get("ProvisionsAllDevices"):
        raise InvalidPackage("Perfil Enterprise não é aceito por este fluxo Ad Hoc.")
    granted = profile.get("Entitlements", {})
    if not isinstance(granted, dict) or not isinstance(entitlements, dict):
        raise InvalidPackage("Entitlements inválidos.")
    if granted.get("get-task-allow") is not False or entitlements.get("get-task-allow") is not False:
        raise InvalidPackage("Pacote de desenvolvimento/debug não pode ser publicado como Ad Hoc.")
    prefixes = profile.get("ApplicationIdentifierPrefix") or []
    expected_ids = {f"{prefix}.{bundle_id}" for prefix in prefixes if isinstance(prefix, str)}
    application_id = granted.get("application-identifier")
    if application_id not in expected_ids or entitlements.get("application-identifier") != application_id:
        raise InvalidPackage("A identidade assinada não corresponde ao perfil Ad Hoc explícito.")
    team = entitlements.get("com.apple.developer.team-identifier")
    teams = profile.get("TeamIdentifier")
    if not isinstance(teams, list) or team not in teams or granted.get("com.apple.developer.team-identifier") != team:
        raise InvalidPackage("A equipe da assinatura não corresponde ao perfil.")
    return {
        "status": "ready", "version": version, "build": build, "bundleId": bundle_id,
        "expiresAt": utc(expiration).isoformat().replace("+00:00", "Z"),
    }


def unpack(ipa: Path, directory: Path) -> Path:
    with zipfile.ZipFile(ipa) as archive:
        members = archive.infolist()
        if len(members) > 30000 or sum(item.file_size for item in members) > MAX_UNPACKED_BYTES:
            raise InvalidPackage("IPA excede o limite de tamanho/arquivos para validação.")
        seen = set()
        for item in members:
            path = PurePosixPath(item.filename)
            mode = item.external_attr >> 16
            if (path.is_absolute() or ".." in path.parts or "\\" in item.filename or
                    item.filename in seen or stat.S_ISLNK(mode)):
                raise InvalidPackage("IPA contém caminho inválido, duplicado ou link simbólico.")
            seen.add(item.filename)
            if item.flag_bits & 1:
                raise InvalidPackage("IPA criptografado não é suportado.")
        app_paths = {str(PurePosixPath(i.filename).parent) for i in members
                     if re.fullmatch(r"Payload/[^/]+\.app/Info\.plist", i.filename)}
        if len(app_paths) != 1:
            raise InvalidPackage("IPA precisa conter exatamente um aplicativo principal.")
        archive.extractall(directory)
        for item in members:
            if not item.is_dir():
                # Restore executable permissions needed by Apple's code verifier;
                # no setuid, setgid or writable-by-everyone bits are restored.
                (directory / item.filename).chmod(0o755 if (item.external_attr >> 16) & 0o111 else 0o644)
    return directory / app_paths.pop()


def apple_tool(args: list[str]) -> bytes:
    try:
        result = subprocess.run(args, capture_output=True, check=True, timeout=60)
        return result.stdout
    except (OSError, subprocess.SubprocessError) as exc:
        # Tool output may contain profile/device details. Keep it out of CI logs.
        raise InvalidPackage(f"Falha na validação Apple ({Path(args[0]).name}); nenhum pacote foi publicado.") from exc


def apple_profile_roots() -> bytes:
    # Only immutable Apple-supplied system roots; never trust a profile's root or
    # certificates imported into a user's login keychain.
    roots = apple_tool(["/usr/bin/security", "find-certificate", "-a", "-c", "Apple Root", "-p",
                        "/System/Library/Keychains/SystemRootCertificates.keychain"])
    if b"-----BEGIN CERTIFICATE-----" not in roots:
        raise InvalidPackage("Não foi possível obter as raízes públicas Apple do sistema.")
    return roots


def verified_profile(profile_file: Path, work: Path) -> dict:
    """Verify CMS content AND its Apple chain before trusting the embedded plist.

    `security cms -D` merely decodes some CMS containers, including containers
    without signers; it must never be used as evidence of a trusted signature.
    """
    roots_file = work / "apple-profile-roots.pem"
    roots_file.write_bytes(apple_profile_roots())
    empty_ca_path = work / "empty-ca-path"
    empty_ca_path.mkdir()
    signer_file = work / "profile-cms-signer.pem"
    payload = apple_tool(["/usr/bin/openssl", "cms", "-verify", "-binary", "-inform", "DER",
                          "-in", str(profile_file), "-CAfile", str(roots_file),
                          "-CApath", str(empty_ca_path), "-purpose", "any", "-signer", str(signer_file)])
    if len(payload) > MAX_PLIST_BYTES or not signer_file.is_file():
        raise InvalidPackage("Perfil CMS sem assinante verificado ou conteúdo inválido.")
    signer = signer_file.read_bytes()
    if signer.count(b"-----BEGIN CERTIFICATE-----") != 1:
        raise InvalidPackage("O perfil deve ter exatamente um assinante Apple verificado.")
    subject = apple_tool(["/usr/bin/openssl", "x509", "-in", str(signer_file), "-noout",
                          "-subject", "-nameopt", "RFC2253"]).decode("utf-8", errors="strict").strip()
    # A normal Apple-issued app developer certificate must not be allowed to
    # issue profiles. Unknown future Apple signer names fail closed for review.
    if not (re.search(r"(?:^|,)CN=Apple iPhone OS Provisioning Profile Signing(?: G[0-9]+)?(?:,|$)",
                      subject.removeprefix("subject=")) and
            re.search(r"(?:^|,)O=Apple Inc\.(?:,|$)", subject.removeprefix("subject="))):
        raise InvalidPackage("O assinante CMS não é o emissor Apple de perfis iOS esperado.")
    profile = plistlib.loads(payload)
    if not isinstance(profile, dict):
        raise InvalidPackage("Conteúdo do perfil CMS inválido.")
    return profile


def read_plist(path: Path) -> dict:
    if path.stat().st_size > MAX_PLIST_BYTES:
        raise InvalidPackage("Plist excede o limite de leitura.")
    value = plistlib.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise InvalidPackage("Plist inválido.")
    return value


def package(ipa: Path, ipa_url: str, manifest_url: str, output: Path,
            expected_bundle_id: str = "com.elevenparispy.erp") -> dict:
    ipa_url = https_url(ipa_url, ".ipa")
    manifest_url = https_url(manifest_url, ".plist")
    if sys.platform != "darwin":
        raise InvalidPackage("Execute no macOS para verificar assinatura com security/codesign.")
    if not ipa.is_file() or ipa.suffix.lower() != ".ipa":
        raise InvalidPackage("Informe o IPA Ad Hoc exportado pelo Xcode.")
    with tempfile.TemporaryDirectory(prefix="eleven-adhoc-") as temporary:
        root = Path(temporary)
        app = unpack(ipa, root)
        profile_file = app / "embedded.mobileprovision"
        if not profile_file.is_file() or profile_file.stat().st_size > MAX_PLIST_BYTES:
            raise InvalidPackage("Perfil assinado ausente ou inválido no IPA.")
        apple_tool(["/usr/bin/codesign", "--verify", "--deep", "--strict", "-R=anchor apple generic", str(app)])
        profile = verified_profile(profile_file, root)
        entitlements = plistlib.loads(apple_tool(["/usr/bin/codesign", "-d", "--entitlements", ":-", str(app)]))
        info = read_plist(app / "Info.plist")
        metadata = validate_profile(info, profile, entitlements, expected_bundle_id=expected_bundle_id)
        # Bind the application's actual signing certificate to the profile. A
        # valid signature alone does not imply authorization for these devices.
        certificate_prefix = root / "signing-cert-"
        apple_tool(["/usr/bin/codesign", "-d", "--extract-certificates", str(certificate_prefix), str(app)])
        signer = Path(f"{certificate_prefix}0").read_bytes()
        if signer not in profile.get("DeveloperCertificates", []):
            raise InvalidPackage("O certificado do aplicativo não está autorizado pelo perfil.")
    with ipa.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    metadata.update(url=ipa_url, manifestUrl=manifest_url, sizeBytes=ipa.stat().st_size, sha256=digest)
    manifest = {"items": [{
        "assets": [{"kind": "software-package", "url": ipa_url}],
        "metadata": {"bundle-identifier": metadata["bundleId"], "bundle-version": metadata["build"],
                     "kind": "software", "title": "Eleven"},
    }]}
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.plist").write_bytes(plistlib.dumps(manifest, sort_keys=False))
    (output / "ios-release.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ipa", type=Path)
    parser.add_argument("--ipa-url", required=True)
    parser.add_argument("--manifest-url", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-bundle-id", default="com.elevenparispy.erp")
    args = parser.parse_args()
    try:
        metadata = package(args.ipa, args.ipa_url, args.manifest_url, args.output, args.expected_bundle_id)
    except (InvalidPackage, OSError, ValueError, zipfile.BadZipFile, plistlib.InvalidFileException) as exc:
        print(f"Não foi possível preparar a instalação: {exc}", file=sys.stderr)
        return 1
    print(f"Manifesto e metadados preparados: versão {metadata['version']} ({metadata['build']}); "
          f"validade {metadata['expiresAt']}. Nenhum arquivo enviado ou ativado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
