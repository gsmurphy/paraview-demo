#!/usr/bin/env bash
# run.sh — thin wrapper around the Makefile.
# Usage:
#   ./run.sh            # full pipeline
#   ./run.sh preview    # quick preview render
#   ./run.sh clean      # remove generated artifacts
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
make "${1:-all}"
