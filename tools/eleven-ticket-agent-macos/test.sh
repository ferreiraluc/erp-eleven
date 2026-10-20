#!/bin/bash
set -euo pipefail
agent_source="$(cd "$(dirname "$0")" && pwd)"
agent_tests="$(mktemp -d)"
trap 'rm -rf "$agent_tests"' EXIT
xcrun swiftc -swift-version 5 "$agent_source/Core.swift" "$agent_source/tests/CoreTests.swift" -o "$agent_tests/tests"
"$agent_tests/tests" "$@"
