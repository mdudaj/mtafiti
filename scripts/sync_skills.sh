#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python_bin="${PYTHON_BIN:-$repo_root/.venv/bin/python}"

if [[ ! -x "$python_bin" ]]; then
  echo "Python executable not found: $python_bin" >&2
  echo "Set PYTHON_BIN or create the workspace virtualenv first." >&2
  exit 1
fi

"$python_bin" "$repo_root/.github/scripts/generate_knowledge_graph.py"
"$python_bin" "$repo_root/.github/scripts/generate_knowledge_graph.py" --check

echo "Skills and knowledge-graph artifacts are synced."
