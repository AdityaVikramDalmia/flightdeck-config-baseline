#!/usr/bin/env bash
# Deprecated reference example for new Claude Code integrations (2026-09-22).
set -euo pipefail
TOOL="$(cd "$(dirname "$0")/../bin" && pwd)/config-baseline"
DEMO_DIR="$(mktemp -d "${TMPDIR:-/tmp}/config-baseline-demo.XXXXXXXX")"
trap 'rm -rf "$DEMO_DIR"' EXIT
mkdir "$DEMO_DIR/config"
printf 'enabled=true\n' >"$DEMO_DIR/config/settings.conf"
"$TOOL" snapshot --manifest "$DEMO_DIR/reference.json" --root "app=$DEMO_DIR/config"
"$TOOL" check --manifest "$DEMO_DIR/reference.json" --root "app=$DEMO_DIR/config"
printf 'enabled=false\n' >"$DEMO_DIR/config/settings.conf"
printf 'new setting\n' >"$DEMO_DIR/config/new.conf"
if "$TOOL" check --json --manifest "$DEMO_DIR/reference.json" --root "app=$DEMO_DIR/config"; then
  echo 'Expected differences' >&2
  exit 1
else
  result=$?
  [ "$result" -eq 3 ]
fi
