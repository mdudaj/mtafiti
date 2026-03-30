# Feature Specification: Behavioral artifact ingestion and Playwright-backed capture

**Feature ID**: `010-behavioral-artifact-ingestion-and-playwright`  
**Execution Branch**: `feat/behavioral-artifact-ingestion-and-playwright`  
**Created**: 2026-03-30  
**Status**: Draft  
**Input**: User description: "Validate the new behavioral capture slice, merge promoted capture artifacts back into committed ontology and skill generation, and add a real browser-backed capture path beyond simple dump-dom commands."

## Repository Context *(mandatory)*

- **Service area**: framework-analysis harness, behavioral capture workflow, canonical knowledge-graph generation
- **Affected code paths**: `.github/scripts/capture_behavioral_sources.py`, `.github/scripts/knowledge_graph_lib.py`, `.github/scripts/query_knowledge_graph.py`, `.github/scripts/configure_knowledge_sources.py`, `analysis/behavioral_patterns/`, `README.md`, `src/tests/`
- **Related design docs**: `specs/009-behavioral-pattern-promotion-and-diff/spec.md`, `specs/008-viewflow-demo-behavioral-capture/spec.md`, `docs/self-reflective-implementation.md`
- **Knowledge graph / skills evidence**: `knowledge_graph/*.yaml`, `ontology/*.yaml`, `skills/generated_skills.yaml`, `.github/skills/*/SKILL.md`

## Architectural Position

This slice extends `009` without creating a second harness path. Behavioral capture remains external-evidence acquisition, but promoted outputs can now be imported into a tracked repository surface and consumed by the canonical generator. Real browser-backed capture is added as an optional Playwright path using local runtime tooling, while direct HTTP and dump-dom capture remain available.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import promoted behavioral artifacts into the canonical generator (Priority: P1)

As a harness maintainer, I want promoted capture artifacts imported into a tracked repository path so committed ontology and skill outputs can incorporate demo behavior.

**Independent Test**: Import promoted artifacts and confirm the generated bundle contains behavioral source nodes, pattern nodes, observed ontology entries, and low-confidence behavior-derived skills.

### User Story 2 - Capture rendered DOM through a real browser runtime (Priority: P1)

As an operator, I want a Playwright-backed capture mode so the harness can wait for a real browser session and serialize `page.content()` when dump-dom output is insufficient.

**Independent Test**: Run the Playwright-backed path in a focused test or runtime probe and confirm HTML is produced from a launched browser session.

### User Story 3 - Package and validate the new slice (Priority: P2)

As a maintainer, I want spec and merge-gate validation run as far as the workspace allows so the slice is packaged consistently with the repository workflow.

**Independent Test**: Validate the spec bundle, regenerate knowledge-graph outputs, and run the focused test suites.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The capture script MUST support importing the latest promoted artifacts into a tracked repository path under `analysis/behavioral_patterns/`.
- **FR-002**: The canonical generator MUST ingest imported behavioral artifacts into committed nodes, ontology observations, and generated skills.
- **FR-003**: Behavior-derived skills generated from imported artifacts MUST remain explicitly low confidence until source-code evidence is merged.
- **FR-004**: The capture script MUST support a Playwright-backed fetch mode that launches a real browser runtime and records `page.content()`.
- **FR-005**: The query surface MUST expose a behavioral summary report for imported behavioral sources.
- **FR-006**: The slice MUST be documented and validated through the repository’s spec-first workflow.

## Success Criteria *(mandatory)*

- **SC-001**: Imported behavioral artifacts appear in committed ontology and skill outputs after regeneration.
- **SC-002**: Focused tests pass for import behavior, graph ingestion, and the expanded capture/bootstrap workflow.
- **SC-003**: The repository documents both Playwright-backed capture and behavioral artifact import clearly enough for repeatable use.

## Delivery Mapping *(mandatory)*

- **Primary issue title**: Ingest behavioral artifacts into the canonical graph and add Playwright capture
- **Planned branch label**: `feat/behavioral-artifact-ingestion-and-playwright`
- **Expected PR scope**: capture script + generator ingestion + docs + tests + tracked behavioral seed artifacts