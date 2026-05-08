#!/usr/bin/env bash
# setup.sh — install dependencies for the ParaView protein demo.
# Idempotent: safe to re-run.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

bold()  { printf "\033[1m%s\033[0m\n" "$*"; }
warn()  { printf "\033[33m%s\033[0m\n" "$*"; }
fail()  { printf "\033[31m%s\033[0m\n" "$*" >&2; exit 1; }

bold "==> Checking macOS prerequisites"
[[ "$(uname)" == "Darwin" ]] || fail "setup.sh targets macOS. See README for manual Linux steps."
command -v brew >/dev/null || fail "Homebrew not found. Install from https://brew.sh and re-run."

bold "==> Installing Homebrew dependencies (paraview, ffmpeg, gh, apbs)"
brew install --cask paraview || warn "ParaView cask install failed or already present"
brew install ffmpeg gh || warn "ffmpeg/gh install failed or already present"
# APBS replaces the now-broken server.poissonboltzmann.org REST path.
# Reasoning documented in README "APBS deviation from brief".
brew tap brewsci/bio 2>/dev/null || true
brew install brewsci/bio/apbs || warn "apbs install failed or already present"

bold "==> Locating pvbatch"
PVBATCH_CANDIDATE=$(ls -d /Applications/ParaView-*.app/Contents/bin/pvbatch 2>/dev/null | sort -V | tail -1 || true)
if [[ -z "$PVBATCH_CANDIDATE" ]]; then
  fail "pvbatch not found. Open ParaView.app once to satisfy macOS Gatekeeper, then re-run setup.sh."
fi
echo "Found: $PVBATCH_CANDIDATE"

# Symlink into ./bin/pvbatch so Makefile/run.sh can invoke a stable path.
mkdir -p "$REPO_ROOT/bin"
ln -sf "$PVBATCH_CANDIDATE" "$REPO_ROOT/bin/pvbatch"
echo "Symlinked $REPO_ROOT/bin/pvbatch -> $PVBATCH_CANDIDATE"

bold "==> Creating Python virtualenv (.venv)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip wheel >/dev/null
pip install -r requirements.txt

bold "==> Setup complete"
echo "Run 'make' (or './run.sh') to build out/demo.mp4."
