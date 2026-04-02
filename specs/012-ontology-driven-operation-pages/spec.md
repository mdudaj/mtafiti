# Feature Specification: Ontology-driven operational pages

**Feature ID**: `012-ontology-driven-operation-pages`  
**Execution Branch**: `feat/ontology-driven-operation-pages`  
**Created**: 2026-03-31  
**Status**: Draft  
**Input**: User description: "Implement reusable operational pages where action cards are the primary interaction surface, bind to views or workflows, support ordering/permissions/state, integrate with sidebar navigation and optional FAB, and remain ontology-driven."

## Intent

Define one reusable operational page pattern that lets operators choose the next allowed action from a bounded set of intent-driven cards, without pushing action ownership back into ad hoc templates, custom dashboards, or page-local workflow launch logic.

This intent is successful when operation pages become a reliable, repeatable page type on top of the `011` shell and the same descriptor contract can drive route-backed actions, workflow-backed actions, and optional FAB emphasis.

## System Context

### In Scope

- operation pages that use action cards as the primary interaction surface
- route-backed and workflow-backed card resolution
- ordering, filtering, page density, and optional FAB derivation rules

### Out of Scope

- redefining the `011` shell itself
- replacing monitors or dashboards with unrestricted action launchers
- client-side workflow URL construction or authorization logic

### Interfaces

- `011-ontology-driven-admin-shell`
- `/api/v1/ui/operations/*` payloads and allowed-action sources
- future operation-page templates and reusable card partials

### Constraints

- must remain server-rendered and django-material-compatible
- must remain tenant-scoped and role-aware
- must keep action ownership in canonical server-side descriptors

### Dependencies

- `011-ontology-driven-admin-shell`
- current operational UI routes and templates under `src/core/templates/core/ui/`

## Repository Context *(mandatory)*

- **Service area**: operational UI surfaces, action-oriented page composition, django-material presentation layer, Viewflow-aware interaction entry points
- **Affected code paths**: `docs/workflow-ui.md`, `src/core/views.py`, `src/core/templates/core/ui/`, future operation-page templates and component partials under `templates/` or `src/core/templates/`, existing `/api/v1/ui/operations/*` payload builders where operation-page descriptors or allowed actions are surfaced
- **Related design docs**: `docs/workflow-ui.md`, `docs/request-context.md`, `docs/policy.md`, `docs/operations-dashboards-alerts.md`
- **Dependencies**: `011-ontology-driven-admin-shell`, parent issue `#130`, implementation issues `#131`, `#132`, and `#133`
- **Knowledge graph / skills evidence**: `plan_viewflow_material_workflow_ui`, `compose_operations_dashboard_contract`, existing operational dashboard and workbench templates under `src/core/templates/core/ui/`
- **External API lookup needs**: confirm django-material card-compatible layout extension points and Materialize card/FAB interaction baselines during implementation

## Problem Statement

The repository now has a shell-level direction for ontology-driven navigation, page slots, and optional FAB behavior, but it still lacks a reusable page pattern where the main interaction surface is a small, ordered set of intent-driven action cards.

Operational pages are not generic dashboards and not free-form CRUD screens. They are focused action-entry surfaces that should let an operator quickly choose one of a bounded set of allowed actions such as receiving a sample, starting a batch workflow, or opening a role-specific operational form.

Without a governed contract, operational pages will drift into page-local template forks with inconsistent card shapes, ad hoc workflow URL construction, unclear ordering behavior, and duplicated permission logic.

This slice defines the missing page-level contract:

- action cards are the primary interaction surface,
- each card resolves to exactly one route-backed or workflow-backed entry,
- card visibility and ordering are deterministic,
- optional FAB behavior remains subordinate to the same allowed-action set,
- the pattern remains reusable across tenant-scoped operational pages.

## Goals

- Define `OperationPage` as a reusable page contract built on top of the `011` shell.
- Define `ActionCard` as the canonical reusable descriptor for operational entry actions.
- Define deterministic ordering, filtering, and resolution rules for action cards.
- Define django-material and Materialize-compatible layout, card, and hover behavior constraints.
- Define how operational pages integrate with sidebar navigation and optional FAB behavior without creating a second source of truth.
- Define bounded extension and override rules so future operation pages remain consistent.

## Non-Goals

- Replacing the `011` admin shell or redefining its navigation/FAB foundations
- Turning operational pages into arbitrary dashboard canvases or multi-purpose landing pages
- Allowing templates to define card behavior inline without resolved descriptors
- Introducing client-side-only workflow resolution or authorization checks
- Solving every downstream operational screen in this bundle

## Architectural Position

