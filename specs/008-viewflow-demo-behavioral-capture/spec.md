# Feature Specification: Viewflow demo behavioral capture and ontology ingestion

**Feature ID**: `008-viewflow-demo-behavioral-capture`  
**Execution Branch**: `feat/viewflow-demo-behavioral-capture`  
**Created**: 2026-03-28  
**Status**: Draft  
**Input**: User description: "Capture the Viewflow demo surface into reusable behavioral artifacts, normalize those captures into page models, and make the results queryable alongside the existing ontology and skill graph."

## Repository Context *(mandatory)*

- **Service area**: framework-analysis harness, behavioral capture, graph query/report tooling
- **Affected code paths**: `.github/scripts/capture_behavioral_sources.py`, `.github/scripts/configure_knowledge_sources.py`, `.github/scripts/query_knowledge_graph.py`, `.github/scripts/knowledge_graph_lib.py`, `README.md`, `src/tests/`
- **Related design docs**: `specs/007-behavioral-ontology-skill-graph/spec.md`, `docs/self-reflective-implementation.md`, `README.md`
- **Knowledge graph / skills evidence**: `ontology/*.yaml`, `skills/generated_skills.yaml`, `.github/skills/*/SKILL.md`
- **External API lookup needs**: `https://demo.viewflow.io/` and the local Viewflow stack manifest under `.mtafiti/`
- **Related issues / PRs**: None

## Architectural Position

This slice builds directly on the harness upgrade from `007`. The prior slice established ontology layers, dependency-aware skills, and source-bootstrap metadata. This slice adds the first executable behavioral-capture loop so live demo evidence can be collected into durable repository-shaped artifacts instead of remaining an informal manual step.

The capture flow remains deliberately narrow:

- crawl configured same-origin demo routes,
- persist raw HTML plus normalized page-model JSON,
- emit capture summaries that later ontology-ingestion and pattern-merging steps can consume,
- expose enough report/query surface that operators can inspect results without opening every artifact manually.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Capture demo pages into durable artifacts (Priority: P1)

As a framework-analysis operator, I want the configured demo surface crawled into raw HTML and normalized page models so later pattern extraction has durable behavioral evidence.

**Independent Test**: Run the capture script against a small same-origin fixture site and confirm it writes HTML, page-model JSON, summary JSON, and a markdown report.

**Acceptance Scenarios**:

1. **Given** a manifest-backed behavioral source, **When** the capture script runs, **Then** same-origin demo pages are fetched until the configured page limit is reached.
2. **Given** a captured page, **When** artifacts are written, **Then** both raw HTML and a normalized page-model JSON document are persisted.

---

### User Story 2 - Normalize page structure and interactions (Priority: P1)

As a harness maintainer, I want captured pages normalized into page models with routes, headings, visible components, links, forms, and interaction hints so ontology extraction is not forced to parse raw HTML every time.

**Independent Test**: Inspect a captured page-model JSON file and confirm it includes route, title, headings, components, forms, and interaction-flow metadata.

**Acceptance Scenarios**:

1. **Given** a captured list or dashboard page, **When** the parser runs, **Then** headings, navigation links, and visible components are extracted.
2. **Given** a captured task or form page, **When** the parser runs, **Then** form actions, methods, input metadata, and form-submit interaction hints are extracted.

---

### User Story 3 - Inspect capture and graph state from CLI reports (Priority: P2)

As an operator, I want CLI-level reporting for graph layers and skill dependencies so I can review what the harness currently knows without reading raw YAML by hand.

**Independent Test**: Run the query script with report modes and confirm it returns ontology-layer and dependency summaries.

**Acceptance Scenarios**:

1. **Given** generated graph artifacts, **When** the query script is called with `--report layers`, **Then** ontology files and skills grouped by layer are returned.
2. **Given** dependency-aware skills, **When** the query script is called with `--report dependencies`, **Then** skill-to-skill dependency mappings are returned.

## Edge Cases

- What happens when a configured demo route returns non-HTML content?
- How should the capture loop behave when some pages fail while others succeed?
- How should query summaries represent layers or dependency groups with no current matches?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository MUST provide a behavioral capture script that reads the configured Viewflow-stack manifest and selects a named behavioral source.
- **FR-002**: The capture script MUST support same-origin crawling from configured seed paths and page limits.
- **FR-003**: The capture script MUST persist raw HTML, normalized page-model JSON, summary JSON, and a markdown report for each capture run.
- **FR-004**: Page-model normalization MUST extract route, title, headings, links, visible components, forms, and interaction hints when present.
- **FR-005**: The query script MUST provide summary reports for ontology layers and skill dependencies in addition to node filtering.
- **FR-006**: Documentation MUST describe how to run the bootstrap, capture, and report commands together.

### Non-Goals

- Deep browser automation or JavaScript execution for this slice.
- Automatic promotion of captured page models into ontology nodes or skills in this slice.
- Replacing the existing generated YAML artifacts with a separate database or service.

### Key Entities *(include if feature involves data)*

- **BehavioralCaptureRun**: One execution of the demo capture process for a named behavioral source.
- **BehavioralPageModel**: Normalized JSON describing the route, page structure, and interaction hints for one captured page.
- **GraphReport**: CLI-generated summary payload over ontology layers or skill dependencies.

## Success Criteria *(mandatory)*

- **SC-001**: Operators can bootstrap sources, run demo capture, and inspect capture or graph summaries with repository-native scripts.
- **SC-002**: Focused tests pass for capture behavior, manifest selection, source-bootstrap documentation, and graph report output.
- **SC-003**: The new capture/report tooling extends the existing harness instead of introducing a separate workflow surface.

## Delivery Mapping *(mandatory)*

- **Primary issue title**: Capture Viewflow demo behavior into page models and CLI reports
- **Planned branch label**: `feat/viewflow-demo-behavioral-capture`
- **Expected PR scope**: capture script + query/report enhancements + docs + tests
- **Blocking dependencies**: `007-behavioral-ontology-skill-graph`