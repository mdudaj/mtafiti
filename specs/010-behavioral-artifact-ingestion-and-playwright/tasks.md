---

description: "Task list for behavioral artifact ingestion and Playwright-backed capture"
---

# Tasks: Behavioral artifact ingestion and Playwright-backed capture

**Input**: Design documents from `/specs/010-behavioral-artifact-ingestion-and-playwright/`
**Prerequisites**: `spec.md` and `plan.md`

## Phase 1: Scope Alignment

- [ ] T001 Confirm `spec.md` captures behavioral import, Playwright capture, and validation scope
- [ ] T002 Confirm `plan.md` reflects canonical generator ingestion and optional browser runtime handling
- [ ] T003 Generate or refresh the issue body with `python .github/scripts/spec_kit_workflow.py issue-body specs/010-behavioral-artifact-ingestion-and-playwright`

## Phase 2: Canonical Ingestion

- [ ] T010 Add tracked behavioral artifact import support in `.github/scripts/capture_behavioral_sources.py`
- [ ] T011 Ingest imported behavioral artifacts into `.github/scripts/knowledge_graph_lib.py`
- [ ] T012 Regenerate committed graph, ontology, and skill outputs from the updated canonical generator

## Phase 3: Browser Runtime Path

- [ ] T020 Add an optional Playwright-backed fetch mode to `.github/scripts/capture_behavioral_sources.py`
- [ ] T021 Document Playwright capture and repo import commands in `README.md` and the bootstrap guide

## Phase 4: Validation

- [ ] T030 Add focused tests for import behavior and behavioral graph ingestion
- [ ] T031 Run focused test suites and repository-safe packaging validation