This slice is a page-pattern extension of `011-ontology-driven-admin-shell`.

Priority order:

1. **Reuse `011` shell contracts**
   - inherit the shell slots, resolver model, and workflow binding rules already defined in `011`
2. **Define one reusable operational page pattern**
   - provide a bounded card-grid surface for action entry rather than another generic panel system
3. **Extend only where operation pages need additional semantics**
   - add page-level action ordering, card layout, and FAB derivation rules without redefining shell ownership

Operation pages remain server-rendered, tenant-scoped, permission-aware, and workflow-aware.

## Reuse / Extend / Override Policy *(mandatory)*

### Reuse baseline

- reuse the `011` shell layout and slot ownership model
- reuse the canonical descriptor-resolution pipeline from `011`
- reuse `workflow_key` as the only workflow-backed action binding
- reuse the same deny-by-default authorization posture for render-time filtering

### Extension methods

- define an `OperationPage` descriptor that contributes page-specific action-card sets into the shell
- define a reusable `ActionCard` component partial and card-grid wrapper
- derive optional FAB behavior from the same resolved action-card set or from an explicit page-level primary-action override

### Override rules

- override the default card-grid layout only when a page must become a step-based or state-staged interaction surface that the standard grid cannot express safely
- any override MUST preserve the action-card descriptor contract, role filtering rules, and full-card click behavior
- any override MUST remain subordinate to the `011` shell contract

## Operation Page Contract

### Page model

An operational page represents one bounded operator intent surface.

It MUST define:

- one page identity and title
- one sidebar navigation binding or page route binding within the `011` shell
- one resolved set of `ActionCard` descriptors
- optional page summary text
- optional page-level primary action selection for FAB behavior

### Page responsibilities

- present a small, action-oriented set of related operational intents
- keep cards as the primary interaction surface for entry actions
- remain bounded to one operational domain or closely related operational procedure family

### Page limits

- an operation page SHOULD render between 1 and 6 cards in the common case
- an operation page MUST NOT render more than 8 cards in one ungrouped grid
- if more than 8 candidate actions exist, the page MUST split the surface by context, introduce secondary navigation, or define multiple operation pages

## Action Card Descriptor *(mandatory)*

### Canonical data shape

```yaml
ActionCard:
  id: string
  title: string
  description: string
  icon: string
  sequence: integer?
  route: string?
  workflow_key: string?
  permission: string?
  required_state: string | list[string]?
  data_condition: string?
  primary_action: boolean?
```

### Descriptor rules

- `id` MUST be stable within the page and suitable for analytics, tests, and ontology references
- `title` MUST be action-oriented and short
- `description` MUST be no more than one sentence
- `icon` MUST use the Material icon set already used by the shell
- `route` and `workflow_key` are mutually exclusive
- each card MUST resolve to exactly one allowed interaction target before render
- `primary_action` MAY mark one card as the explicit FAB candidate when FAB is enabled

### Canonical ownership

Action-card descriptors MUST be produced by the same server-side registry and resolver discipline introduced in `011`.

- templates MUST receive resolved descriptors and MUST NOT invent card entries inline
- page views MAY contribute page context, current state, and data-availability facts to the resolver
- operational UI endpoints MAY surface allowed-action payloads that feed operation pages, but those payloads MUST still conform to the same descriptor contract

## Cross-Layer Binding

Each `ActionCard` is both a UI artifact and an operational intent binding.

```text
ActionCard
  -> UI card component
  -> route or workflow entry binding
  -> process or task state constraint
  -> optional domain model or work item context
```

This means a card is not just a visual shortcut. It is the governed representation of an allowed operational intent for the current tenant, user, and page context.

## Layout Contract

### Base template pattern

```html
{% extends "material/layout/base.html" %}

{% block content %}
<div class="container-fluid">
  <div class="section">
    <div class="row">
      {% for card in action_cards %}
        {% include "components/action_card.html" with card=card %}
      {% endfor %}
    </div>
  </div>
</div>

{% include "partials/fab.html" %}
{% endblock %}
```

### Grid rules

- use Materialize-compatible responsive columns with `col s12 m6 l4` as the default operational card density
- cards MUST align in a consistent responsive grid
- the grid MUST remain legible without requiring nested buttons or per-card action menus in the common case
- empty states MUST use the shared shell empty-state slot rather than rendering an empty grid

## Reusable Action Card Component

### Template contract

