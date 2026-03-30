# Implementation Plan: Behavioral ontology and skill-graph harness upgrade

**Feature ID**: `007-behavioral-ontology-skill-graph` | **Branch**: `feat/behavioral-ontology-skill-graph` | **Date**: 2026-03-28 | **Spec**: `specs/007-behavioral-ontology-skill-graph/spec.md`
**Input**: Feature specification from `/specs/007-behavioral-ontology-skill-graph/spec.md`

## Summary

Upgrade the current agentic harness so it can support behavior-first framework mining for the Viewflow stack. The implementation keeps the current right-target and phase-gated execution controls, but extends the knowledge-graph generator with layered ontology outputs and a richer skill graph, then adds a source-bootstrap path for the required repositories and demo-site evidence.

## Technical Context

**Language/Version**: Python 3.13  
**Primary Dependencies**: standard library, existing knowledge-graph generator, existing Context Hub source-generation workflow  
**Storage**: committed YAML and markdown artifacts  
**Testing**: `pytest`, `python .github/scripts/spec_kit_workflow.py validate`, `python .github/scripts/generate_knowledge_graph.py --check`  
**Target Platform**: Linux development environment, repository-local harness tooling  
**Project Type**: spec-first repository tooling upgrade  
**Performance Goals**: preserve fast local generation for committed artifacts while adding ontology layers and richer skill metadata  
**Constraints**: keep diffs surgical, preserve current bundle generation semantics, do not require live network access during tests  
**Scale/Scope**: one tooling slice plus harness documentation and committed generated outputs

## Constitution Check

- [x] Specifications remain the source of truth for the slice.
- [x] Tenant and service routing impacts are identified as none for runtime behavior.
- [x] Knowledge graph / skill / Context Hub inputs are captured where needed.
- [x] Validation commands and merge gates are defined.
- [x] Issue, branch, and PR mapping are consistent with the spec.

## Research & Knowledge Inputs

### Repository Evidence

- `docs/self-reflective-implementation.md` defines the current harness execution model.
- `templates/agentic-workflow/` contains the portable harness contracts that were already upgraded at the documentation layer.
- `.github/scripts/knowledge_graph_lib.py` is the canonical generator for committed graph and skill artifacts.
- `.github/scripts/configure_knowledge_sources.py` already knows how to translate cloned repositories into Context Hub content and is the correct extension point for framework-source bootstrap.

### Knowledge Graph / Skills

- `skills/generated_skills.yaml`
- `.github/skills/*/SKILL.md`
- `framework_knowledge/viewflow.yaml`
- `framework_knowledge/django_material.yaml`

### Context Hub Lookups

- Not required for this implementation slice

## Project Structure

### Documentation (this feature)

```text
specs/007-behavioral-ontology-skill-graph/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code (repository root)

```text
.github/scripts/knowledge_graph_lib.py
.github/scripts/configure_knowledge_sources.py
src/tests/test_knowledge_graph_generator.py
src/tests/test_configure_knowledge_sources.py
README.md
analysis/environment_inventory.yaml
knowledge_graph/{ontology,nodes,edges}.yaml
ontology/*.yaml
skills/generated_skills.yaml
.github/skills/*/SKILL.md
```

## Delivery Mapping

- **Issue title**: Upgrade agentic harness for behavioral ontology and skill graph extraction
- **Issue generation command**: `python .github/scripts/spec_kit_workflow.py issue-body specs/007-behavioral-ontology-skill-graph`
- **PR generation command**: `python .github/scripts/spec_kit_workflow.py pr-body specs/007-behavioral-ontology-skill-graph`
- **Branch naming**: `feat/behavioral-ontology-skill-graph`
- **Execution slices**: one issue-sized tooling slice
- **Dependencies**: None

## Planned Validation

- `python .github/scripts/spec_kit_workflow.py validate specs/007-behavioral-ontology-skill-graph`
- `python .github/scripts/generate_knowledge_graph.py --check`
- `cd src && ../.venv/bin/python -m pytest tests/test_knowledge_graph_generator.py -q`
- `cd src && ../.venv/bin/python -m pytest tests/test_configure_knowledge_sources.py -q`

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Generator emits additional committed artifacts | Layered ontology and richer skill metadata must live in the same committed harness outputs | Keeping them only in docs would not make the harness executable or queryable |
| Source-bootstrap metadata in tooling rather than README only | Operators need reproducible acquisition inputs for the Viewflow stack | README-only instructions would remain easy to drift and hard to test |