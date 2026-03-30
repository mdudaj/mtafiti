# Feature Specification: Behavioral ontology and skill-graph harness upgrade

**Feature ID**: `007-behavioral-ontology-skill-graph`  
**Execution Branch**: `feat/behavioral-ontology-skill-graph`  
**Created**: 2026-03-28  
**Status**: Draft  
**Input**: User description: "Upgrade the current agentic harness so it can learn from the full Viewflow demo surface plus Viewflow, django-material, and cookbook source code, then generalize that knowledge into a multi-layer ontology and dependency-aware skill graph."

## Repository Context *(mandatory)*

- **Service area**: agentic harness, knowledge graph generation, external framework-ingestion workflow
- **Affected code paths**: `.github/scripts/knowledge_graph_lib.py`, `.github/scripts/configure_knowledge_sources.py`, `templates/agentic-workflow/`, `docs/self-reflective-implementation.md`, `README.md`, `src/tests/`
- **Related design docs**: `docs/self-reflective-implementation.md`, `docs/spec-kit-workflow.md`, `docs/workflow-ui.md`, `README.md`
- **Knowledge graph / skills evidence**: `skills/generated_skills.yaml`, `.github/skills/*/SKILL.md`, `framework_knowledge/viewflow.yaml`, `framework_knowledge/django_material.yaml`
- **External API lookup needs**: Viewflow demo site behavior and cloned repositories for `viewflow`, `django-material`, and `cookbook`
- **Related issues / PRs**: None

## Architectural Position

This slice extends the current harness rather than replacing it. The existing right-target contract, 3-phase execution flow, and lesson loop remain authoritative, but the harness is upgraded to support a second mode: behavior-first framework mining backed by source-level validation.

That mode introduces three durable concepts:

- a multi-layer ontology for UI, navigation, workflow, state, permissions, and cross-layer relations,
- a dependency-aware skill graph with explicit confidence and provenance metadata,
- a repeatable acquisition workflow for the Viewflow stack so demo behavior and source repositories can be analyzed together.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Model framework behavior in ontology layers (Priority: P1)

As a harness maintainer, I want the knowledge-graph generator to emit layered ontology artifacts so framework-learning work does not collapse UI, workflow, navigation, and permission concerns into one flat note set.

**Why this priority**: Without explicit ontology layers, later demo-site analysis will produce brittle summaries instead of reusable graph structure.

**Independent Test**: Generate the knowledge graph and confirm `ontology/ui.yaml`, `ontology/navigation.yaml`, `ontology/workflow.yaml`, `ontology/state.yaml`, `ontology/permission.yaml`, and `ontology/cross-layer.yaml` are emitted with expected entities.

**Acceptance Scenarios**:

1. **Given** the repository generator runs, **When** bundle artifacts are written, **Then** layered ontology files exist alongside the existing knowledge graph.
2. **Given** an ontology consumer reads the generated artifacts, **When** it inspects layer definitions, **Then** UI, navigation, workflow, state, permission, and cross-layer backbone concepts are explicit.

---

### User Story 2 - Promote harness skills into a dependency-aware skill graph (Priority: P1)

As a harness maintainer, I want generated skills to carry layer, dependency, confidence, and provenance metadata so complex framework-derived capabilities can be composed rather than hard-coded into monolithic recipes.

**Why this priority**: The current skill inventory is useful but too flat to drive multi-step framework analysis and composition safely.

**Independent Test**: Generate the skill inventory and confirm representative skills expose `layer`, `depends_on`, and `confidence` metadata, and that dependency edges appear in the graph.

**Acceptance Scenarios**:

1. **Given** the skill generator runs, **When** it emits the skill inventory and markdown skill files, **Then** each skill can declare a target layer and dependency skills.
2. **Given** the graph generator builds edges, **When** a skill depends on another skill, **Then** a `depends_on` relationship links them.

---

### User Story 3 - Bootstrap Viewflow-stack source acquisition (Priority: P2)

As a framework-analysis operator, I want a repository-supported bootstrap path for `viewflow`, `django-material`, `cookbook`, and the demo site so the harness can ingest the intended evidence set consistently.

**Why this priority**: The harness cannot perform durable framework mining if source acquisition remains implicit or tribal knowledge.

**Independent Test**: Run the knowledge-source configuration script with the bootstrap option and confirm it writes a machine-readable manifest and operator guide for the Viewflow stack.

**Acceptance Scenarios**:

1. **Given** a fresh knowledge-source root, **When** the bootstrap option is used, **Then** the script writes a manifest listing the required repositories and the demo-site behavioral source.
2. **Given** an operator reads the generated guide, **When** they prepare sources for Context Hub generation, **Then** the required clone and demo-capture steps are explicit.

## Edge Cases

- What happens when only source repositories are available and demo-site evidence is still missing?
- How does the harness represent low-confidence patterns that are observed in only one evidence layer?
- How do generated skill dependencies stay stable if a future refactor renames or splits one skill?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The generator MUST emit layered ontology artifacts for UI, navigation, workflow, state, permission, and cross-layer relations.
- **FR-002**: Generated skills MUST support explicit metadata for target layer, dependencies, and confidence.
- **FR-003**: Generated skill markdown MUST surface dependency and confidence metadata so the workspace skill files remain self-describing.
- **FR-004**: The graph generator MUST emit `depends_on` edges between skills when dependency metadata is present.
- **FR-005**: The source-bootstrap workflow MUST declare the required Viewflow stack repositories and the demo-site behavioral source in a machine-readable manifest.
- **FR-006**: The source-bootstrap workflow MUST produce operator guidance that explains how to capture behavioral demo evidence separately from cloned repositories.
- **FR-007**: The implementation MUST preserve the existing harness execution controls instead of introducing a parallel workflow contract.

### Non-Goals

- Implementing a full browser crawler for the Viewflow demo site in this slice.
- Replacing the current knowledge graph with a separate storage system.
- Generating final production-grade framework components from mined knowledge in this slice.

### Key Entities *(include if feature involves data)*

- **OntologyLayer**: A generated artifact that captures one analytical layer such as UI or workflow semantics.
- **SkillGraphNode**: A generated skill enriched with target layer, dependency, and confidence metadata.
- **FrameworkSourceManifest**: A machine-readable declaration of required source repositories and behavioral sources.

## Success Criteria *(mandatory)*

- **SC-001**: The repository can generate layered ontology files and a richer skill graph without breaking current knowledge-graph workflows.
- **SC-002**: The Viewflow-stack acquisition path is reproducible from repository scripts and documentation rather than only chat instructions.
- **SC-003**: Focused tests covering the generator and source-bootstrap flows pass after the upgrade.

## Delivery Mapping *(mandatory)*

- **Primary issue title**: Upgrade agentic harness for behavioral ontology and skill graph extraction
- **Planned branch label**: `feat/behavioral-ontology-skill-graph`
- **Expected PR scope**: docs + generator + tests + source-bootstrap script
- **Blocking dependencies**: None