```html
<div class="col s12 m6 l4">
  <a href="{{ card.resolved_url|default:'#' }}"
     class="card hoverable action-card"
     data-workflow-key="{{ card.workflow_key|default:'' }}"
     data-card-id="{{ card.id }}">

    <div class="card-content">
      <div class="card-header">
        <div class="icon-wrapper">
          <i class="material-icons">{{ card.icon }}</i>
        </div>

        {% if card.sequence is not None %}
        <span class="sequence">{{ card.sequence }}</span>
        {% endif %}
      </div>

      <div class="card-body">
        <span class="card-title">{{ card.title }}</span>
        <p>{{ card.description }}</p>

        <div class="hover-cue">
          <span>Open</span>
        </div>
      </div>
    </div>
  </a>
</div>
```

### Interaction rules

- the full card surface MUST be clickable
- buttons nested inside the card are prohibited for the primary action path
- the card MUST use `resolved_url` produced server-side rather than constructing workflow URLs client-side
- cards MAY display sequence and hover cues, but those decorations MUST NOT replace the card title or description as the main affordance

## Card Styling Contract

### Required styling semantics

- cards MUST fill their column height cleanly enough to align in common grid layouts
- header layout MUST accommodate icon and sequence without pushing the title below the fold on standard desktop widths
- hover cues MAY animate subtly but MUST remain optional for keyboard-only usage
- styling MUST remain a Materialize-aligned extension, not a replacement component library

### Allowed extension

- elevation and spacing may be tuned
- subtle transitions may be added
- icon container treatment may be themed by operational domain

### Disallowed styling behaviors

- animation that obscures the title, icon, or click target
- interaction models that require hovering to discover the only actionable control
- page-specific card markup forks for cosmetic variation alone

## Resolution, Filtering, and Ordering *(mandatory)*

### Resolution pipeline

Operation pages MUST resolve action cards in this order:

1. load page descriptor and candidate action cards from the canonical registry or allowed-action payload
2. bind tenant, user, route, page context, and optional work-item context
3. resolve `route` or `workflow_key` into one `resolved_url`
4. apply permission filtering
5. apply state filtering
6. apply data-availability filtering
7. sort cards deterministically
8. derive optional FAB behavior
9. render allowed cards

### Filtering rules

- cards with unresolved routes or unresolved `workflow_key` values MUST be excluded
- cards with missing required permission MUST be excluded
- cards with non-matching `required_state` MUST be excluded
- cards whose `data_condition` is not satisfied MUST be excluded
- all filtering remains advisory for UI rendering; server-side authorization remains mandatory for the target route or workflow

### Ordering rules

- cards with explicit `sequence` MUST sort ascending by `sequence`
- ties on `sequence` MUST break by `title`, then by `id`
- cards without `sequence` MUST appear after sequenced cards in stable registry order
- ordering MUST be deterministic across repeated renders for the same input context

## Workflow and Route Binding

### Route-backed card

- a route-backed card navigates to `resolved_url`

### Workflow-backed card

- a workflow-backed card uses `workflow_key`
- `workflow_key` MUST resolve server-side to the canonical shell workflow entry route from `011`
- templates and client scripts MUST NOT concatenate `/workflow/start/<workflow_key>/` directly

### Click behavior

- card click MUST navigate to `resolved_url`
- workflow-backed cards MAY include data attributes for analytics or enhancement, but not for primary URL construction

## FAB Integration

### Role of FAB

The FAB is optional on an operation page.

If present, it represents the highest-priority allowed action, while cards remain the primary page surface.

### Derivation rules

- FAB MUST NOT introduce an action that is absent from the resolved allowed card set
- FAB MAY be derived from the first explicit `primary_action` card
- if no explicit `primary_action` exists, FAB MAY derive from the first allowed sorted card
- pages MAY disable FAB when the page already presents one clear card action or when FAB would visually compete with the card grid

### Consistency rules

- the FAB target MUST equal one allowed card target
- if FAB is suppressed for responsive or layout reasons, the underlying card set remains authoritative

## Sidebar Navigation Integration

- each operation page MUST have one navigation entry or navigation parent within the `011` shell
- sidebar navigation decides how the user arrives at the page
- action cards decide what the user can do next within that operational context
- operation pages MUST NOT duplicate sidebar navigation items as cards unless the page is explicitly acting as a bounded action launcher for that one navigation node

## Dynamic and State-Aware Behavior

- cards MAY be generated dynamically from current workflow state, role, and data availability
- dynamic generation MUST still produce the canonical descriptor shape before render
- workflow-state-driven cards MUST remain bounded to current operational context and MUST NOT mix unrelated procedures on the same page

## Reusability and Registration

### Component registration

```yaml
Component:
  name: ActionCard
  type: UI
  reusable: true
  depends_on:
    - OperationPage
    - ApplicationShell
```

