#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$ROOT_DIR/src"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"

export POSTGRES_DB="${POSTGRES_DB:-mtafiti_test}"
export POSTGRES_USER="${POSTGRES_USER:-mtafiti}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-mtafiti}"
export POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-localhost,127.0.0.1}"
export EDMP_UI_MATERIAL_ENABLED="${EDMP_UI_MATERIAL_ENABLED:-${MTAFITI_UI_MATERIAL_ENABLED:-false}}"
export MTAFITI_PREVIEW_PORT="${MTAFITI_PREVIEW_PORT:-${EDMP_PREVIEW_PORT:-8000}}"

usage() {
  echo "Usage: $0 [prep|serve|up|down|status]"
}

ensure_venv() {
  if [[ ! -x "$PYTHON_BIN" ]]; then
    python3 -m venv "$ROOT_DIR/.venv"
    "$PYTHON_BIN" -m pip install -q --upgrade pip
    "$PYTHON_BIN" -m pip install -q -r "$SRC_DIR/requirements-dev.txt"
  fi
}

prep() {
  cd "$ROOT_DIR"
  docker compose up -d --wait postgres rabbitmq
  ensure_venv
  cd "$SRC_DIR"
  "$PYTHON_BIN" manage.py migrate_schemas --shared --noinput
  "$PYTHON_BIN" manage.py migrate_schemas --tenant --noinput
  "$PYTHON_BIN" manage.py shell -c "from tenants.models import Tenant,Domain; t,_=Tenant.objects.get_or_create(schema_name='local', defaults={'name':'Local Tenant'}); Domain.objects.get_or_create(domain='localhost', tenant=t, defaults={'is_primary':True})"
}

serve() {
  local existing_pid
  existing_pid="$(ss -ltnp "( sport = :${MTAFITI_PREVIEW_PORT} )" 2>/dev/null | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' | head -n1 || true)"
  if [[ -n "${existing_pid}" ]]; then
    echo "Port ${MTAFITI_PREVIEW_PORT} is already in use by PID ${existing_pid}."
    echo "Stop it with: kill ${existing_pid}"
    echo "Or run on another port: MTAFITI_PREVIEW_PORT=8001 $0 serve"
    exit 1
  fi
  cd "$SRC_DIR"
  "$PYTHON_BIN" manage.py runserver "0.0.0.0:${MTAFITI_PREVIEW_PORT}"
}

command="${1:-up}"
case "$command" in
  prep)
    prep
    ;;
  serve)
    serve
    ;;
  up)
    prep
    serve
    ;;
  down)
    cd "$ROOT_DIR"
    docker compose down
    ;;
  status)
    cd "$ROOT_DIR"
    docker compose ps
    ;;
  *)
    usage
    exit 1
    ;;
esac
