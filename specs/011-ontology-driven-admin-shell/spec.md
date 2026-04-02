# Feature Specification: Ontology-driven admin application shell

**Feature ID**: `011-ontology-driven-admin-shell`  
**Execution Branch**: `feat/ontology-driven-admin-shell`  
**Created**: 2026-03-31  
**Status**: Draft  
**Input**: User description: "Implement an admin-style application shell on top of django-material with ontology-driven navigation, workflow-aware views, permission-aware rendering, optional FAB or speed dial actions, and a strict reuse/extend/override policy."

## Intent

Define the governing server-rendered application shell for Mtafiti UI surfaces so that navigation, page framing, and contextual actions use one reusable, ontology-driven contract instead of page-local template decisions.

This intent is successful when CRUD, dashboard, and workflow-aware pages can adopt one django-material-first shell without reopening questions about navigation ownership, workflow entry routing, or FAB authority.

## System Context

### In Scope

- server-rendered django-material shell behavior for dashboard, CRUD, and workflow-aware pages
- ontology-driven navigation and contextual action ownership
- page slot ownership, workflow entry resolution, and optional FAB behavior

### Out of Scope

- SPA or client-heavy shell architecture
- persisted navigation models or arbitrary page builders
- domain-specific business data loading inside the shell layer

### Interfaces

- `/api/v1/ui/operations/*` payloads and future UI-oriented descriptor sources
- future HTML routes under `src/core/` or a dedicated UI app
- Viewflow-backed workflow entry routes

### Constraints

- must remain django-material-first
- must preserve server-side role and tenant enforcement
- must keep workflow resolution server-side

### Dependencies

- `docs/workflow-ui.md`
- tenant and policy constraints documented in `docs/request-context.md` and `docs/policy.md`

## Repository Context *(mandatory)*

- **Service area**: workflow UI shell, admin-style navigation, ontology-driven rendering, django-material presentation layer
- **Affected code paths**: `docs/workflow-ui.md`, `src/config/urls.py`, `src/core/views.py`, future HTML UI routes under `src/core/` or a dedicated UI app, future server-rendered templates under `templates/`, generated ontology and component metadata where applicable
- **Related design docs**: `docs/workflow-ui.md`, `docs/request-context.md`, `docs/policy.md`, `docs/self-reflective-implementation.md`
- **Knowledge graph / skills evidence**: `plan_viewflow_material_workflow_ui`, `compose_operations_dashboard_contract`, `extract_pattern_from_ui`, layered ontology artifacts under `ontology/`
- **External API lookup needs**: confirm django-material template-extension points and Materialize FAB initialization semantics during implementation
- **Related issues / PRs**: depends on the existing workflow UI and operational dashboard direction already documented in `docs/workflow-ui.md`

## Problem Statement

The repository already defines Viewflow as the workflow engine and django-material as the preferred Django-native presentation stack. It also documents operations dashboards, role-based visibility, tenant isolation, and server-rendered UI as the intended direction.

What is still missing is a governed admin-style application shell that can use those decisions consistently across dashboard, CRUD, and workflow-task views without hardcoding static menus or page actions.

This shell must solve a narrower and more disciplined problem than a generic frontend rewrite:

- reuse django-material layout and Materialize behavior by default,
- bind navigation and contextual actions from ontology-driven definitions,
- render CRUD and workflow-oriented views through one common shell contract,
- filter navigation and FAB actions by permission and workflow state,
- allow extension or override only when reuse and extension are insufficient.

It must **not** become an ad hoc UI layer that duplicates framework behavior or hardcodes application structure outside the ontology-driven source of truth.

## Goals

- Define a reusable admin-style application shell using django-material as the baseline layout.
- Define a strict reuse, extend, and override policy for shell composition.
- Define ontology-driven navigation and contextual action rendering.
- Define a shared content-area contract for dashboard, CRUD, form, and workflow-task views.
- Define a reusable FAB or speed-dial component with permission-aware and state-aware filtering.
- Define explicit extension points so future screens can evolve without breaking the base layout contract.

## Non-Goals