### Capability mapping

```text
RenderOperationPage =
  ResolveActionCards +
  ApplyPermissions +
  ApplyStateAndDataFilters +
  SortCards +
  RenderGrid +
  OptionallyDeriveFAB
```

## Extension / Override Rules

### Extend (preferred)

- styling density
- hover behavior
- card emphasis rules
- grid spacing

### Override (allowed)

Override is allowed only when:

1. ontology requirements demand a staged or step-based layout rather than a bounded card grid
2. workflow-state progression needs card groups or sectional progression that the default grid cannot represent safely
3. accessibility or device constraints require a different arrangement while preserving the same descriptor contract

Example allowed override:

- replace one flat grid with a two-section staged layout for preconditions and next actions

## Constraints *(mandatory)*

### MUST

- use action-oriented titles
- keep descriptions to one sentence or less
- use Material icons consistently
- keep the full card surface clickable
- keep action cards as the primary interaction surface on the page
- keep cards scoped to one operational domain or related procedure family

### MUST NOT

- render nested primary buttons inside cards
- render more than 8 ungrouped cards on one page
- mix unrelated operations into one launcher surface
- construct workflow URLs inline in templates or JavaScript

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Launch a route-backed operational action from a bounded card grid (Priority: P1)

As an operator, I want to open a common operational form or CRUD entry from a full-card click surface so that I can begin work from one clean operational page instead of navigating through dense menus.

**Independent Test**: Render an operation page with route-backed cards only, confirm that cards sort correctly, align in the grid, and navigate through server-resolved URLs without nested buttons.

**Acceptance Scenarios**:

1. **Given** a page has allowed route-backed actions, **When** the operation page renders, **Then** each card appears in deterministic order and the full card opens the resolved route.
2. **Given** a card lacks permission, **When** the page resolves action cards, **Then** that card is excluded before render.
3. **Given** more than 8 candidate actions exist, **When** the page is designed, **Then** the actions are split into multiple contexts rather than rendered as one overloaded grid.

---

### User Story 2 - Launch workflow-backed operational actions from the same card pattern (Priority: P1)

As an operator, I want cards to start the correct workflow entry path without handwritten workflow URL logic so that operation pages remain consistent with the shell's workflow contract.

**Independent Test**: Render an operation page with both route-backed and workflow-backed cards, confirm that `workflow_key` descriptors resolve to server-provided URLs, and verify that unresolved workflow entries are excluded.

**Acceptance Scenarios**:

1. **Given** a card uses `workflow_key`, **When** the page resolves descriptors, **Then** the card receives one server-resolved workflow entry URL.
2. **Given** a workflow key is invalid for the current tenant or context, **When** the page resolves cards, **Then** that card is excluded before render.
3. **Given** the user clicks a workflow-backed card, **When** navigation occurs, **Then** it uses the resolved URL rather than client-side string concatenation.

---

### User Story 3 - Show only the right actions for the current state and data context (Priority: P1)

As an operator, I want operation pages to hide actions that do not apply to my current role, workflow state, or data availability so that the page remains trustworthy and uncluttered.

**Independent Test**: Evaluate one page against different user roles, workflow states, and data conditions, then verify that only allowed cards remain visible and that ordering stays deterministic after filtering.

**Acceptance Scenarios**:

1. **Given** a card requires a state the page does not currently satisfy, **When** the page resolves cards, **Then** the card is excluded.
2. **Given** a card depends on missing data availability, **When** the page resolves cards, **Then** the card is excluded.
3. **Given** filtering changes the visible set, **When** the page renders, **Then** the remaining cards still follow deterministic ordering.

---

### User Story 4 - Optionally expose one primary action through FAB without diverging from cards (Priority: P2)

As a workflow-aware UI designer, I want one optional FAB to surface the highest-priority allowed action while the cards remain authoritative so that the page can emphasize a common action without creating competing action models.

**Independent Test**: Render an operation page with one explicit primary action, verify that the FAB target matches the corresponding card target, and confirm that disabling FAB does not change the allowed card set.

**Acceptance Scenarios**:

