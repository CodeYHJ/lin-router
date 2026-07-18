#!/usr/bin/env bash
set -e

# Compatibility wrapper; implementation lives under packaging/desktop.
exec "$(cd "$(dirname "$0")/.." && pwd)/packaging/desktop/build.sh" "$@"