- A SPA rewrite or client-heavy workflow designer
- Replacing django-material or Materialize as the baseline UI contract in this slice
- Hardcoding application navigation inside templates without ontology-backed metadata
- Reimplementing CRUD, form rendering, or workflow runtime logic that the existing frameworks already provide
- Defining the full backend implementation of every dashboard, CRUD, or workflow screen in this specification slice

## Architectural Position

This slice defines an application-shell layer with the following priority order:

1. **Reuse**
   - use django-material layout, navbar, sidenav, form rendering, and Materialize-compatible components wherever they fit
2. **Extend**
   - use template blocks, CSS augmentation, JS initialization hooks, and partial injection when baseline components are close but not sufficient
3. **Override**
   - override only as a last resort when ontology-driven layout or workflow-aware rendering conflicts with static framework assumptions

The shell remains server-rendered, workflow-aware, permission-aware, and compatible with Materialize JS.

## Reuse / Extend / Override Policy *(mandatory)*

### Default decision tree

```text
IF feature exists in django-material:
  reuse it

ELSE IF feature partially fits:
  extend via blocks / CSS / JS

ELSE:
  override (last resort, must isolate)
```

### Reuse baseline

- `material/layout/base.html`
- navbar structure
- sidenav structure
- form rendering
- Materialize-compatible components and initialization patterns

### Extension methods

- template block override
- CSS augmentation
- JS initialization hooks
- injected partials such as FAB or contextual action fragments

### Override rules

- override is allowed only when required behavior cannot be achieved through extension or when ontology-driven rendering conflicts with static framework assumptions
- override MUST NOT break the base layout contract
- override MUST remain compatible with Materialize JS
- override MUST be isolated in a dedicated layout such as `custom_layout.html`

## Base Layout Contract

### Primary strategy

```html
{% extends "material/layout/base.html" %}
```

### Optional override strategy

```html
{% extends "material/base.html" %}
```

This fallback is allowed only when the application needs full control over structural layout for ontology-driven rendering or workflow-aware shell changes.

### Content injection

```html
{% block content %}
<div class="app-content">
  {% block page_content %}{% endblock %}
</div>

{% include "partials/fab.html" %}
{% endblock %}
```

## Ontology-driven Navigation Contract

### Menu model

The shell should support navigation metadata such as:

```python
MENU = [
  {
    "label": "Dashboard",
    "icon": "dashboard",
    "route": "/dashboard/",
    "permission": "view_dashboard",
  },
  {
    "label": "Samples",
    "icon": "inventory",
    "workflow_key": "sample_intake",
    "permission": "lims.start_sample_intake",
  },
]
```

### Canonical ownership

The first implementation MUST use one server-side shell metadata registry as the canonical source of truth for navigation and contextual actions.

- the registry MUST be defined in Python or generated Python-readable metadata that is owned by the shell layer
- templates, template tags, and page views MUST consume resolved metadata and MUST NOT define menu structure or FAB actions inline as their primary source
- page views MAY contribute page-local context such as the current object, current workflow state, or page-specific action candidates, but they MUST do so through the shared resolver contract rather than handwritten template conditionals
- persisted models for navigation are explicitly out of scope for this slice unless a later spec introduces them

This keeps the shell ontology-driven without forcing this bundle to solve long-term metadata storage prematurely.

### Resolver contract

Navigation and action rendering MUST follow this server-side resolution order:

1. load shell metadata from the canonical registry
2. bind tenant, user, route, and page context
3. resolve route-backed versus workflow-backed entries
4. apply permission and state filters
5. render only the resolved, allowed descriptors

### Rendering rules

- navigation MUST be generated dynamically from ontology-driven metadata rather than handwritten menu markup alone
- permission-aware and state-aware filtering MUST occur before rendering
- workflow-aware menu entries MUST resolve through the shared workflow action contract instead of ad hoc URL concatenation in templates
- role and tenant isolation MUST remain enforced server-side regardless of rendered menu state
- unresolved or invalid navigation descriptors MUST be excluded from render rather than producing partially bound links

### Extension and override

- if the django-material menu system is insufficient, the shell MAY override sidebar rendering and inject a dynamic renderer
- if navigation must be fully ontology-driven, sidebar rendering MAY be replaced as long as Materialize-compatible classes such as `sidenav` and `waves-effect` are preserved

