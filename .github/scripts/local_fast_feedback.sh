#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

FULL_GATE=0
if [[ "${1:-}" == "--full-gate" ]]; then
  FULL_GATE=1
  shift
fi

if [[ $FULL_GATE -eq 1 ]]; then
  python3 .github/scripts/check_docs_workflow.py --base-ref "${BASE_REF:-main}"
  python3 .github/scripts/check_openapi_contract.py
fi

docker compose up -d --wait postgres

PYTHON_BIN="python3"
if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
fi

cd src
if [[ $# -gt 0 ]]; then
  "$PYTHON_BIN" -m pytest -q "$@"
else
  "$PYTHON_BIN" -m pytest -q -k "not performance_baseline"
fi
