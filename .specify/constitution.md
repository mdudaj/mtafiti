# Mtafiti Constitution

## Core Principles

### I. Specifications Are the Source of Truth
All substantial delivery work MUST begin with `spec-kit` artifacts under `specs/<feature>/`.
The committed specification, implementation plan, and task list define the intended behavior, scope boundaries, and acceptance checks.
GitHub issues, branches, PR descriptions, SQL todos, and implementation notes MUST derive from those artifacts instead of becoming competing sources of truth.

### II. Tenant-Safe, Service-Aware Design
Every change MUST preserve schema-per-tenant isolation, service-aware routing, and explicit tenant context propagation.
Specifications and plans MUST call out tenant boundaries, service host impacts, and any migration or background-task implications before implementation starts.

### III. Knowledge-Backed Engineering
Specifications and plans MUST cite relevant repository design docs, knowledge-graph artifacts, local skills, and Context Hub lookups for external APIs when they materially affect implementation quality.
Agents should prefer verified repository knowledge and retrieved framework documentation over assumptions.

### IV. End-to-End Verification Is Mandatory
No work item is complete until the declared acceptance criteria, targeted validation, and repository merge gates pass.
Plans MUST name the concrete validation commands, and tasks MUST preserve an implement -> verify -> fix -> re-verify flow before PR creation.

### V. Traceable GitHub Delivery
Each execution slice MUST map cleanly from spec -> plan -> tasks -> issue -> branch -> PR -> squash merge.
Branch names MUST remain Git-safe Conventional Commit slugs such as `feat/lims-permissions`, even when a spec directory uses a numeric `spec-kit` feature identifier.

## Platform Constraints

- Primary stack: Django, django-tenants, Celery, PostgreSQL, RabbitMQ, Viewflow, django-material.
- Service boundaries and tenant routing MUST remain aligned with `TenantServiceRoute` and shared host conventions.
- Knowledge graph artifacts under `analysis/`, `knowledge_graph/`, `skills/`, and `framework_knowledge/` are deterministic repository outputs and MUST be refreshed when affected.
- External API usage SHOULD be grounded in Context Hub lookups when the repository does not already contain authoritative usage patterns.

## Development Workflow

1. Ratify or update this constitution when project rules change.
2. Create or refine `specs/<feature>/spec.md` with `/speckit.specify`.
3. Produce `plan.md` plus supporting design artifacts with `/speckit.plan`.
4. Produce `tasks.md` with `/speckit.tasks`.
5. Generate or refresh GitHub issue and PR bodies from the spec bundle using `.github/scripts/spec_kit_workflow.py`.
6. Mirror executable work into SQL todos and issue tracking.
7. Implement on a scoped branch, validate, open a PR, and squash merge after review.

## Governance

This constitution supersedes older ad hoc workflow notes when conflicts arise.
Amendments MUST be reviewed in Git, explain the reason for change, and update dependent workflow docs or templates in the same PR.

**Version**: 1.0.0 | **Ratified**: 2026-03-19 | **Last Amended**: 2026-03-19