## Content Area Contract

### Standard wrapper

```html
<div class="container-fluid">
  <div class="section">
    <!-- dynamic content -->
  </div>
</div>
```

### Supported view types

- `ListView`
- `DetailView`
- `FormView`
- `WorkflowTaskView`
- `DashboardView`

### Allowed content extensions

- action cards
- dashboard summary cards
- workflow state panels
- context-sensitive toolbars and action strips

### Ownership and state rules

- the shell wrapper MUST own layout structure, section spacing, shared header regions, and action-slot placement
- each page-type implementation MUST own its data loading, empty state, and domain-specific error presentation inside the shared wrapper
- the shell MUST provide stable slots for page heading, supporting actions, main content, and optional workflow state guidance
- the shell MUST NOT fetch business data directly; it consumes view-provided context and resolved shell descriptors
- when a page combines CRUD content with workflow guidance, both surfaces MUST remain separate slots inside one shared page contract rather than triggering a special-case layout

## FAB / Speed Dial Contract

### Purpose

The FAB represents contextual primary actions derived from ontology and workflow metadata, such as create, start workflow, or trigger operation.

### Reusable template shape

```html
{% if fab_actions %}
<div class="fixed-action-btn direction-top">
  <a class="btn-floating btn-large red">
    <i class="large material-icons">add</i>
  </a>

  <ul>
    {% for action in fab_actions %}
    <li>
      <a href="{{ action.url|default:'#' }}"
         class="btn-floating {{ action.color|default:'blue' }} tooltipped"
         data-tooltip="{{ action.label }}"
         data-workflow-key="{{ action.workflow_key|default:'' }}"
         data-resolved-url="{{ action.resolved_url|default:'' }}">
        <i class="material-icons">{{ action.icon }}</i>
      </a>
    </li>
    {% endfor %}
  </ul>
</div>
{% endif %}
```

### FAB data model

```python
fab_actions = [
  {
    "label": "Add Sample",
    "icon": "add_box",
    "url": "/samples/create/",
    "permission": "add_sample",
  },
  {
    "label": "Start Intake",
    "icon": "play_arrow",
    "workflow_key": "sample_intake",
    "permission": "lims.start_sample_intake",
  },
]
```


### Workflow action contract

Any navigation item or FAB action that starts a workflow MUST use an explicit `workflow_key` field as its canonical binding.

```python
{
  "label": "Start Intake",
  "icon": "play_arrow",
  "workflow_key": "sample_intake",
  "permission": "lims.start_sample_intake",
}
```

Resolution rules:

- `route` and `workflow_key` are mutually exclusive for one descriptor
- a `workflow_key` MUST resolve server-side to the canonical HTML entry route `/workflow/start/<workflow_key>/`
- the shell MUST resolve that route before render; templates MUST NOT construct workflow URLs by string concatenation
- if a `workflow_key` cannot be resolved for the current tenant or page context, the action MUST be excluded from render
### Behavior

- FAB MUST support direct URL navigation and workflow-trigger actions
- FAB MUST initialize through Materialize-compatible JS hooks
- FAB or menu action with a `workflow_key` resolves to the canonical workflow start route
- FAB placement MUST remain robust against sidebar expansion and responsive layout changes

### Initialization baseline

```javascript
document.addEventListener('DOMContentLoaded', function() {
  M.FloatingActionButton.init(
    document.querySelectorAll('.fixed-action-btn'),
    {
      direction: 'top',
      hoverEnabled: false
    }
  );

  M.Tooltip.init(document.querySelectorAll('.tooltipped'));
});
```

### Workflow trigger baseline

```javascript
document.querySelectorAll('[data-workflow-key]').forEach(el => {
  el.addEventListener('click', function(e) {
    const resolvedUrl = this.dataset.resolvedUrl;
    if (resolvedUrl) {
      e.preventDefault();
      window.location.href = resolvedUrl;
    }
  });
});
```

### Positioning baseline

```css
.fixed-action-btn {
  right: 24px;
  bottom: 24px;
  z-index: 900;
}
```

### Sidebar-aware adjustment

```css
body.sidebar-expanded .fixed-action-btn {
  right: 32px;
}
```

