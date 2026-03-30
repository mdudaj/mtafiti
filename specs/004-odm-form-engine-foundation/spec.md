# Feature Specification: ODM form engine foundation

**Feature ID**: `004-odm-form-engine-foundation`  
**Execution Branch**: `docs/odm-form-engine-foundation`  
**Created**: 2026-03-19  
**Status**: Draft  
**Input**: GitHub issue `#109` plus user clarification that Django/Viewflow/django-material are orchestration/UI layers, not the core form compiler.

## Repository Context *(mandatory)*

- **Service area**: shared `lims` / future `edcs` form-engine foundation
- **Affected code paths**: `src/lims/models.py`, `src/lims/services.py`, future shared form-engine app(s), `docs/lab-lims.md`, `docs/metadata-versioning.md`, `docs/workflow-ui.md`
- **Related design docs**: `specs/002-operation-driven-lims-edcs-foundation/spec.md`, `specs/003-operation-runtime-domain/spec.md`, `docs/metadata-versioning.md`, `docs/lab-lims.md`
- **Prior checkpoints**: `022-architecture-spec-and-skills.md`, `020-spec-first-metadata-planning.md`, `017-accession-wizard-and-metadata.md`
- **Knowledge graph / skills evidence**: `openclinica-odm-form-engine-patterns`, `viewflow-configurable-metadata-forms`, `viewflow-governed-workflow-definition-patterns`
- **External API lookup needs**: verify OpenClinica/ODM package semantics and any implementation-time parser/export details via Context Hub or curated local sources
- **Related issues / PRs**: parent issue `#107`, scoped issue `#109`, merged architecture PRs `#112` and `#113`

## Problem Statement

The current repository has tenant-scoped metadata schemas, schema versions, fields, bindings, and vocabulary APIs. Those are useful foundations, but they do not yet define a real ODM/OpenClinica-style form engine.

The missing distinction is architectural:

- Django is the application runtime boundary.
- Viewflow is the orchestration/runtime layer.
- django-material is a presentation layer.
- **The ODM engine must be a separate transformation and validation subsystem** responsible for parsing, normalizing, compiling, validating, and exporting governed form packages.

Without that separation, form semantics risk being scattered across UI code, workflow code, and ad hoc metadata JSON rather than being governed by one compiler/validator source of truth.

## Goals

- Define the ODM engine as a standalone subsystem with clear inputs, intermediate models, validation stages, and outputs.
- Define OpenClinica-style governed package semantics for forms: package metadata, sections/pages, item groups, items/questions, choice lists, stable identifiers, versioning, and artifacts.
- Define how XLSX and ODM/XML authoring/import paths feed the same canonical compiler pipeline.
- Define how orchestration and UI layers consume compiled outputs without owning form compilation logic.
- Define migration boundaries from the current metadata schema models into the new form-engine domain.

## Non-Goals

- Full parser/compiler implementation in this slice
- Full browser visual designer implementation
- Full workflow-builder semantics for branching or task assignment
- Treating ODM XML as the sole persisted runtime data model in the first implementation increment
- Moving orchestration or UI concerns into the compiler subsystem

## Architectural Position

This slice establishes five explicit layers:

1. **Authoring / Import layer**
   - spreadsheet/XLSX templates
   - ODM/XML import artifacts
   - future visual designer inputs
2. **ODM engine core**
   - parsing
   - normalization
   - canonical intermediate representation / relational model
   - semantic validation
   - compilation / projection
3. **Runtime consumption layer**
   - workflow/task binding
   - runtime submission contracts
   - operation/runtime version freeze
4. **Orchestration layer**
   - Django + Viewflow services, task routing, approvals, execution state
5. **Presentation layer**
   - django-material or other HTML/UI renderers that consume compiled definitions

The ODM engine core is the authority for form meaning. Django/Viewflow/django-material are downstream consumers, not the compiler.

## OpenClinica/ODM-inspired Engine Direction

The form engine should follow OpenClinica-style governed patterns:

- a form package is a versioned governed artifact, not just a flat list of fields
- form structure includes package metadata, sections/pages, item groups/repeats, items/questions, choice lists, and stable identifiers/OIDs
- published versions are immutable
- spreadsheet authoring remains a first-class path for large choice lists and advanced logic
- ODM/XML is a durable interchange/export contract
- runtime rendering and execution must reference compiled published versions rather than free-form draft definitions
- one governed package family may supply the full capture contract for an operation while individual workflow tasks bind only the relevant sections/groups/items
- metadata fields, outcome fields, storage-log fields, disposition-log fields, and similar operational categories should be represented within the same governed package family rather than separate ungoverned entry structures

## Compiler / Validation Pipeline

### Inputs

- `XLSXTemplateArtifact`
- `ODMXmlArtifact`
- future designer-authored draft package payloads

### Pipeline stages

1. **Artifact ingestion**
   - load and fingerprint source artifact
   - record source format and import metadata
2. **Syntactic parse**
   - parse spreadsheet tabs / XML structure into typed source objects
3. **Canonical normalization**
   - transform parsed source objects into the repository's canonical form-package model
4. **Semantic validation**
   - enforce structural, identifier, vocabulary, repeat/group, and rule constraints
5. **Compilation / projection**
   - emit runtime-friendly compiled sections/fields/widgets/contracts
   - emit exportable ODM/XML and XLSX artifacts
   - emit binding-friendly task/section/field references for workflow/runtime layers
6. **Publication freeze**
   - publish immutable compiled version and prevent silent mutation

### Outputs

- `FormPackage`
- `FormPackageVersion`
- compiled section/group/item graph
- compiled validation/edit-check rules
- compiled render projection for UI/task consumers
- export artifacts (`ODM XML`, `XLSX`, import bundle metadata)

## Repository Evidence

### Existing reusable foundations

- `MetadataSchema`, `MetadataSchemaVersion`, and `MetadataSchemaField` already show the repo has draft/published versioning and version-owned field records.
- `MetadataVocabulary*` models provide reusable controlled vocabulary infrastructure.
- `MetadataSchemaBinding` demonstrates there is already a runtime-binding concern, even though it is currently too target-key-driven.

### Current gaps

- the current metadata models do not distinguish compiler inputs from compiled outputs
- there is no explicit parse/normalize/validate/compile pipeline
- there is no package/section/group/item hierarchy matching ODM/OpenClinica structure
- there is no stable artifact model for source imports versus compiled published exports
- workflow and UI layers do not yet consume compiler-owned contracts; they currently depend on lighter metadata schema structures

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Compile governed form packages from authoring artifacts (Priority: P1)

As a form designer, I want XLSX or ODM/XML inputs to compile into one governed form-package model so authoring channels differ without changing runtime semantics.

**Independent Test**: Import an XLSX-authored form and an ODM/XML-authored form with equivalent structure, compile both, and confirm they produce the same canonical package/version shape and validation results.

**Acceptance Scenarios**:

1. **Given** a spreadsheet template is uploaded, **When** the ODM engine ingests it, **Then** the artifact is parsed and normalized into canonical package structures.
2. **Given** an ODM/XML artifact is uploaded, **When** the engine ingests it, **Then** it follows the same normalization and validation pipeline as other authoring channels.
3. **Given** equivalent authored form content, **When** compilation completes, **Then** downstream consumers see one consistent compiled contract regardless of source format.

---

### User Story 2 - Enforce semantic validation in the compiler, not in UI/orchestration layers (Priority: P1)

As a platform engineer, I want form semantics validated centrally so Viewflow tasks and HTML/UI screens do not re-implement form meaning.

**Independent Test**: Introduce invalid identifiers, broken repeat-group structure, and incompatible vocabulary bindings; verify the engine rejects publication before any workflow/UI layer can consume the definition.

**Acceptance Scenarios**:

1. **Given** a form has duplicate stable item identifiers, **When** validation runs, **Then** publication is rejected by the ODM engine.
2. **Given** a question references an invalid choice list or repeat-group structure, **When** semantic validation runs, **Then** the compiler returns explicit errors.
3. **Given** a UI renderer or workflow binder consumes the package, **When** it renders or binds the form, **Then** it relies on compiler outputs rather than re-deriving structure itself.

---

### User Story 3 - Publish immutable compiled versions for runtime use (Priority: P1)

As an administrator, I want only published compiled versions to be used by workflows and runtime capture so live operations remain stable.

**Independent Test**: Publish a compiled form package version, bind it to runtime consumers, then create a new draft and verify active runtime uses the published version until explicitly switched.

**Acceptance Scenarios**:

1. **Given** a draft package version exists, **When** it is still undergoing edits, **Then** orchestration/UI layers cannot treat it as the live runtime contract.
2. **Given** a compiled package version is published, **When** runtime consumers request form structure, **Then** they receive the immutable compiled projection.
3. **Given** a newer draft or published version later exists, **When** historical submissions are viewed, **Then** they still resolve against the originally published compiled version.

---

### User Story 4 - Keep orchestration and UI layers downstream of the engine (Priority: P2)

As a system architect, I want Django/Viewflow/django-material to consume compiled contracts so the form engine remains reusable across LIMS and EDCS.

**Independent Test**: Bind one compiled package version to a Viewflow-backed task and one to a server-rendered HTML preview and confirm both use the same compiler-owned field/section/rule outputs.

**Acceptance Scenarios**:

1. **Given** a workflow task references a form step, **When** it resolves capture metadata, **Then** it uses compiler-owned references to sections/groups/items rather than defining fields itself.
2. **Given** a django-material page renders a form, **When** it builds the UI, **Then** it uses compiled render projections rather than raw authoring artifacts.
3. **Given** EDCS later adopts the same engine, **When** a different UI shell is used, **Then** the compiler outputs remain reusable without moving logic into a specific frontend layer.

## Edge Cases

- How are partial imports handled when an XLSX workbook has valid sections but invalid item identifiers?
- How should source-artifact provenance be preserved when a published package version is compiled from multiple imports?
- How are stable identifiers preserved across new versions when labels or layout change but logical meaning does not?
- How should compiler outputs distinguish authoring-only hints from runtime-consumable render metadata?
- How should advanced edit checks be represented when some rules are compiler-owned and some later belong to workflow routing?
- How are deprecated vocabulary items preserved for historical rendering while excluded from new authoring choices?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define a standalone ODM form engine subsystem separate from orchestration and UI layers.
- **FR-002**: The ODM engine MUST support authoring/import inputs from XLSX and ODM/XML artifacts.
- **FR-003**: The ODM engine MUST normalize all supported input channels into one canonical form-package model.
- **FR-004**: The canonical model MUST represent package metadata, sections/pages, item groups/repeats, items/questions, choice lists, and stable identifiers/OIDs.
- **FR-005**: The ODM engine MUST perform semantic validation before publication, including structural, identifier, vocabulary, and repeat/group checks.
- **FR-006**: The ODM engine MUST compile published package versions into downstream-consumable projections for runtime binding and UI rendering.
- **FR-007**: The ODM engine MUST preserve source-artifact provenance and exportable artifacts for each package version.
- **FR-008**: The system MUST distinguish source authoring artifacts from published compiled outputs.
- **FR-009**: Published compiled package versions MUST be immutable.
- **FR-010**: Workflow/orchestration layers MUST consume compiler-owned references and outputs rather than owning form compilation logic.
- **FR-011**: UI layers MUST consume compiled render contracts rather than parsing ODM/XML or XLSX directly.
- **FR-012**: The engine MUST support version-safe historical rendering by preserving compiled published versions used at runtime.
- **FR-013**: The system MUST support migration from the current metadata schema model by identifying which existing entities become authoring assets, compiler inputs, or transitional compatibility layers.
- **FR-014**: The engine MUST remain reusable across both LIMS and EDCS without embedding workflow-runtime-only or UI-only assumptions in the compiler core.
- **FR-015**: The engine MUST support controlled vocabulary references as compiler-owned bindings, not only ad hoc UI widget metadata.
- **FR-016**: The engine MUST provide explicit publication errors and validation diagnostics suitable for governed authoring workflows.
- **FR-017**: The engine MUST support a unified governed capture contract in which one package family can represent metadata, outcome data, storage-log data, and disposition-log data for an operation while still allowing task-level subset bindings.
- **FR-018**: Runtime and UI consumers MUST NOT introduce separate non-compiler data-entry structures for categories already modeled in the published package contract.
- **FR-019**: The canonical compiler model MUST support field types, validation constraints, controlled choices, and conditional/relevance logic suitable for regulated or semi-regulated clinical and laboratory data capture.

