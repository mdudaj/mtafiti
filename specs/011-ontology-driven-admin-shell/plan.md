# Implementation Plan: Ontology-driven admin application shell

**Feature ID**: `011-ontology-driven-admin-shell` | **Branch**: `feat/ontology-driven-admin-shell` | **Date**: 2026-03-31 | **Spec**: `specs/011-ontology-driven-admin-shell/spec.md`
**Input**: User description defining a django-material-based admin shell with ontology-driven navigation, workflow-aware rendering, permission-aware actions, optional FAB or speed dial, and controlled extension or override rules.

## Summary

Define a django-material-first admin application shell for server-rendered Mtafiti UI surfaces. This slice formalizes the base layout contract, ontology-driven menu rendering, supported page-type wrappers, permission-aware and state-aware contextual actions, and a reusable FAB or speed-dial component. It also defines a strict reuse, extend, and override policy so future UI work stays framework-aligned instead of drifting into ad hoc template forks.

## Technical Context

**Language/Version**: Python 3.13, Django server-rendered templates, Materialize-compatible JavaScript  
**Primary Dependencies**: Django, django-material, Viewflow workflow runtime conventions, existing role and tenant policy enforcement  
**Storage**: Django templates, Python view metadata, ontology-backed navigation or component metadata, repository documentation  
**Testing**: `spec_kit_workflow.py validate`, focused UI-contract or template tests to be defined in implementation issues, repository merge gate before integration  
**Target Platform**: server-rendered admin-style workflow UI inside the existing Django runtime  
**Project Type**: spec-first workflow/UI architecture slice  
**Constraints**: preserve django-material compatibility, preserve Materialize JS behavior, avoid SPA drift, keep ontology as the navigation and action source of truth, keep overrides isolated  
**Scale/Scope**: specification and issue slicing only, not full shell implementation in this bundle

## Constitution Check

- [x] The slice stays inside the current Django plus Viewflow plus django-material architecture.
- [x] The slice defines clear boundaries between reuse, extension, and override instead of defaulting to custom UI code.
- [x] The slice preserves tenant-scoped and role-scoped behavior as first-class UI constraints.
- [x] The slice keeps workflow state integration and permission filtering aligned with server-side enforcement.
- [x] The slice remains implementation-facing without prematurely committing to a SPA or a full layout rewrite.

## Research & Repository Evidence

### Current repository evidence

- `docs/workflow-ui.md` already establishes Viewflow as the workflow engine, django-material as the preferred server-rendered UI stack, and role-based visibility as a core contract.
- Existing `/api/v1/ui/operations/*` endpoints already provide UI-oriented payloads that a future shell can consume.
- The generated skills `plan_viewflow_material_workflow_ui` and `compose_operations_dashboard_contract` reinforce the current target layer and framework direction.
- The layered ontology work under `ontology/` creates a natural repository surface for UI, navigation, workflow, state, and permission concepts.

### Gaps this slice must close

- no first-class application-shell contract currently governs CRUD, dashboard, and workflow-task surfaces together
- no explicit ontology-driven navigation model exists for server-rendered shell composition
- no reusable FAB or speed-dial contract exists for contextual workflow or CRUD actions
- no strict repository-level decision policy currently tells implementers when to reuse, extend, or override django-material layout behavior

## Proposed Design Direction

### 1. Shell-first baseline

- define `ApplicationShell` around django-material layout primitives
- make `material/layout/base.html` the default inheritance target
- define isolated fallback rules for a custom layout only when extension is insufficient

### 2. Ontology-driven navigation

- define a `NavigationItem` metadata contract with label, icon, route or `workflow_key` binding, permission, and optional state constraints
- render menu content dynamically from metadata rather than static sidebar markup
- preserve Materialize-compatible classes and interaction patterns when custom rendering is needed
- make one server-side shell metadata registry the first canonical source for navigation and contextual action descriptors

### 3. Shared content-area contract

- define a common wrapper for dashboard, list, detail, form, and workflow-task views
- allow page-local cards, workflow panels, and action strips inside the shared shell contract
- keep shell structure separate from view-specific business content and data loading responsibilities

### 4. Reusable FAB and contextual action model

- define a reusable FAB or speed-dial component fed by contextual action metadata
- support URL navigation and canonical workflow-start behavior through `workflow_key`
- require deny-by-default permission-aware and state-aware filtering before render
- preserve Materialize initialization and tooltip behavior

### 5. Controlled extension and override policy

- define when block override, CSS augmentation, JS hooks, and partial injection are sufficient
- define isolated override scenarios for dynamic layout or workflow-state-driven shell changes
- make override reviewable and auditable instead of allowing informal template forks

## Reviewable Slices

1. **Base shell contract**
   - define default layout inheritance, content blocks, and isolated override boundaries

2. **Navigation model**
   - define ontology-driven menu metadata and rendering rules

3. **View-type content contract**
   - define supported page wrappers and extension slots for dashboard and workflow content

4. **FAB component contract**
   - define contextual action metadata, filtering, and workflow routing behavior

5. **Extension and override governance**
   - define repository-safe rules for block-level extension, shell augmentation, and isolated layout replacement

## Resolved Design Decisions

- the first canonical metadata source is one server-side shell metadata registry owned by the shell layer; persisted navigation models are out of scope for this slice
- workflow-start actions use `workflow_key` and resolve server-side to `/workflow/start/<workflow_key>/`
- shell filtering is deny-by-default for permission, tenant, workflow-resolution, and state constraints
- shell structure and slots are owned by the shell layer, while page implementations own data loading and domain-specific empty or error states
- FAB actions are resolved through the same descriptor pipeline as navigation items and can fall back to a shared non-floating action slot when responsive collision would occur

## Implementation Readiness Anchors

The first implementation issues should prove the contract on three concrete surfaces:

1. an operations-style dashboard landing surface
2. one CRUD list or detail surface
3. one workflow-start or workflow-task surface

These anchors keep the first issues concrete and prevent the shell contract from drifting into abstract template work with no proving pages.

## Initial Issue Split

The first GitHub issue set should use one parent issue plus three implementation issues:

1. **Parent spec issue**
   - captures the shell contract, dependencies, and acceptance criteria

2. **Shell contract issue**
   - implement layout inheritance, slot ownership, and proving-surface shell adoption

3. **Navigation resolution issue**
   - implement canonical shell metadata ownership and navigation resolution

4. **FAB and shared action-slot issue**
   - implement FAB derivation, workflow-aware action behavior, and responsive fallback rules

This split keeps layout structure, descriptor ownership, and contextual action behavior reviewable as separate implementation units.

## Delivery Mapping

- **Issue title**: Define ontology-driven admin application shell on django-material
- **Issue generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py issue-body specs/011-ontology-driven-admin-shell`
- **PR generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py pr-body specs/011-ontology-driven-admin-shell`
- **Branch naming**: `feat/ontology-driven-admin-shell`

## Planned Validation

- `./.venv/bin/python .github/scripts/spec_kit_workflow.py validate specs/011-ontology-driven-admin-shell`
- confirm issue-body and PR-body generation from the bundle before implementation begins
- confirm the issue body carries the resolved design decisions rather than generic acceptance text
- future implementation issues should add focused template, view, and permission-filtering validation plus the repository full gate

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Explicit override path alongside reuse-first policy | Ontology-driven rendering may eventually need structural shell changes | Pretending extension always suffices would produce hidden template forks later |
| Ontology-driven navigation instead of static sidebars | The user explicitly wants metadata-backed navigation and action rendering | Static template menus would violate the source-of-truth constraint |