1. **Given** one card is marked `primary_action`, **When** FAB is enabled, **Then** the FAB target matches that card's resolved target.
2. **Given** no explicit primary action exists, **When** FAB derivation is allowed, **Then** the first allowed sorted card may be used.
3. **Given** FAB is suppressed for layout reasons, **When** the page renders, **Then** the card grid still exposes the same allowed actions.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Operation pages MUST be implemented as a page-pattern extension of `011-ontology-driven-admin-shell`.
- **FR-002**: Operation pages MUST render action cards as the primary interaction surface.
- **FR-003**: Each `ActionCard` MUST resolve to exactly one route-backed or workflow-backed target before render.
- **FR-004**: `route` and `workflow_key` MUST be mutually exclusive on one card.
- **FR-005**: `workflow_key` MUST resolve server-side through the canonical workflow-entry contract from `011`.
- **FR-006**: Action cards MUST be produced from canonical server-side descriptors rather than template-local definitions.
- **FR-007**: Operation pages MUST apply permission, state, and data-availability filtering before render.
- **FR-008**: Operation pages MUST exclude unresolved cards before render.
- **FR-009**: Operation pages MUST order cards deterministically with sequenced cards first.
- **FR-010**: The default operation-page grid MUST use Materialize-compatible responsive columns.
- **FR-011**: The full card surface MUST be clickable.
- **FR-012**: The page MUST NOT rely on nested primary buttons inside cards for the main action.
- **FR-013**: The page MUST NOT render more than 8 ungrouped cards.
- **FR-014**: Descriptions MUST remain one sentence or shorter.
- **FR-015**: If FAB is enabled, it MUST derive from the same allowed action set as cards.
- **FR-016**: FAB MUST NOT point to an action absent from the rendered allowed cards.
- **FR-017**: Each operation page MUST integrate with one shell navigation node or navigation parent.
- **FR-018**: Dynamic cards generated from workflow state, role, or data context MUST still conform to the canonical `ActionCard` descriptor.
- **FR-019**: Operation pages MUST remain tenant-scoped and consistent with server-side authorization checks.
- **FR-020**: Override layouts MUST preserve the underlying action-card descriptor and interaction contract.

### Non-Functional Requirements

- **NFR-001**: The page pattern MUST remain server-rendered and compatible with django-material and Materialize behaviors.
- **NFR-002**: The card grid MUST remain readable and actionable on desktop and mobile breakpoints.
- **NFR-003**: Two implementers applying the same descriptors and page context MUST render the same visible cards in the same order.
- **NFR-004**: The page pattern MUST be reusable across multiple operational domains without page-local contract changes.
- **NFR-005**: Card interactions MUST remain accessible to keyboard users without hover-only affordances.

### Key Entities *(include if feature involves data)*

- **OperationPage**: One bounded operational entry surface rendered inside the `011` shell.
- **ActionCard**: Reusable operational entry descriptor bound to exactly one resolved route or workflow entry.
- **ResolvedActionSet**: The filtered and ordered action-card collection that the page actually renders.
- **PrimaryAction**: Optional FAB-compatible action derived from the resolved action set.

## Proposed Mapping to Current Repository

### Reuse

- reuse the `011` shell contract for layout, workflow binding, and optional FAB semantics
- reuse existing `/api/v1/ui/operations/*` allowed-action and capability payload concepts where they fit operation-page descriptors
- reuse current operational UI includes and template patterns where they can host card-grid content without redefining shell ownership

### Extend

- define explicit operation-page descriptors and reusable `ActionCard` component partials
- extend operational surfaces so action-card launcher pages become first-class alongside current monitor and dashboard screens
- define deterministic ordering and action-derivation rules for operation pages

### Controlled override

- allow staged or sectioned layouts only when a page's action semantics cannot be represented safely by one bounded card grid

## Implementation Readiness Anchors

The first implementation should prove the pattern on three concrete surfaces:

1. one route-heavy operational intake page
2. one mixed route-and-workflow page
3. one state-sensitive page where visible actions change by current context

## Success Criteria *(mandatory)*

- **SC-001**: The spec clearly defines operation pages as a reusable page pattern on top of `011`, not as a competing shell.
- **SC-002**: The spec defines one canonical `ActionCard` descriptor with unambiguous route versus workflow binding.
- **SC-003**: The spec fixes deterministic filtering and ordering behavior before render.
- **SC-004**: The spec keeps FAB behavior subordinate to the same allowed card set.
- **SC-005**: The spec defines clear page-density and scope constraints so operation pages do not become overloaded dashboards.
- **SC-006**: The spec is issue-ready for operation-page contract work, reusable component work, and proving-surface implementation work.

## Delivery Mapping *(mandatory)*

- **Primary issue title**: Define ontology-driven operational pages with reusable action cards
- **Planned branch label**: `feat/ontology-driven-operation-pages`
- **Expected PR scope**: specification-first definition of action-card operation pages, then scoped implementation issues for descriptor resolution, reusable component rendering, and proving pages
- **Blocking dependencies**: `011-ontology-driven-admin-shell` issue chain must remain the governing shell contract