### Non-Functional Requirements

- **NFR-001**: Compiler outputs MUST be deterministic so generated artifacts and downstream bindings remain stable in CI and runtime.
- **NFR-002**: The engine architecture MUST allow future parser adapters without redefining runtime or UI contracts.
- **NFR-003**: Separation of concerns MUST be explicit enough that code review can distinguish compiler logic from orchestration/UI logic.

### Key Entities *(include if feature involves data)*

- **FormPackage**: Stable identity of a governed form family.
- **FormPackageVersion**: Draft or published governed package revision.
- **SourceArtifact**: Uploaded XLSX, ODM/XML, or future design-source artifact with provenance metadata.
- **ParsedArtifactModel**: Typed representation of an imported source before canonical normalization.
- **CompiledFormProjection**: Engine-owned runtime/render projection emitted from a published package version.
- **CompilerDiagnostic**: Structured validation or compilation error/warning.
- **ChoiceList**: Controlled option set referenced by items/questions.
- **ItemGroup**: Group or repeat structure for related items/questions.
- **FormItem**: Compiler-owned canonical question/item definition with stable identifier.

## Proposed Mapping to Current Repository

### Reuse

- keep `MetadataVocabularyDomain`, `MetadataVocabulary`, and `MetadataVocabularyItem` as reusable vocabulary foundations
- treat `MetadataSchema`, `MetadataSchemaVersion`, and `MetadataSchemaField` as migration-source evidence for draft/published authoring patterns
- preserve tenant-scoped versioning and auditable publication behavior already demonstrated by the metadata slice

### Redefine or replace

- current metadata schema/version/field structures should not be treated as the final compiler model
- current target-key binding patterns should be replaced by compiler-owned package/version references consumed by runtime and workflow layers
- UI-facing field metadata should become compiled outputs, not the authoring source of truth

### Layer contract

- **Compiler core owns** parse, normalize, validate, compile, export
- **Workflow/orchestration owns** task progression, assignment, approvals, runtime state
- **UI owns** rendering compiled contracts and collecting submissions

## Success Criteria *(mandatory)*

- **SC-001**: The spec clearly defines the ODM engine as separate from Django/Viewflow/django-material orchestration/UI layers.
- **SC-002**: The spec defines a concrete compiler pipeline from source artifacts to canonical model to compiled outputs.
- **SC-003**: The spec explains how existing metadata models are reused as migration foundations without being mistaken for the final compiler.
- **SC-004**: The spec provides enough structure to guide an implementation slice for parser/compiler/validator work.
- **SC-005**: The spec keeps LIMS and EDCS as consumers of the same compiler-owned published package versions.
- **SC-006**: The spec makes the form-centric capture principle explicit enough to prevent fragmented operational data-entry designs in later slices.

## Delivery Mapping *(mandatory)*

- **Issue title**: Design ODM form engine foundation
- **Issue reference**: `#109`
- **Parent issue**: `#107`
- **Issue generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py issue-body specs/004-odm-form-engine-foundation`
- **PR generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py pr-body specs/004-odm-form-engine-foundation --issue-number 109`
- **Branch naming**: `docs/odm-form-engine-foundation`
