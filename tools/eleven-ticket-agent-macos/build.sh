#!/bin/bash
set -euo pipefail
agent_source="$(cd "$(dirname "$0")" && pwd)"
agent_output="${1:?Informe uma pasta de saída}"
mkdir -p "$agent_output"
agent_output="$(cd "$agent_output" && pwd)"
for arch in arm64 x86_64; do
  xcrun swiftc -swift-version 5 -O -whole-module-optimization \
    -target "$arch-apple-macos12.0" \
    "$agent_source/Core.swift" "$agent_source/main.swift" \
    -o "$agent_output/eleven-tickets-$arch"
done
xcrun lipo -create "$agent_output/eleven-tickets-arm64" "$agent_output/eleven-tickets-x86_64" -output "$agent_output/eleven-tickets"
/usr/bin/codesign --force --sign - --identifier com.eleven.tickets "$agent_output/eleven-tickets"
/usr/bin/codesign --verify --deep --strict "$agent_output/eleven-tickets"
rm "$agent_output/eleven-tickets-arm64" "$agent_output/eleven-tickets-x86_64"
for script in Instalar.command Iniciar.command Parar.command Diagnostico.command; do
  cp "$agent_source/$script" "$agent_output/$script"
  chmod 755 "$agent_output/$script"
  bash -n "$agent_output/$script"
done
cp "$agent_source/LEIA-ME.txt" "$agent_output/LEIA-ME.txt"
cd "$agent_output"
shasum -a 256 eleven-tickets > SHA256SUMS
