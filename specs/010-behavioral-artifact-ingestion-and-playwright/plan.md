# Implementation Plan: Behavioral artifact ingestion and Playwright-backed capture

**Feature ID**: `010-behavioral-artifact-ingestion-and-playwright` | **Branch**: `feat/behavioral-artifact-ingestion-and-playwright` | **Date**: 2026-03-30 | **Spec**: `specs/010-behavioral-artifact-ingestion-and-playwright/spec.md`
**Input**: Feature specification from `/specs/010-behavioral-artifact-ingestion-and-playwright/spec.md`

## Summary

Finish the next harness follow-ups after `009`: import promoted behavioral artifacts into a tracked repository path, ingest them through the canonical knowledge-graph generator as low-confidence behavior-derived ontology and skills, and add an optional Playwright-backed browser capture mode that uses local runtime tooling without adding a permanent repo dependency.

## Technical Context

**Language/Version**: Python 3.13 plus optional local Node/Playwright runtime for capture  
**Primary Dependencies**: standard library, existing capture/generator/query scripts, local `node`/`npx` when Playwright mode is used  
**Storage**: `analysis/behavioral_patterns/` as tracked import input plus generated graph/skill artifacts  
**Testing**: focused `pytest` suites, `python .github/scripts/generate_knowledge_graph.py --check`, `python .github/scripts/spec_kit_workflow.py validate`  
**Constraints**: preserve the current capture flow, keep Playwright optional, do not replace the canonical generator with a new ingestion path

## Planned Validation

- `cd src && ../.venv/bin/python -m pytest tests/test_capture_behavioral_sources.py tests/test_configure_knowledge_sources.py tests/test_knowledge_graph_generator.py -q`
- `./.venv/bin/python .github/scripts/generate_knowledge_graph.py --check`
- `./.venv/bin/python .github/scripts/spec_kit_workflow.py validate specs/010-behavioral-artifact-ingestion-and-playwright`

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Tracked behavioral import directory | The canonical generator cannot ingest external captures unless they are imported into a stable repo surface | Reading arbitrary external paths during generation would make committed outputs non-reproducible |
| Optional Playwright runtime | Some demos need a real browser session and `page.content()` to capture reliable DOM state | Limiting the richer path to dump-dom commands would keep JS-heavy surfaces under-modeled |