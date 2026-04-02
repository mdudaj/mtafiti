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
python .github/scripts/query_knowledge_graph.py --report layers
python .github/scripts/query_knowledge_graph.py --report dependencies
python .github/scripts/query_knowledge_graph.py --report behavioral
```

Generated artifacts are committed under:

* `analysis/environment_inventory.yaml`
* `knowledge_graph/{ontology,nodes,edges}.yaml`
* `ontology/{ui,navigation,workflow,state,permission,cross-layer}.yaml`
* `skills/generated_skills.yaml`
* `.github/skills/*/SKILL.md`
* `framework_knowledge/{django,viewflow,django_material}.yaml`

The canonical skill source now lives in `.github/scripts/knowledge_graph_lib.py`. Both `skills/generated_skills.yaml` and workspace-native Copilot skills under `.github/skills/` are generated artifacts, so update the generator definitions and regenerate rather than editing either output by hand.

To regenerate both the YAML inventory and the workspace skill files in one step, run:

```bash
./scripts/sync_skills.sh
```

The generated skill descriptions intentionally use a `Use when ...` discovery pattern so Copilot can match them more reliably during skill selection.
Generated skills also carry target-layer, dependency, and confidence metadata so they can evolve toward a composable skill graph instead of staying a flat inventory.

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

To bootstrap the expected Viewflow framework-analysis source set first, use:

```bash
python .github/scripts/configure_knowledge_sources.py \
  --source-root /home/jmduda/KodeX.2026/knowledge-src \
  --bootstrap-viewflow-stack
```

That writes a machine-readable manifest plus an operator guide covering:

* `git@github.com:viewflow/viewflow.git`
* `git@github.com:viewflow/django-material.git`
* `git@github.com:viewflow/cookbook.git`
* `https://demo.viewflow.io/` as the separate behavioral evidence source

To capture the configured demo site into raw HTML, normalized page models, and a markdown summary report, run:

```bash
python .github/scripts/capture_behavioral_sources.py \
  --source-root /home/jmduda/KodeX.2026/knowledge-src \
  --source-name viewflow-demo-site
```

This writes capture artifacts under `/home/jmduda/KodeX.2026/knowledge-src/.mtafiti/behavioral-captures/viewflow-demo-site/`.

Each capture also stores a timestamped run under `runs/`, promotes page models into `patterns.json`, `patterns.md`, and `ontology-candidates.json`, and keeps the latest summary/report artifacts at the source root for quick inspection.

If the demo requires client-side rendering, request browser-backed capture:

```bash
python .github/scripts/capture_behavioral_sources.py \
  --source-root /home/jmduda/KodeX.2026/knowledge-src \
  --source-name viewflow-demo-site \
  --fetch-mode browser
```

For a richer JavaScript-aware capture path that waits for a real browser session and then records `page.content()`, use the Playwright-backed mode:

```bash
python .github/scripts/capture_behavioral_sources.py \
  --source-root /home/jmduda/KodeX.2026/knowledge-src \
  --source-name viewflow-demo-site \
  --fetch-mode playwright
```

To compare two stored capture runs, use:

```bash
python .github/scripts/capture_behavioral_sources.py diff \
  --source-root /home/jmduda/KodeX.2026/knowledge-src \
  --source-name viewflow-demo-site \
  --baseline-run 20260328T120000Z \
  --candidate-run 20260328T123000Z
```

To import the latest promoted behavioral artifacts back into this repository so the canonical generator can ingest them into committed ontology and skill outputs, run:

```bash
python .github/scripts/capture_behavioral_sources.py import \
  --source-root /home/jmduda/KodeX.2026/knowledge-src \
  --source-name viewflow-demo-site \
  --repo-root /home/jmduda/KodeX.2026/mtafiti

python .github/scripts/generate_knowledge_graph.py
python .github/scripts/query_knowledge_graph.py --report behavioral
```

### Spec-first delivery with Spec Kit

This repository now keeps project-local `spec-kit` rules under `.specify/` and expects substantial work to flow through:

1. `/speckit.specify`
2. `/speckit.plan`
3. `/speckit.tasks`
4. `python .github/scripts/spec_kit_workflow.py issue-body specs/<feature>`
5. `python .github/scripts/spec_kit_workflow.py pr-body specs/<feature>`

Install the upstream CLI with:

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
```

See `docs/spec-kit-workflow.md` for the repository-specific workflow, branch naming rules, and how knowledge graph / Context Hub inputs fit into the spec bundle.

### Faster local feedback loop

```bash
# targeted change validation (example)
.github/scripts/local_fast_feedback.sh tests/test_printing_api.py -k gateway

# broader local gate (docs checks + non-perf backend suite)
.github/scripts/local_fast_feedback.sh --full-gate
```

Validation artifacts are written to `./test-results/` by default:

* `test-results/local-fast-feedback.log`
* `test-results/full-gate.log`
* `test-results/pytest-targeted.xml`
* `test-results/pytest-full-gate.xml`

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
