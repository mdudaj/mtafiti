# Implementation Plan: [FEATURE]

**Feature ID**: `[###-feature-name]` | **Branch**: `[type/slug-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

## Summary

[Primary requirement, intended outcome, and implementation approach]

## Technical Context

**Language/Version**: [e.g. Python 3.12]  
**Primary Dependencies**: [e.g. Django, Viewflow, Celery]  
**Storage**: [e.g. PostgreSQL, N/A]  
**Testing**: [e.g. pytest, manage.py check, local_fast_feedback]  
**Target Platform**: [e.g. Linux server, tenant-aware Django app]  
**Project Type**: [e.g. multi-tenant web platform]  
**Performance Goals**: [domain-specific goals or N/A]  
**Constraints**: [tenant safety, routing, UX, compliance, etc.]  
**Scale/Scope**: [expected blast radius]

## Constitution Check

- [ ] Specifications remain the source of truth for the slice.
- [ ] Tenant and service routing impacts are identified.
- [ ] Knowledge graph / skill / Context Hub inputs are captured where needed.
- [ ] Validation commands and merge gates are defined.
- [ ] Issue, branch, and PR mapping are consistent with the spec.

## Research & Knowledge Inputs

### Repository Evidence

- [docs, code paths, checkpoints, or prior PRs]

### Knowledge Graph / Skills

- [relevant nodes, generated skills, or framework knowledge files]

### Context Hub Lookups

- [e.g. `chub get django/forms`, or `Not required`]

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### Source Code (repository root)

```text
[List the concrete repository paths touched by this feature]
```

## Delivery Mapping

- **Issue title**: [planned GitHub issue title]
- **Issue generation command**: `python .github/scripts/spec_kit_workflow.py issue-body specs/[###-feature-name]`
- **PR generation command**: `python .github/scripts/spec_kit_workflow.py pr-body specs/[###-feature-name]`
- **Branch naming**: [e.g. `feat/spec-kit-workflow`]
- **Execution slices**: [one issue or multiple issue-sized slices]
- **Dependencies**: [Depends on / Blocks / None]

## Planned Validation

- `python .github/scripts/spec_kit_workflow.py validate specs/[###-feature-name]`
- [targeted validation commands]
- `.github/scripts/local_fast_feedback.sh --full-gate`

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g. cross-service edit] | [reason] | [why smaller scope was insufficient] |
