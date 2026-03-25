#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEMPLATE_DIR="$ROOT_DIR/templates/agentic-workflow"

FORCE=0
DRY_RUN=0
TARGET_DIR=""

usage() {
  echo "Usage: $0 [--force] [--dry-run] <target-repo-path>"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      FORCE=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      TARGET_DIR="$1"
      shift
      ;;
  esac
done

if [[ -z "$TARGET_DIR" ]]; then
  usage
  exit 1
fi

if [[ ! -d "$TARGET_DIR" ]]; then
  echo "Target directory does not exist: $TARGET_DIR" >&2
  exit 1
fi

copy_file() {
  local src="$1"
  local dst="$2"
  if [[ $DRY_RUN -eq 1 ]]; then
    if [[ -e "$dst" && $FORCE -ne 1 ]]; then
      echo "skip  $dst (exists)"
    else
      echo "write $dst (dry-run)"
    fi
    return 0
  fi
  mkdir -p "$(dirname "$dst")"
  if [[ -e "$dst" && $FORCE -ne 1 ]]; then
    echo "skip  $dst (exists)"
    return 0
  fi
  cp "$src" "$dst"
  echo "write $dst"
}

copy_file "$TEMPLATE_DIR/CLAUDE.md" "$TARGET_DIR/CLAUDE.md"
copy_file "$TEMPLATE_DIR/COPILOT.md" "$TARGET_DIR/COPILOT.md"
copy_file "$TEMPLATE_DIR/.github/copilot-instructions.md" "$TARGET_DIR/.github/copilot-instructions.md"
copy_file "$TEMPLATE_DIR/.agentic/right-thing.yaml" "$TARGET_DIR/.agentic/right-thing.yaml"
copy_file "$TEMPLATE_DIR/tasks/todo.md" "$TARGET_DIR/tasks/todo.md"
copy_file "$TEMPLATE_DIR/tasks/lessons.md" "$TARGET_DIR/tasks/lessons.md"

echo "Agentic workflow template scaffolded into: $TARGET_DIR"
