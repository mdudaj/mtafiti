---

description: "Task list for Viewflow demo behavioral capture and ontology ingestion"
---

# Tasks: Viewflow demo behavioral capture and ontology ingestion

**Input**: Design documents from `/specs/008-viewflow-demo-behavioral-capture/`
**Prerequisites**: `spec.md` and `plan.md`

## Phase 1: Specification Alignment

- [ ] T001 Confirm `spec.md` matches the intended capture/report scope
- [ ] T002 Confirm `plan.md` captures crawler, reporting, docs, and validation work
- [ ] T003 Generate or refresh issue body with `python .github/scripts/spec_kit_workflow.py issue-body specs/008-viewflow-demo-behavioral-capture`

---

## Phase 2: Capture Implementation

- [ ] T010 Add a manifest-backed behavioral capture script in `.github/scripts/capture_behavioral_sources.py`
- [ ] T011 Normalize page captures into route/title/headings/components/forms/interaction page models
- [ ] T012 Write summary JSON and markdown report artifacts for each capture run

---

## Phase 3: Reporting and Documentation

- [ ] T020 Extend graph query/report tooling for ontology layers and skill dependencies
- [ ] T021 Document bootstrap, capture, and report commands in `README.md`
- [ ] T022 Keep the bootstrap guide aligned with the capture script entry point

---

## Phase 4: Validation

- [ ] T030 Add focused tests for capture behavior and manifest selection
- [ ] T031 Extend existing tests for bootstrap docs and graph report output
- [ ] T032 Run targeted test suites and record results

## Notes

- This slice captures durable behavioral evidence but does not yet promote captured page models directly into ontology or skill artifacts.
- Browser automation and JavaScript execution remain future work.