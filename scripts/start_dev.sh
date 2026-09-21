#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source .venv/bin/activate
export SKINMYBIRD_TEXCONV="${SKINMYBIRD_TEXCONV:-/workspace/tools/texconv.exe}"
echo "SkinMyBird → http://127.0.0.1:5173"
exec python server.py
