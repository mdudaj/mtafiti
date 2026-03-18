# Mtafiti

Mtafiti is a Kubernetes-native, multi-tenant enterprise research data management system.

## Design docs

* [Architecture overview](docs/architecture.md)
* [Roadmap (design increments)](docs/roadmap.md)
* [Identity & access](docs/identity.md)
* [Identity lifecycle and membership operations](docs/identity-lifecycle.md)
* [Notification delivery hardening](docs/notification-delivery.md)
* [Governance & policy](docs/governance.md)
* [Governance workflows](docs/governance-workflows.md)
* [Workflow engine and UI](docs/workflow-ui.md)
* [API versioning policy](docs/api-versioning.md)
* [API change communication checklist](docs/api-change-management.md)
* [Data privacy management](docs/privacy.md)
* [Data residency controls](docs/residency.md)
* [Data access requests](docs/access-requests.md)
* [Platform security baseline](docs/platform-security.md)
* [Platform services baseline](docs/platform-services.md)
* [Catalog growth](docs/catalog.md)
* [Printing and gateway](docs/printing.md)
* [Collaboration](docs/collaboration.md)
* [Notebook infrastructure](docs/notebooks.md)
* [Policy enforcement](docs/policy.md)
* [Data retention & lifecycle](docs/retention.md)
* [Audit events](docs/audit.md)
* [Request context propagation](docs/request-context.md)
* [Ingestion](docs/ingestion.md)
* [Connector execution model](docs/connectors.md)
* [Workflow orchestration](docs/orchestration.md)
* [Project membership and invitations](docs/project-membership.md)
* [Invitation security hardening](docs/invitation-security.md)
* [Lineage](docs/lineage.md)
* [Search](docs/search.md)
* [Data quality](docs/data-quality.md)
* [Data contracts](docs/data-contracts.md)
* [Data products](docs/data-products.md)
* [Data sharing](docs/data-sharing.md)
* [Agentic AI execution](docs/agentic-ai.md)
* [Self-reflective implementation workflow](docs/self-reflective-implementation.md)
* [Portable agentic workflow template](templates/agentic-workflow/README.md)
* [Metadata versioning](docs/metadata-versioning.md)
* [Reference data management](docs/reference-data.md)
* [Master data management](docs/master-data.md)
* [Data classification taxonomy](docs/classification.md)
* [Business glossary](docs/glossary.md)
* [Data stewardship operations](docs/stewardship.md)
* [Observability](docs/observability.md)
* [Metrics](docs/metrics.md)
* [Performance baseline](docs/performance-baseline.md)
* [Operational runbooks and incident playbooks](docs/operations-runbooks.md)
* [Operational dashboards and alert rules](docs/operations-dashboards-alerts.md)
* [Kubernetes deployment notes](docs/kubernetes.md)
* [Research LAB LIMS placeholder spec](docs/lab-lims.md)
* [EDCS placeholder spec](docs/edcs.md)
* [OpenAPI (HTTP surface)](docs/openapi.yaml)
* [Eventing conventions](docs/events.md)

## Django application (`src/` + schema-per-tenant)

* Framework: Django
* Multi-tenancy: `django-tenants` (schema-per-tenant)
* Async: Celery (RabbitMQ-backed)
* Kubernetes probes:
  * `GET /healthz` / `GET /livez` (liveness; no tenant host required)
  * `GET /readyz` (readiness; performs a DB round-trip; no tenant host required)

### Local dev prerequisites

* Python 3.12+
* PostgreSQL (local service is fine)
* Python code contributions should follow PEP 8 conventions.

### Run tests

```bash
docker compose up -d --wait postgres

cd src
python -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements-dev.txt

export POSTGRES_DB=mtafiti_test POSTGRES_USER=mtafiti POSTGRES_PASSWORD=mtafiti POSTGRES_HOST=localhost POSTGRES_PORT=5432
pytest

# faster local feedback (skip dedicated perf baseline lane)
pytest -q -k "not performance_baseline"

# run perf baseline separately
pytest -q tests/test_performance_baseline.py

# optional cleanup
docker compose down
```

Note: Django creates a separate test database (e.g. `test_mtafiti_test`) during `pytest`, so the configured `POSTGRES_USER` must have the `CREATEDB` privilege (or be a superuser).

### Local UI preview

```bash
# bootstrap database + tenant/service routes, then run Django
./scripts/local_preview.sh up

# or prepare once, then start/stop separately
./scripts/local_preview.sh prep
./scripts/local_preview.sh serve
./scripts/local_preview.sh down
```

The preview helper provisions a local tenant and prints service URLs such as:

* `http://workspace.local.localhost:8000/app`
* `http://lims.local.localhost:8000/lims/`

It also prepares an `edcs.local.localhost` route for future service work, even though EDCS does not yet expose a dedicated UI.

### Generate the knowledge graph

```bash
python .github/scripts/generate_knowledge_graph.py
python .github/scripts/query_knowledge_graph.py --type Skill --text dashboard
```

Generated artifacts are committed under:

* `analysis/environment_inventory.yaml`
* `knowledge_graph/{ontology,nodes,edges}.yaml`
* `skills/generated_skills.yaml`
* `framework_knowledge/{django,viewflow,django_material}.yaml`

For external API documentation retrieval, install Context Hub and use the commands embedded in the framework nodes:

```bash
npm install -g @aisuite/chub
chub update
chub search django
chub get django/forms
```

`chub update` refreshes configured registry sources; it does not pull directly from a git URL. To use docs from a git repository, clone the repo locally, structure or extract the docs as a Context Hub content directory, run `chub build <content-dir> -o <content-dir>/dist`, add that `dist` path under `sources[].path` in `~/.chub/config.yaml`, and then run `chub update`.

To turn a local repository collection into the designated Context Hub source, use:

```bash
python .github/scripts/configure_knowledge_sources.py \
  --source-root /home/jmduda/KodeX.2026/knowledge-src

chub update
chub search viewflow
chub search cookbook-crud101
chub search theme
```

### Faster local feedback loop

```bash
# targeted change validation (example)
.github/scripts/local_fast_feedback.sh tests/test_printing_api.py -k gateway

# broader local gate (docs checks + non-perf backend suite)
.github/scripts/local_fast_feedback.sh --full-gate
```

### Local operations UI preview (django-material optional)

```bash
# one command local preview (services + migrations + tenant + runserver)
./scripts/local_preview.sh up
```

HTML routes:
* `/app` (end-user workspace)
* `/ui/operations/dashboard`
* `/ui/operations/stewardship`
* `/ui/operations/orchestration`
* `/ui/operations/printing`
* `/ui/operations/agent`

Printing UI supports:
* printer (gateway) configuration
* print template definition
* template presets + inline preview for end users
* test print submission from selected template
* Zebra default batch mode: 9 labels per participant via prefix + range inputs
* end-user workspace at `/app` for template/printer setup and test print
* tenant service-route registry API: `GET/POST /api/v1/tenants/services` for wildcard hosts like `<service>.<tenant>.<base-domain>`
* PDF preview download: `GET /api/v1/printing/jobs/<job_id>/preview.pdf`

Useful subcommands:

```bash
./scripts/local_preview.sh prep    # dependencies + migrations + localhost tenant
./scripts/local_preview.sh serve   # run Django server only
./scripts/local_preview.sh status  # docker compose service status
./scripts/local_preview.sh down    # stop local services
```

Optional:

```bash
EDMP_UI_MATERIAL_ENABLED=true ./scripts/local_preview.sh up
EDMP_PREVIEW_PORT=8001 ./scripts/local_preview.sh up
```
