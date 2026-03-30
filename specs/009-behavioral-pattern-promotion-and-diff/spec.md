# Feature Specification: Behavioral pattern promotion, browser capture, and run diffing

**Feature ID**: `009-behavioral-pattern-promotion-and-diff`  
**Execution Branch**: `feat/behavioral-pattern-promotion-and-diff`  
**Created**: 2026-03-28  
**Status**: Draft  
**Input**: User description: "Promote captured page models into reusable pattern artifacts, support browser-rendered DOM capture when direct HTTP is insufficient, and diff successive demo capture runs."

## Repository Context *(mandatory)*

- **Service area**: framework-analysis harness, behavioral capture workflow, promoted pattern artifacts
- **Affected code paths**: `.github/scripts/capture_behavioral_sources.py`, `.github/scripts/configure_knowledge_sources.py`, `README.md`, `src/tests/`
- **Related design docs**: `specs/008-viewflow-demo-behavioral-capture/spec.md`, `specs/007-behavioral-ontology-skill-graph/spec.md`, `docs/self-reflective-implementation.md`
- **Knowledge graph / skills evidence**: `ontology/*.yaml`, `skills/generated_skills.yaml`, `.github/skills/*/SKILL.md`
- **External API lookup needs**: configured behavioral sources and optional external headless browser commands
- **Related issues / PRs**: None

## Architectural Position

This slice extends the behavioral capture foundation from `008` without replacing it. The existing capture loop already persists raw HTML and normalized page models. This slice adds three missing review and promotion capabilities:

- timestamped capture runs so evidence is durable across time,
- promoted pattern and ontology-candidate artifacts derived from captured page models,
- optional browser-rendered capture and diff tooling for pages where plain HTTP fetches or one-off reviews are insufficient.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Promote captured pages into reusable patterns (Priority: P1)

As a harness maintainer, I want each capture run to emit promoted pattern artifacts so page models become reusable inputs for ontology and skill work instead of staying as raw crawl output only.

**Independent Test**: Run capture against a small fixture and confirm `patterns.json`, `patterns.md`, and `ontology-candidates.json` are written.

**Acceptance Scenarios**:

1. **Given** captured page models, **When** promotion runs, **Then** each page is classified into a reusable layout or interaction pattern.
2. **Given** promoted patterns, **When** ontology candidates are written, **Then** UI, navigation, workflow, state, permission, or cross-layer hints are grouped into explicit artifact families.

---

### User Story 2 - Capture rendered DOM through a browser-backed mode (Priority: P1)

As an operator, I want an optional browser-backed capture mode so demos that rely on client-side rendering can still produce usable page models.

**Independent Test**: Invoke browser-mode fetching with a stubbed external command and confirm HTML is captured successfully.

**Acceptance Scenarios**:

1. **Given** browser mode is requested and a working dump command is available, **When** a page is fetched, **Then** rendered DOM is captured and normalized like the HTTP path.
2. **Given** browser mode is requested without an available command, **When** capture starts, **Then** the operator receives a clear configuration error instead of silent fallback.

---

### User Story 3 - Diff stored capture runs (Priority: P2)

As an operator, I want successive capture runs diffed so UI or workflow changes are easy to inspect over time.

**Independent Test**: Compare two synthetic runs and confirm added routes plus changed components or interaction types are reported.

**Acceptance Scenarios**:

1. **Given** two stored runs for the same source, **When** diffing is requested, **Then** added and removed routes are reported.
2. **Given** the same route exists in both runs, **When** page structure or interaction hints differ, **Then** the diff artifact records those changes.

## Edge Cases

- How should promotion behave when a run captures zero pages successfully?
- How should browser capture be configured when several possible headless browsers are installed?
- How should diffs treat title-only changes versus structural component or interaction changes?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each capture run MUST be stored under a stable run-specific directory instead of overwriting prior evidence.
- **FR-002**: The capture workflow MUST continue to write latest-summary artifacts for quick inspection while preserving run history.
- **FR-003**: The capture workflow MUST promote page models into pattern and ontology-candidate artifacts automatically after a successful run.
- **FR-004**: The capture workflow MUST support an optional browser-backed fetch mode using configurable external dump commands.
- **FR-005**: The repository MUST provide a diff mode that compares two stored runs for the same behavioral source and emits machine-readable plus markdown reports.
- **FR-006**: Documentation and bootstrap metadata MUST describe the browser-backed mode and run-diff workflow.

### Non-Goals

- Full browser automation or authenticated workflows in this slice.
- Automatic promotion of pattern artifacts into the committed repository ontology or skill graph in this slice.
- Long-term storage outside the source-root `.mtafiti` workspace.

### Key Entities *(include if feature involves data)*

- **BehavioralCaptureRun**: One timestamped capture execution stored under a run-specific directory.
- **PromotedPatternArtifact**: Derived artifact summarizing layout, interaction, or navigation patterns from captured page models.
- **BehavioralCaptureDiff**: Structured comparison of two capture runs for the same source.

## Success Criteria *(mandatory)*

- **SC-001**: Operators can preserve multiple capture runs and compare them without manual file inspection.
- **SC-002**: Promoted pattern artifacts are emitted automatically from successful captures.
- **SC-003**: Focused tests pass for pattern promotion, browser-backed fetching, and run diffs.

## Delivery Mapping *(mandatory)*

- **Primary issue title**: Promote behavioral captures into patterns and diff run history
- **Planned branch label**: `feat/behavioral-pattern-promotion-and-diff`
- **Expected PR scope**: capture workflow extensions + docs + tests
- **Blocking dependencies**: `008-viewflow-demo-behavioral-capture`