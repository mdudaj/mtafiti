# Feature Specification: Metadata vocabularies and configurable form schemas

**Feature ID**: `001-metadata-vocabularies-and-form-schemas`  
**Execution Branch**: `feat/metadata-vocabularies-and-form-schemas`  
**Created**: 2026-03-19  
**Status**: Draft  
**Input**: User description: "Revise metadata configuration before further implementation, starting with vocabularies organized per functionality and versioned configurable form schemas with draft/published versions."

## Repository Context *(mandatory)*

- **Service area**: `lims` metadata configuration
- **Affected code paths**: `src/lims/models.py`, `src/lims/services.py`, `src/lims/views.py`, `src/lims/urls.py`, `src/lims/templates/lims/`, `src/tests/test_lims_metadata_api.py`
- **Related design docs**: `docs/lab-lims.md`, `docs/self-reflective-implementation.md`, `docs/spec-kit-workflow.md`
- **Knowledge graph / skills evidence**: metadata domain and configurable metadata skills referenced in the session plan; local skills include `viewflow-configurable-metadata-forms`
- **External API lookup needs**: likely Context Hub / local knowledge lookups for schema-driven form builder patterns and controlled vocabulary API design during implementation
- **Related issues / PRs**: none yet; this spec should become the source for future issue creation

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Manage vocabularies by functional domain (Priority: P1)

As a LIMS administrator, I want controlled vocabularies grouped by functional purpose so I can discover, provision, and maintain them without mixing unrelated enumerations together.

**Why this priority**: Controlled vocabularies are foundational for all schema-driven forms and select widgets, so they must be coherent before more metadata features are built.

**Independent Test**: An admin can create or provision tenant-scoped vocabularies under domains like roles, outcomes, consent types, units, or workflow states, then query them by domain through dedicated REST endpoints.

**Acceptance Scenarios**:

1. **Given** an administrator views metadata vocabularies, **When** they filter by a functional domain such as `roles`, **Then** only vocabularies for that domain are returned.
2. **Given** a tenant has an initial vocabulary provision set, **When** the tenant metadata API is queried, **Then** the default vocabularies are present without requiring one-by-one manual creation.
3. **Given** a previously unforeseen vocabulary is needed, **When** an administrator defines a new domain vocabulary, **Then** it can be added without a code change or data-model fork.

---

### User Story 2 - Search vocabulary values from dedicated widget APIs (Priority: P1)

As an operator or form designer, I want dedicated searchable vocabulary endpoints so select and multi-select widgets can load large controlled lists quickly and consistently.

**Why this priority**: Searchable REST endpoints are required before vocabularies can reliably power richer select widgets across the platform.

**Independent Test**: A client widget can query a vocabulary item endpoint with a search term and receive filtered, paginated, display-ready results for single or multi-select rendering.

**Acceptance Scenarios**:

1. **Given** a select widget for a vocabulary with many items, **When** the user types a search term, **Then** the widget retrieves matching items from a dedicated REST endpoint instead of downloading the full list.
2. **Given** a multi-select field references a controlled vocabulary, **When** the widget requests options, **Then** the API returns stable `value` / `label` payloads suitable for reusable select components.
3. **Given** an inactive or deprecated vocabulary item exists, **When** default widget queries are made, **Then** that item is excluded unless explicitly requested for historical display.

---

### User Story 3 - Define versioned configurable form schemas in two steps (Priority: P1)

As a metadata designer, I want to define form metadata first and then build fields for a specific form version so schemas can evolve safely through draft and published states.

**Why this priority**: Versioned configurable forms are the core of metadata-driven workflows, and the user explicitly wants field ownership to be ODK-style under a form version.

**Independent Test**: A designer can create a form definition with metadata such as name, code, target, and version, then open a second-step builder for that draft version, add fields that belong directly to the form version, and publish it when valid.

**Acceptance Scenarios**:

1. **Given** a new configurable form is needed, **When** the designer creates the form metadata, **Then** a draft form version is established before any fields are added.
2. **Given** the designer edits a draft form version, **When** they use the field builder, **Then** all fields belong directly to that form version rather than referencing shared global definitions.
3. **Given** a published form version is already in use, **When** the designer creates a new draft version, **Then** existing published versions remain immutable and available for existing bindings or submissions.

---

### User Story 4 - Bind published form versions to runtime targets (Priority: P2)

