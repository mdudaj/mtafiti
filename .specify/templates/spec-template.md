# Feature Specification: [FEATURE NAME]

**Feature ID**: `[###-feature-name]`  
**Execution Branch**: `[type/slug-name]`  
**Created**: [DATE]  
**Status**: Draft  
**Input**: User description: "$ARGUMENTS"

## Repository Context *(mandatory)*

- **Service area**: [e.g. core, lims, edcs, printing]
- **Affected code paths**: [e.g. `src/lims/`, `src/core/`, `.github/scripts/`]
- **Related design docs**: [e.g. `docs/architecture.md`, `docs/lab-lims.md`]
- **Knowledge graph / skills evidence**: [relevant nodes, skills, or generated artifacts]
- **External API lookup needs**: [Context Hub lookups required, or `None`]
- **Related issues / PRs**: [existing GitHub references, or `None`]

## User Scenarios & Testing *(mandatory)*

### User Story 1 - [Brief Title] (Priority: P1)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]
2. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

### User Story 2 - [Brief Title] (Priority: P2)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

### User Story 3 - [Brief Title] (Priority: P3)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]

## Edge Cases

- What happens when [boundary condition]?
- How does the system handle [error scenario]?
- What tenant, permission, or service-routing boundary must remain intact?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST [specific capability]
- **FR-002**: System MUST [specific capability]
- **FR-003**: Users MUST be able to [key interaction]
- **FR-004**: System MUST preserve [tenant, routing, audit, or data invariant]

### Non-Goals

- [Explicitly out-of-scope item]
- [Explicitly deferred item]

### Key Entities *(include if feature involves data)*

- **[Entity 1]**: [What it represents and why it matters]
- **[Entity 2]**: [What it represents and its relationships]

## Success Criteria *(mandatory)*

- **SC-001**: [Measurable, technology-agnostic outcome]
- **SC-002**: [Measurable, technology-agnostic outcome]
- **SC-003**: [Operator, UX, or delivery metric]

## Delivery Mapping *(mandatory)*

- **Primary issue title**: [GitHub issue title derived from this spec]
- **Planned branch label**: [e.g. `feat/spec-kit-workflow`]
- **Expected PR scope**: [single slice, multi-file change, docs + script, etc.]
- **Blocking dependencies**: [other issues, migrations, or `None`]