## Permission and State Filtering

The shell MUST filter navigation items and FAB actions by permission, tenant scope, resolution status, and required page state before rendering.

Example baseline:

```python
fab_actions = [
  action for action in fab_actions
  if action.get("resolved")
  and action.get("tenant_allowed", False)
  and user.has_perm(action.get("permission", ""))
]
```

The shell MUST also support state-aware filtering where a contextual action applies only in a matching workflow or page state.

Example baseline:

```python
required_state = action.get("state")
if required_state is not None and required_state != current_state:
    exclude
```

## Workflow Integration

The shell should treat contextual actions as two primary bindings:

- FAB or menu action with a URL resolves to navigation
- FAB or menu action with a `workflow_key` resolves to a server-resolved workflow start entry

The shell should remain compatible with skill-level concepts such as `StartWorkflowSkill` and `NavigateToViewSkill`, even if those names remain conceptual until implementation.

## Component Registration and Extension Points

The FAB should be registered as a reusable component with a contract equivalent to:

```yaml
Component:
  name: FloatingActionButton
  type: UI
  inputs:
    - actions[]
  supports:
    - permission_filtering
    - workflow_trigger
```

The shell MAY extend:

- sidebar rendering
- navbar actions
- content wrappers
- FAB behavior

## Override Scenarios

Override is allowed only when:

1. ontology-driven UI requires dynamic layout beyond supported django-material extension points
2. workflow state must alter shell structure, not only page content
3. multi-context dashboards require a custom shell composition pattern that extension cannot safely express

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reuse django-material as the default shell baseline (Priority: P1)

As a UI implementer, I want the application shell to reuse django-material layout primitives first so the shell stays aligned with framework behavior and avoids unnecessary duplication.

**Independent Test**: Implement a shell layout that extends `material/layout/base.html`, injects page content through defined blocks, and demonstrates that dashboard and CRUD views can render without replacing the base contract.

**Acceptance Scenarios**:

1. **Given** a feature can be expressed by existing django-material layout or components, **When** the shell is assembled, **Then** it reuses the framework primitive instead of replacing it.
2. **Given** a layout-level enhancement is required, **When** the shell is extended, **Then** blocks, CSS augmentation, JS hooks, or partial injection are used before override is considered.
3. **Given** a custom layout is required, **When** override is approved, **Then** the override remains isolated and compatible with Materialize behavior.

---

### User Story 2 - Render ontology-driven navigation and supported page types (Priority: P1)

As a platform architect, I want menus and content wrappers to be driven by ontology-backed metadata so navigation and page rendering remain dynamic rather than hardcoded.

**Independent Test**: Render a shell from a navigation definition that includes standard routes and workflow-backed entries, then verify the shell supports dashboard, list, detail, form, and workflow-task views through one content-area contract.

**Acceptance Scenarios**:

1. **Given** ontology-backed menu metadata exists, **When** the shell renders navigation, **Then** labels, icons, routes, and workflow entries are rendered dynamically.
2. **Given** a page declares one of the supported view types, **When** the shell renders content, **Then** it uses the shared wrapper and allows contextual cards or workflow panels without changing the shell contract.
3. **Given** django-material's built-in menu rendering is insufficient, **When** a sidebar extension is introduced, **Then** Materialize-compatible classes and responsive behavior are preserved.

---

### User Story 3 - Filter actions by permission and workflow state (Priority: P1)

As an operator, I want navigation and primary actions filtered by permission and current state so the UI only renders actions I can actually execute in the current workflow context.

**Independent Test**: Evaluate a menu and FAB action set against role permissions and a current workflow state, then verify disallowed or state-mismatched actions are excluded while server-side enforcement remains unchanged.

**Acceptance Scenarios**:

1. **Given** a menu or FAB action requires a permission, **When** the current user lacks it, **Then** the action is not rendered.
2. **Given** a menu or FAB action applies only in one state, **When** the current workflow state differs, **Then** the action is excluded.
3. **Given** a user manipulates the client directly, **When** a disallowed transition or action is attempted, **Then** server-side policy enforcement still rejects it.

---

### User Story 4 - Provide reusable FAB or speed-dial workflow actions (Priority: P2)