As an administrator, I want only published form versions to be bound to runtime targets so live workflows do not depend on incomplete drafts.

**Why this priority**: Binding discipline protects active operational workflows and keeps draft design separate from runtime execution.

**Independent Test**: A published form version can be activated for a target such as `sample_type` or `workflow_step`, while draft versions cannot be activated for runtime use.

**Acceptance Scenarios**:

1. **Given** a draft form version exists, **When** an administrator attempts to bind it to a runtime target, **Then** the system rejects the action with a clear validation error.
2. **Given** a published form version is active for a target, **When** a new published version is activated, **Then** the target is switched in a controlled, auditable way.

## Edge Cases

- What happens when a vocabulary domain exists but has no current items?
- How are historical submissions rendered if a vocabulary item is later deprecated?
- What happens when a draft form version includes invalid field definitions or duplicate keys?
- How does the system prevent accidental editing of a published form version already used by runtime targets?
- How are large vocabularies handled for widget search and pagination without loading the entire set into the browser?
- What tenancy and permission boundaries prevent one tenant from reading or reusing another tenant's controlled vocabularies or form definitions?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST support tenant-scoped controlled vocabularies organized by functional domain or category.
- **FR-002**: The system MUST provide dedicated REST endpoints to list, filter, and search vocabularies and vocabulary items for select and multi-select widgets.
- **FR-003**: The system MUST support initial provisioning of common vocabularies for a tenant without requiring manual one-by-one entry.
- **FR-004**: The system MUST let administrators define new unforeseen vocabularies and vocabulary domains through configuration rather than code changes.
- **FR-005**: The system MUST support configurable forms whose fields belong directly to a form version rather than to reusable global field definitions.
- **FR-006**: The system MUST support a two-step authoring workflow: first define form metadata, then build fields for a draft version.
- **FR-007**: The system MUST distinguish draft and published form versions, and published versions MUST be immutable.
- **FR-008**: The system MUST allow only published form versions to be activated for runtime targets such as sample types or workflow steps.
- **FR-009**: The system MUST preserve tenant isolation, permission boundaries, and auditable state transitions across vocabularies, form versions, and bindings.
- **FR-010**: The system MUST return stable display-ready option payloads suitable for shared single-select and multi-select widgets.

### Non-Goals

- Building the full production form-builder UI in this specification slice
- Introducing cross-tenant shared vocabulary catalogs in the first pass
- Reworking workflow runtime execution beyond the metadata / binding contract needed for forms
- Implementing advanced hierarchical thesauri or external standards federation in the first pass

### Key Entities *(include if feature involves data)*

- **Vocabulary Domain**: A functional grouping such as roles, outcomes, consent, units, or statuses that organizes controlled vocabularies by purpose.
- **Controlled Vocabulary**: A tenant-scoped set of allowed values within a domain, with metadata supporting discovery, search, provisioning, and lifecycle state.
- **Controlled Vocabulary Item**: A value/label pair exposed through searchable option APIs and optionally tracked for active/deprecated lifecycle handling.
- **Form Definition**: The logical identity of a configurable form, including metadata such as name, code, purpose, target applicability, and human-readable description.
- **Form Version**: A draft or published immutable snapshot of a form definition, used for editing, publishing, and binding.
- **Form Field**: A field that belongs directly to a specific form version, carrying field type, key, label, validation, condition, widget hints, and vocabulary bindings.
- **Form Binding**: The controlled activation of a published form version for a runtime target such as a sample type or workflow step.

## Success Criteria *(mandatory)*

- **SC-001**: Administrators can discover and query vocabularies by functional domain through dedicated tenant-safe REST endpoints.
- **SC-002**: Shared select and multi-select widgets can load vocabulary options through paginated search APIs without needing full-list downloads.
- **SC-003**: Metadata designers can create a form definition, author a draft version, publish it, and activate it for a runtime target through a clearly separated two-step workflow.
- **SC-004**: Published form versions remain immutable while new draft versions can be created for future changes.

## Delivery Mapping *(mandatory)*

- **Primary issue title**: Define metadata vocabularies and configurable form schema foundation
- **Planned branch label**: `feat/metadata-vocabularies-and-form-schemas`
- **Expected PR scope**: specification-first design slice followed by reviewable implementation slices
- **Blocking dependencies**: none for the specification slice; later implementation will likely depend on metadata domain migration and API/UI slices
