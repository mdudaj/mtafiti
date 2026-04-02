#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

REPORTS_DIR="$ROOT_DIR/test-results"
mkdir -p "$REPORTS_DIR"

FULL_GATE=0
if [[ "${1:-}" == "--full-gate" ]]; then
  FULL_GATE=1
  shift
fi

LOG_FILE="$REPORTS_DIR/local-fast-feedback.log"
PYTEST_REPORT="$REPORTS_DIR/pytest-targeted.xml"
if [[ $FULL_GATE -eq 1 ]]; then
  LOG_FILE="$REPORTS_DIR/full-gate.log"
  PYTEST_REPORT="$REPORTS_DIR/pytest-full-gate.xml"
fi

exec > >(tee "$LOG_FILE") 2>&1

echo "Writing validation artifacts to $REPORTS_DIR"

if [[ $FULL_GATE -eq 1 ]]; then
  RELEVANT_PENDING_FILES="$(
    {
      git ls-files --others --exclude-standard -- '*.py' '*.yaml' '*.yml' '*.sh' '*.md'
      git ls-files --deleted -- '*.py' '*.yaml' '*.yml' '*.sh' '*.md'
    } | sort -u
  )"
  if [[ -n "$RELEVANT_PENDING_FILES" ]]; then
    echo "Full gate requires new or deleted source/doc files to be staged first." >&2
    echo "Run 'git add -A' (or stage the relevant files) before '.github/scripts/local_fast_feedback.sh --full-gate'." >&2
    echo "Pending files:" >&2
    echo "$RELEVANT_PENDING_FILES" >&2
    exit 1
  fi
  python3 .github/scripts/check_docs_workflow.py --base-ref "${BASE_REF:-main}"
  python3 .github/scripts/check_openapi_contract.py
  python3 .github/scripts/generate_knowledge_graph.py --check
fi

docker compose up -d --wait postgres

PYTHON_BIN="python3"
if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
fi

cd src
PYTEST_ARGS=("$@")
HAS_JUNITXML=0
for arg in "${PYTEST_ARGS[@]}"; do
  if [[ "$arg" == "--junitxml" || "$arg" == --junitxml=* ]]; then
    HAS_JUNITXML=1
    break
  fi
done

if [[ $HAS_JUNITXML -eq 0 ]]; then
  PYTEST_ARGS+=("--junitxml=$PYTEST_REPORT")
fi

if [[ $# -gt 0 ]]; then
  "$PYTHON_BIN" -m pytest -q "${PYTEST_ARGS[@]}"
else
  "$PYTHON_BIN" -m pytest -q -k "not performance_baseline" "${PYTEST_ARGS[@]}"
fi