As a workflow-aware UI designer, I want a reusable FAB or speed-dial component that can navigate to routes or start workflows so contextual primary actions are consistent across screens.

**Independent Test**: Render a FAB from an action list containing both URL-backed and workflow-backed actions, initialize Materialize behavior, and verify the workflow trigger redirects to the configured workflow start route.

**Acceptance Scenarios**:

1. **Given** a page exposes contextual primary actions, **When** the FAB is rendered, **Then** actions appear as a reusable floating action menu with tooltips.
2. **Given** a FAB action includes a URL, **When** the action is selected, **Then** navigation occurs normally.
3. **Given** a FAB action includes a workflow identifier, **When** the action is selected, **Then** the workflow start route is invoked through the configured integration behavior.

## Edge Cases

- How should the shell behave when a workflow action exists but the current user lacks permission to start that workflow?
- How should navigation behave when ontology metadata is incomplete or references a route that is disabled in the current tenant context?
- How should FAB actions behave on pages where a sidebar, state panel, or dashboard overlay could visually collide with the floating action region?
- How should the shell represent pages that combine CRUD content with workflow state guidance without collapsing them into one special-case template?

Required answers for this slice:

- if the current user lacks the required permission for a navigation or FAB action, the descriptor MUST be excluded before render
- if tenant context disables a route or workflow entry, the descriptor MUST be excluded before render
- if a page layout would cause FAB collision on common screen sizes, the page MAY suppress the FAB slot and surface the same actions in the shared action-strip slot instead
- if no current workflow or page state is available, any state-constrained action MUST be excluded by default

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The application shell MUST use django-material layout as the baseline presentation strategy.
- **FR-002**: The shell MUST follow the strict reuse, extend, and override decision tree where reuse is default, extension is preferred, and override is isolated as a last resort.
- **FR-003**: The default base layout MUST extend `material/layout/base.html` unless a justified override requires `material/base.html`.
- **FR-004**: The shell MUST provide a shared content injection contract that supports page-content blocks and optional FAB partial injection.
- **FR-005**: Navigation MUST be generated dynamically from ontology-driven metadata instead of static template markup alone.
- **FR-006**: The shell MUST support navigation items that resolve to either standard routes or workflow-backed entry points.
- **FR-007**: The shell MUST support `ListView`, `DetailView`, `FormView`, `WorkflowTaskView`, and `DashboardView` as first-class page types.
- **FR-008**: The shell MUST allow contextual dashboard cards, action cards, and workflow state panels within the shared content contract.
- **FR-009**: The shell MUST provide a reusable FAB or speed-dial component whose actions are derived from contextual metadata.
- **FR-010**: FAB actions MUST support direct URL navigation and workflow-trigger behavior.
- **FR-011**: FAB actions MUST be filtered by permission before rendering.
- **FR-012**: FAB actions MUST support state-aware filtering against the current workflow or page state.
- **FR-013**: Any sidebar or navigation override MUST preserve Materialize-compatible classes and responsive behavior.
- **FR-014**: Any full-layout override MUST remain isolated and MUST NOT break the base layout contract.
- **FR-015**: The shell MUST keep ontology or metadata definitions as the source of truth for navigation and contextual actions rather than hardcoding view-specific UI logic.
- **FR-016**: The shell MUST remain compatible with server-side permission enforcement and MUST NOT treat client-side filtering as sufficient authorization.
- **FR-017**: The shell MUST define extension points for sidebar rendering, navbar actions, content wrappers, and FAB behavior.
- **FR-018**: The first implementation MUST define one canonical server-side shell metadata registry for navigation items and contextual actions.
- **FR-019**: Templates and page views MUST consume resolved shell descriptors and MUST NOT construct menu trees or workflow-start links inline.
- **FR-020**: Workflow-backed navigation items and FAB actions MUST use `workflow_key` as the canonical binding and MUST resolve to `/workflow/start/<workflow_key>/` server-side.
- **FR-021**: Route-backed and workflow-backed descriptors MUST be mutually exclusive within one action or navigation item.
- **FR-022**: Descriptor filtering MUST be deny-by-default: unresolved routes, unresolved workflow keys, missing permissions, missing tenant scope, or missing required page state all result in exclusion from render.
- **FR-023**: The shell wrapper MUST own structure and slots, while page implementations remain responsible for data loading and domain-specific empty or error states.
- **FR-024**: The shell MUST provide stable slots for page heading, supporting actions, main content, workflow guidance, and optional FAB placement.
- **FR-025**: A page that suppresses FAB for responsive or collision reasons MUST still expose the same allowed actions through a shared non-floating action slot.

