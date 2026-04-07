#!/usr/bin/env bash
# ── DocFlow – Quick Start ─────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ── 1. Check Python ───────────────────────────────────────────────
PYTHON=$(command -v python3 || command -v python)
if [[ -z "$PYTHON" ]]; then
  echo "❌  Python 3.11+ required but not found."
  exit 1
fi

PY_VERSION=$("$PYTHON" -c 'import sys; print(sys.version_info.minor)')
if [[ "$PY_VERSION" -lt 11 ]]; then
  echo "❌  Python 3.11+ required. Found: $("$PYTHON" --version)"
  exit 1
fi

# ── 2. Virtual environment ────────────────────────────────────────
if [[ ! -d ".venv" ]]; then
  echo "📦  Creating virtual environment…"
  "$PYTHON" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/Scripts/activate

# ── 3. Install dependencies ───────────────────────────────────────
echo "📥  Installing dependencies…"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# ── 4. Check service.json ─────────────────────────────────────────
if [[ ! -f "service.json" ]]; then
  echo "⚠️   service.json not found. Copy your GCP service account key here."
  echo "    Then re-run this script."
  exit 1
fi

export GOOGLE_APPLICATION_CREDENTIALS="$ROOT/service.json"

# ── 5. Load .env if present ───────────────────────────────────────
if [[ -f ".env" ]]; then
  # Export each non-comment line
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  echo "✅  Loaded .env"
else
  echo "⚠️   No .env file found. Using .env.example defaults."
  echo "    Copy .env.example → .env and fill in your values."
fi

# ── 6. Start backend ──────────────────────────────────────────────
echo ""
echo "🚀  Starting DocFlow backend at http://localhost:8000"
echo "    Frontend: http://localhost:8000/"
echo ""

uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --log-level info
