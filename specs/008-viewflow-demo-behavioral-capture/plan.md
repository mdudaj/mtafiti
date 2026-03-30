# Implementation Plan: Viewflow demo behavioral capture and ontology ingestion

**Feature ID**: `008-viewflow-demo-behavioral-capture` | **Branch**: `feat/viewflow-demo-behavioral-capture` | **Date**: 2026-03-28 | **Spec**: `specs/008-viewflow-demo-behavioral-capture/spec.md`
**Input**: Feature specification from `/specs/008-viewflow-demo-behavioral-capture/spec.md`

## Summary

Add the first executable behavioral-capture loop on top of the harness upgrade from `007`. The implementation introduces a repository-native crawler for configured same-origin demo sources, writes raw HTML and normalized page models under `.mtafiti/behavioral-captures/`, and extends the existing graph query surface with report modes for ontology layers and skill dependencies.

## Technical Context

**Language/Version**: Python 3.13  
**Primary Dependencies**: standard library only, existing manifest/bootstrap tooling, existing graph generator/query helpers  
**Storage**: manifest-backed capture artifacts under `.mtafiti/behavioral-captures/` plus committed code/tests/docs  
**Testing**: `pytest`, `python .github/scripts/query_knowledge_graph.py --report layers`, `python .github/scripts/query_knowledge_graph.py --report dependencies`  
**Target Platform**: Linux development environment, repository-local tooling  
**Project Type**: spec-first harness tooling slice  
**Performance Goals**: keep capture bounded through same-origin and page-limit controls; keep report generation local and fast  
**Constraints**: no headless browser requirement, no live network dependency in tests, preserve the existing harness structure  
**Scale/Scope**: one CLI capture tool plus reporting and documentation

## Constitution Check

- [x] Specifications remain the source of truth for the slice.
- [x] No tenant/runtime service routing changes are introduced.
- [x] The work extends existing harness scripts rather than adding a disconnected subsystem.
- [x] Validation is explicit and bounded.

## Research & Knowledge Inputs

### Repository Evidence

- `specs/007-behavioral-ontology-skill-graph/spec.md` defined source bootstrap and graph/report foundations.
- `.github/scripts/configure_knowledge_sources.py` already owns the Viewflow stack manifest.
- `.github/scripts/query_knowledge_graph.py` and `.github/scripts/knowledge_graph_lib.py` already expose local graph queries.

### Knowledge Graph / Skills

- `ontology/*.yaml`
- `skills/generated_skills.yaml`
- `.github/skills/*/SKILL.md`

## Project Structure

```text
.github/scripts/capture_behavioral_sources.py
.github/scripts/query_knowledge_graph.py
.github/scripts/knowledge_graph_lib.py
src/tests/test_capture_behavioral_sources.py
src/tests/test_knowledge_graph_generator.py
src/tests/test_configure_knowledge_sources.py
README.md
specs/008-viewflow-demo-behavioral-capture/
```

## Delivery Mapping

- **Issue title**: Capture Viewflow demo behavior into page models and CLI reports
- **Issue generation command**: `python .github/scripts/spec_kit_workflow.py issue-body specs/008-viewflow-demo-behavioral-capture`
- **PR generation command**: `python .github/scripts/spec_kit_workflow.py pr-body specs/008-viewflow-demo-behavioral-capture`
- **Branch naming**: `feat/viewflow-demo-behavioral-capture`

## Planned Validation

- `cd src && ../.venv/bin/python -m pytest tests/test_capture_behavioral_sources.py -q`
- `cd src && ../.venv/bin/python -m pytest tests/test_configure_knowledge_sources.py -q`
- `cd src && ../.venv/bin/python -m pytest tests/test_knowledge_graph_generator.py -q`
- `python .github/scripts/query_knowledge_graph.py --report layers`
- `python .github/scripts/query_knowledge_graph.py --report dependencies`

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Add a dedicated capture script | Live demo evidence needs an executable entry point instead of README-only instructions | Folding crawling into the source-bootstrap script would conflate setup and evidence collection |
| Add CLI graph reports | Operators need fast inspection of ontology and dependency state | Reading raw YAML for every review loop is too manual and error-prone |