### Non-Functional Requirements

- **NFR-001**: The shell MUST remain compatible with Materialize JS initialization patterns.
- **NFR-002**: The shell MUST preserve responsive layout behavior and MUST NOT introduce overlay collisions that hide core navigation or FAB actions on common screen sizes.
- **NFR-003**: The shell contract MUST be explicit enough that future CRUD and workflow screens can adopt it without redefining base layout behavior.
- **NFR-004**: Override behavior MUST remain auditable and isolated enough that code review can distinguish reuse, extension, and override decisions clearly.
- **NFR-005**: The shell contract MUST be deterministic enough that two implementers would derive the same workflow entry routing, filtering behavior, and slot ownership from this spec.

### Key Entities *(include if feature involves data)*

- **ApplicationShell**: The reusable django-material-based admin shell used by CRUD, dashboard, and workflow pages.
- **NavigationItem**: Ontology-driven menu metadata containing labels, icons, route or workflow bindings, and permission constraints.
- **ViewTypeContract**: One supported page-type contract such as dashboard, list, detail, form, or workflow task.
- **FloatingActionButton**: Reusable contextual action component supporting URL and workflow bindings.
- **ActionDescriptor**: Contextual action metadata containing label, icon, route or workflow binding, permission, and optional state constraint.

## Proposed Mapping to Current Repository

### Reuse

- reuse `docs/workflow-ui.md` as the current contract for Viewflow plus django-material UI direction
- reuse existing UI-focused operational endpoints under `/api/v1/ui/operations/*` as the backend payload source of truth
- reuse role-based visibility and tenant-isolation constraints already documented for operations dashboards and workflow surfaces

### Redefine or extend

- extend the current documentation and future HTML UI routes so an admin-style shell becomes explicit rather than implied
- extend navigation and contextual action rendering from static route assumptions toward ontology-driven metadata
- define a reusable FAB contract instead of page-local floating-action implementations

### Controlled override

- allow a custom shell layout only when ontology-driven or workflow-state-driven structure cannot be represented safely by django-material extension points

## Proving Surfaces

The first implementation should prove the shell contract across three concrete surface types:

1. an operations-style dashboard landing page
2. one CRUD list or detail surface
3. one workflow-start or workflow-task entry surface

Issue slicing and implementation validation should use those surfaces to verify that one shell contract works across navigation, content slots, and contextual actions.

## Success Criteria *(mandatory)*

- **SC-001**: The spec clearly defines the admin-style application shell as django-material-first rather than a generic custom frontend.
- **SC-002**: The spec makes ontology-driven navigation and contextual action rendering the source-of-truth pattern.
- **SC-003**: The spec clearly distinguishes reuse, extension, and override decisions and limits override to isolated cases.
- **SC-004**: The spec defines a reusable FAB or speed-dial component with permission-aware and workflow-aware behavior.
- **SC-005**: The spec is implementation-ready enough to drive one or more GitHub issues for shell layout, navigation rendering, FAB behavior, and controlled overrides.
- **SC-006**: The spec names a canonical metadata ownership model and eliminates ambiguity about where navigation and contextual actions are defined first.
- **SC-007**: The spec fixes one canonical workflow binding and route-resolution contract for shell actions.
- **SC-008**: The spec defines deny-by-default filtering semantics for permission, tenant, and state constraints.

## Delivery Mapping *(mandatory)*

- **Primary issue title**: Define ontology-driven admin application shell on django-material
- **Planned branch label**: `feat/ontology-driven-admin-shell`
- **Expected PR scope**: specification-first UI shell definition followed by scoped implementation issues for layout, navigation, FAB, and extension points
- **Blocking dependencies**: current workflow UI documentation and django-material baseline remain prerequisites for implementation