---

description: "Task list for behavioral ontology and skill-graph harness upgrade"
---

# Tasks: Behavioral ontology and skill-graph harness upgrade

**Input**: Design documents from `/specs/007-behavioral-ontology-skill-graph/`
**Prerequisites**: `spec.md`, `plan.md`, `tasks.md`

## Phase 1: Spec and Workflow Alignment

- [ ] T001 Confirm `spec.md` reflects the agreed harness-upgrade scope
- [ ] T002 Confirm `plan.md` captures generator, source-bootstrap, and validation work
- [ ] T003 Generate or refresh issue body with `python .github/scripts/spec_kit_workflow.py issue-body specs/007-behavioral-ontology-skill-graph`
- [ ] T004 Mirror executable work into SQL todos and dependency tracking

---

## Phase 2: Foundational Work

- [ ] T005 Add layered ontology artifact generation in `.github/scripts/knowledge_graph_lib.py`
- [ ] T006 [P] Add skill graph metadata and dependency edges in `.github/scripts/knowledge_graph_lib.py`
- [ ] T007 [P] Add or update tests in `src/tests/test_knowledge_graph_generator.py`
- [ ] T008 [P] Update generated artifact documentation in `README.md`

**Checkpoint**: Generator emits richer graph outputs and test coverage exists

---

## Phase 3: User Story 1 - Model framework behavior in ontology layers (Priority: P1)

**Goal**: Emit reusable ontology artifacts for framework-learning layers

**Independent Test**: `python .github/scripts/generate_knowledge_graph.py --check`

- [ ] T010 [P] [US1] Implement ontology layer generation in `.github/scripts/knowledge_graph_lib.py`
- [ ] T011 [US1] Commit generated files under `ontology/`
- [ ] T012 [US1] Validate artifact drift and documentation alignment

---

## Phase 4: User Story 2 - Promote harness skills into a dependency-aware skill graph (Priority: P1)

**Goal**: Enrich generated skills with layer, dependency, and confidence metadata

**Independent Test**: `cd src && ../.venv/bin/python -m pytest tests/test_knowledge_graph_generator.py -q`

- [ ] T020 [P] [US2] Extend skill definitions and markdown rendering in `.github/scripts/knowledge_graph_lib.py`
- [ ] T021 [P] [US2] Regenerate `skills/generated_skills.yaml`, `.github/skills/*/SKILL.md`, and graph files
- [ ] T022 [US2] Add dependency-edge and metadata assertions in `src/tests/test_knowledge_graph_generator.py`

---

## Phase 5: User Story 3 - Bootstrap Viewflow-stack source acquisition (Priority: P2)

**Goal**: Make upstream source and demo acquisition reproducible for framework mining

**Independent Test**: `cd src && ../.venv/bin/python -m pytest tests/test_configure_knowledge_sources.py -q`

- [ ] T030 [P] [US3] Extend `.github/scripts/configure_knowledge_sources.py` with a Viewflow-stack bootstrap option
- [ ] T031 [P] [US3] Add manifest and guide assertions in `src/tests/test_configure_knowledge_sources.py`
- [ ] T032 [US3] Document the bootstrap workflow in `README.md`

---

## Phase N: Integration and PR Readiness

- [ ] T900 Re-run targeted validation and required merge-gate checks
- [ ] T901 Generate or refresh PR body with `python .github/scripts/spec_kit_workflow.py pr-body specs/007-behavioral-ontology-skill-graph`
- [ ] T902 Update issue checklist, risk notes, and done/blocker state

## Notes

- This slice upgrades the existing harness rather than introducing a second workflow engine.
- Live demo crawling remains out of scope here; the bootstrap workflow prepares sources and operator guidance for that later slice.