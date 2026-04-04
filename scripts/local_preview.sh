#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$ROOT_DIR/src"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
TENANT_SLUG="${MTAFITI_PREVIEW_TENANT_SLUG:-local}"
BASE_DOMAIN="${MTAFITI_PREVIEW_BASE_DOMAIN:-localhost}"
WORKSPACE_HOST="workspace.${TENANT_SLUG}.${BASE_DOMAIN}"
LIMS_HOST="lims.${TENANT_SLUG}.${BASE_DOMAIN}"
EDCS_HOST="edcs.${TENANT_SLUG}.${BASE_DOMAIN}"

export POSTGRES_DB="${POSTGRES_DB:-mtafiti}"
export POSTGRES_USER="${POSTGRES_USER:-mtafiti}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-mtafiti}"
export POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-localhost,127.0.0.1,.localhost}"
export EDMP_UI_MATERIAL_ENABLED="${EDMP_UI_MATERIAL_ENABLED:-${MTAFITI_UI_MATERIAL_ENABLED:-false}}"
export MTAFITI_PREVIEW_PORT="${MTAFITI_PREVIEW_PORT:-${EDMP_PREVIEW_PORT:-8000}}"

usage() {
  echo "Usage: $0 [prep|serve|up|down|status|urls]"
}

print_urls() {
  cat <<EOF
Preview URLs
  Workspace: http://${WORKSPACE_HOST}:${MTAFITI_PREVIEW_PORT}/app
  LIMS:      http://${LIMS_HOST}:${MTAFITI_PREVIEW_PORT}/lims/
  EDCS:      http://${EDCS_HOST}:${MTAFITI_PREVIEW_PORT}/
EOF
}

ensure_venv() {
  if [[ ! -x "$PYTHON_BIN" ]]; then
    python3 -m venv "$ROOT_DIR/.venv"
    "$PYTHON_BIN" -m pip install -q --upgrade pip
    "$PYTHON_BIN" -m pip install -q -r "$SRC_DIR/requirements-dev.txt"
  fi
}

ensure_database() {
  "$PYTHON_BIN" - <<PY
import psycopg

conn = psycopg.connect(
    "host=${POSTGRES_HOST} port=${POSTGRES_PORT} dbname=postgres user=${POSTGRES_USER} password=${POSTGRES_PASSWORD}",
    autocommit=True,
)
with conn.cursor() as cur:
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", ("${POSTGRES_DB}",))
    if cur.fetchone() is None:
        cur.execute('CREATE DATABASE "${POSTGRES_DB}"')
        print("Created database ${POSTGRES_DB}")
    else:
        print("Database ${POSTGRES_DB} already exists")
conn.close()
PY
}

prep() {
  cd "$ROOT_DIR"
  docker compose up -d --wait postgres rabbitmq
  ensure_venv
  ensure_database
  cd "$SRC_DIR"
  "$PYTHON_BIN" manage.py migrate_schemas --shared --noinput
  "$PYTHON_BIN" manage.py migrate_schemas --tenant --noinput
  "$PYTHON_BIN" manage.py shell -c "from tenants.models import Tenant, Domain, TenantServiceRoute; tenant, created = Tenant.objects.get_or_create(schema_name='local', defaults={'name':'Local Tenant'}); primary_domain = '${TENANT_SLUG}.${BASE_DOMAIN}'; Domain.objects.update_or_create(domain=primary_domain, defaults={'tenant': tenant, 'is_primary': True}); routes = [('workspace', '${TENANT_SLUG}', '${BASE_DOMAIN}', '/app'), ('lims', '${TENANT_SLUG}', '${BASE_DOMAIN}', '/lims/'), ('edcs', '${TENANT_SLUG}', '${BASE_DOMAIN}', '/')]; [TenantServiceRoute.objects.update_or_create(service_key=service_key, tenant_slug=tenant_slug, base_domain=base_domain, defaults={'tenant': tenant, 'workspace_path': workspace_path, 'is_enabled': True}) for service_key, tenant_slug, base_domain, workspace_path in routes]; print(f'Prepared preview tenant {tenant.schema_name} for {primary_domain}')"
  print_urls
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
  print_urls
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
  urls)
    print_urls
    ;;
  *)
    usage
    exit 1
    ;;
esac
