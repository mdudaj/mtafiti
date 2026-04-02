# Implementation Plan: Ontology-driven operational pages

**Feature ID**: `012-ontology-driven-operation-pages` | **Branch**: `feat/ontology-driven-operation-pages` | **Date**: 2026-03-31 | **Spec**: `specs/012-ontology-driven-operation-pages/spec.md`
**Input**: User description defining operation pages where action cards are the primary interaction surface, bind to views or workflows, support ordering and filtering, integrate with the sidebar and optional FAB, and remain ontology-driven.

## Summary

Define a reusable operational page pattern that sits on top of the `011` shell and uses action cards as the primary interaction surface. This slice formalizes the `OperationPage` and `ActionCard` descriptor contracts, deterministic filtering and ordering, route and workflow resolution, optional FAB derivation, and bounded layout rules so operational pages remain consistent across different domains.

## Technical Context

**Language/Version**: Python 3.13, Django templates, Materialize-compatible JavaScript  
**Primary Dependencies**: `011-ontology-driven-admin-shell`, Django, django-material, Viewflow conventions, existing `/api/v1/ui/operations/*` payload builders  
**Storage**: server-side descriptor registries or UI payloads, Django template partials, repository documentation  
**Testing**: `spec_kit_workflow.py validate`, future focused resolver/template tests, role and tenant visibility tests, repository merge gate  
**Target Platform**: server-rendered operational entry pages inside the existing Django runtime  
**Project Type**: spec-first page-pattern architecture slice  
**Constraints**: must depend on `011`, preserve server-side authorization, keep workflow resolution server-side, keep the page bounded and action-oriented, avoid overloaded dashboards  
**Scale/Scope**: specification and issue slicing only, not implementation in this bundle

## Constitution Check

- [x] The slice stays inside the Django plus Viewflow plus django-material runtime.
- [x] The slice extends `011` instead of competing with it.
- [x] The slice keeps tenant and role filtering server-driven.
- [x] The slice preserves a bounded, reusable page contract rather than a bespoke page family.
- [x] The slice remains implementation-facing without committing to client-heavy behavior.

## Research & Repository Evidence

### Current repository evidence

- `docs/workflow-ui.md` already defines operational UI endpoints, role-based visibility, and server-rendered django-material direction.
- current templates under `src/core/templates/core/ui/` show operational dashboards, monitors, and reusable shell includes that operation pages should align with rather than replace.
- `011-ontology-driven-admin-shell` already defines the governing shell contract for navigation, workflow binding, and optional FAB behavior.

### Gaps this slice must close

- no explicit `OperationPage` descriptor currently defines action-card-first operational entry surfaces
- no canonical `ActionCard` descriptor currently binds route-backed and workflow-backed actions consistently
- ordering, state filtering, and FAB derivation are not yet constrained enough for repeatable implementation
- current operational templates emphasize panels and monitors, but not a reusable bounded action-card launcher surface

## Proposed Design Direction

### 1. Make operation pages a shell extension, not a shell variant

- inherit `011` layout and workflow binding rules
- keep navigation entry handled by the shell and action entry handled by cards
- preserve shell ownership of structure and page ownership of action-set context

### 2. Define one canonical action-card descriptor

- require stable `id`, short action-oriented title, one-sentence description, Material icon, and exactly one route or workflow binding
- keep workflow binding on `workflow_key`
- keep `resolved_url` as a computed output, not the authored source of truth

### 3. Fix the resolver and ordering behavior

- resolve candidate actions from a canonical source
- bind tenant, role, workflow state, and data availability
- exclude unresolved or disallowed actions before render
- sort sequenced cards first and preserve deterministic order for the rest

### 4. Keep FAB subordinate to cards

- allow one optional primary action emphasis
- ensure FAB is only a secondary rendering of an allowed card action, never a separate authority
- allow suppression when it would visually compete with the page

### 5. Bound page density and scope

- keep pages focused on one operational domain or related procedure family
- cap one grid at 8 cards
- force split or staged layouts when the operation set becomes too broad

## Reviewable Slices

1. **OperationPage contract**
   - define page identity, page scope, and relation to `011`

2. **ActionCard descriptor**
   - define authored fields, computed fields, and route/workflow exclusivity

3. **Filtering and ordering pipeline**
   - define deterministic resolver behavior and deny-by-default exclusions

4. **Reusable rendering contract**
   - define card-grid layout, component rules, and click behavior

5. **FAB and proving-surface rules**
   - define optional primary-action emphasis and first implementation anchors

## Resolved Design Decisions

- this work is a new feature bundle that depends on `011`, not an expansion of `011` issue scope
- `ActionCard` is the canonical operational entry descriptor for this slice
- `workflow_key` remains the only workflow binding field; raw `workflow` names are out of scope
- operation pages use one deterministic resolver pipeline with deny-by-default exclusions
- FAB can only mirror one allowed card action and cannot introduce an independent action authority
- one ungrouped operation page grid cannot exceed 8 cards

## Implementation Readiness Anchors

The first implementation issues should prove the pattern on:

1. one route-heavy operational intake page
2. one mixed route-and-workflow page
3. one state-sensitive page whose visible cards change by current context

These anchors force the implementation to prove route resolution, workflow resolution, and filtering behavior across distinct page types.

## Initial Issue Split

The first GitHub issue set should use one parent issue plus three implementation issues:

1. **Parent spec issue**
   - captures the page-pattern contract, dependencies on `011`, and acceptance criteria

2. **Descriptor resolution issue**
   - implement `OperationPage` and `ActionCard` descriptor ownership
   - implement route and workflow resolution
   - implement permission, state, and data-availability filtering
   - implement deterministic ordering

3. **Reusable rendering issue**
   - implement the reusable action-card component
   - implement the bounded card-grid layout contract
   - implement full-card click behavior and styling constraints
   - implement empty-state and accessibility-aligned rendering behavior

4. **Proving surfaces and FAB issue**
   - implement one route-heavy page, one mixed route-and-workflow page, and one state-sensitive page
   - implement optional FAB derivation from the same allowed card set
   - verify that FAB suppression does not change the authoritative card set

This split keeps resolver logic, reusable UI rendering, and concrete page adoption reviewable as separate changes.

## Delivery Mapping

- **Issue title**: Define ontology-driven operational pages with reusable action cards
- **Implementation issue 1**: Implement operation-page descriptor resolution and deterministic action filtering
- **Implementation issue 2**: Implement reusable action-card component and bounded card-grid rendering
- **Implementation issue 3**: Implement proving operation pages and FAB derivation from allowed actions
- **Issue generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py issue-body specs/012-ontology-driven-operation-pages`
- **PR generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py pr-body specs/012-ontology-driven-operation-pages`
- **Branch naming**: `feat/ontology-driven-operation-pages`

## Planned Validation

- `./.venv/bin/python .github/scripts/spec_kit_workflow.py validate specs/012-ontology-driven-operation-pages`
- confirm issue-body and PR-body generation from the bundle before creating GitHub issues
- confirm generated issue output carries the page-pattern and action-card decisions rather than generic acceptance text
- future implementation issues should add resolver, template, and role/state visibility validation

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Separate operational-page bundle on top of `011` | The page pattern has enough unique behavior to require its own issue set | Folding all details into `011` would blur shell and page-pattern responsibilities |
| Explicit 8-card cap | Operational pages need a hard bound to avoid becoming generic dashboards | A soft recommendation would allow overloaded launcher pages |
| FAB subordinate to cards | The page needs one source of truth for allowed actions | Independent FAB definitions would recreate the ambiguity already removed from `011` |