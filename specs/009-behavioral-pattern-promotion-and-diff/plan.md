# Implementation Plan: Behavioral pattern promotion, browser capture, and run diffing

**Feature ID**: `009-behavioral-pattern-promotion-and-diff` | **Branch**: `feat/behavioral-pattern-promotion-and-diff` | **Date**: 2026-03-28 | **Spec**: `specs/009-behavioral-pattern-promotion-and-diff/spec.md`
**Input**: Feature specification from `/specs/009-behavioral-pattern-promotion-and-diff/spec.md`

## Summary

Extend the behavioral capture workflow from `008` so captures are durable across time, page models are promoted into reusable pattern artifacts, and operators can choose either direct HTTP or browser-rendered DOM capture depending on the demo surface. Add run diffing to make changes between captures reviewable.

## Technical Context

**Language/Version**: Python 3.13  
**Primary Dependencies**: standard library only, existing behavioral capture workflow  
**Storage**: `.mtafiti/behavioral-captures/<source>/runs/<run>/...` plus latest summary artifacts  
**Testing**: `pytest` targeted suites for capture, bootstrap metadata, and graph generator behavior  
**Target Platform**: Linux development environment, repository-local harness tooling  
**Project Type**: spec-first tooling slice  
**Constraints**: no mandatory new runtime dependencies; browser mode must stay optional; preserve current HTTP capture path  
**Scale/Scope**: capture script enhancement plus docs and tests

## Constitution Check

- [x] The work extends existing tooling rather than creating a parallel harness.
- [x] Validation is explicit and repository-local.
- [x] No tenant or runtime service behavior is changed.

## Project Structure

```text
.github/scripts/capture_behavioral_sources.py
.github/scripts/configure_knowledge_sources.py
README.md
src/tests/test_capture_behavioral_sources.py
src/tests/test_configure_knowledge_sources.py
specs/009-behavioral-pattern-promotion-and-diff/
```

## Planned Validation

- `cd src && ../.venv/bin/python -m pytest tests/test_capture_behavioral_sources.py -q`
- `cd src && ../.venv/bin/python -m pytest tests/test_configure_knowledge_sources.py -q`

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Persist run history under dedicated directories | Operators need stable evidence snapshots for later review and diffing | Overwriting one latest capture destroys the comparison path |
| Optional browser-backed fetch mode | Some demo pages may need rendered DOM rather than raw HTTP output | Forcing a mandatory browser dependency would make the tooling heavier and less portable |