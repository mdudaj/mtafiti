from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from django.http import HttpRequest
from django.urls import NoReverseMatch, reverse

from core.identity import request_roles, roles_enforced
from lims.permissions import has_lims_permission


@dataclass(frozen=True)
class ShellResolutionContext:
    request: HttpRequest
    page_key: str | None
    route_name: str | None
    tenant_schema: str
    user_id: str
    roles: frozenset[str]
    page_states: frozenset[str]
    data_facts: Mapping[str, Any]


ResolutionGate = Callable[[ShellResolutionContext], bool]


@dataclass(frozen=True)
class WorkflowEntry:
    key: str
    href: str


@dataclass(frozen=True)
class WorkflowEntryDescriptor:
    key: str
    route_name: str
    permission_gate: ResolutionGate | None = None


@dataclass(frozen=True)
class NavigationDescriptor:
    section: str
    key: str
    label: str
    icon: str
    route_name: str | None = None
    workflow_key: str | None = None
    permission_gate: ResolutionGate | None = None

    def __post_init__(self) -> None:
        if bool(self.route_name) == bool(self.workflow_key):
            raise ValueError(
                "navigation descriptors must define exactly one of route_name or workflow_key"
            )


@dataclass(frozen=True)
class ActionDescriptor:
    key: str
    title: str
    description: str
    icon: str
    route_name: str | None = None
    workflow_key: str | None = None
    permission_gate: ResolutionGate | None = None
    enabled_gate: ResolutionGate | None = None
    data_gate: ResolutionGate | None = None
    status: str | None = None
    sequence: int | None = None
    primary_action: bool = False
    required_states: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if bool(self.route_name) == bool(self.workflow_key):
            raise ValueError(
                "action descriptors must define exactly one of route_name or workflow_key"
            )


@dataclass(frozen=True)
class OperationPageDescriptor:
    key: str
    title: str
    route_name: str | None = None
    navigation_key: str | None = None
    action_descriptors: tuple[ActionDescriptor, ...] = ()
    fab_enabled: bool = False
    shared_action_slot_enabled: bool = False

    def __post_init__(self) -> None:
        if not self.route_name and not self.navigation_key:
            raise ValueError(
                "operation pages must define at least one of route_name or navigation_key"
            )


USER_PORTAL_NAVIGATION_DESCRIPTORS: tuple[NavigationDescriptor, ...] = (
    NavigationDescriptor(
        section="Applications",
        key="home",
        label="Home",
        icon="home",
        route_name="user_portal_dashboard_page",
    ),
    NavigationDescriptor(
        section="Applications",
        key="printing",
        label="Operations printing",
        icon="print",
        route_name="ui_operations_printing_page",
        permission_gate=lambda context: can_view_user_portal_operations_link(context),
    ),
)


WORKSPACE_NAVIGATION_DESCRIPTORS: tuple[NavigationDescriptor, ...] = (
    *USER_PORTAL_NAVIGATION_DESCRIPTORS,
    NavigationDescriptor(
        section="LIMS",
        key="lims-dashboard",
        label="Dashboard",
        icon="dashboard",
        route_name="lims_dashboard_page",
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.dashboard.view"
        ),
    ),
    NavigationDescriptor(
        section="LIMS",
        key="lims-tasks",
        label="Tasks",
        icon="task",
        route_name="lims_task_inbox_page",
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.workflow_task.view"
        ),
    ),
    NavigationDescriptor(
        section="LIMS",
        key="lims-reference",
        label="Reference",
        icon="globe_location_pin",
        route_name="lims_reference_page",
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.reference.view"
        ),
    ),
    NavigationDescriptor(
        section="LIMS",
        key="lims-metadata",
        label="Metadata",
        icon="schema",
        route_name="lims_metadata_page",
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.metadata.view"
        ),
    ),
    NavigationDescriptor(
        section="LIMS",
        key="lims-biospecimens",
        label="Biospecimens",
        icon="biotech",
        route_name="lims_biospecimens_page",
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.artifact.view"
        ),
    ),
    NavigationDescriptor(
        section="LIMS",
        key="lims-receiving",
        label="Receiving",
        icon="inventory_2",
        route_name="lims_receiving_page",
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.artifact.view"
        ),
    ),
    NavigationDescriptor(
        section="LIMS",
        key="lims-processing",
        label="Processing",
        icon="science",
        route_name="lims_processing_page",
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.artifact.view"
        ),
    ),
    NavigationDescriptor(
        section="LIMS",
        key="lims-storage",
        label="Storage",
        icon="inventory",
        route_name="lims_storage_inventory_page",
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.storage.view"
        )
        or has_lims_permission_in_context(context, "lims.inventory.view"),
    ),
)


OPERATIONS_NAVIGATION_DESCRIPTORS: tuple[NavigationDescriptor, ...] = (
    NavigationDescriptor(
        section="Applications",
        key="dashboard",
        label="Dashboard",
        icon="dashboard",
        route_name="ui_operations_dashboard_page",
        permission_gate=lambda context: can_view_operations_shell(context),
    ),
    NavigationDescriptor(
        section="Applications",
        key="stewardship",
        label="Stewardship",
        icon="fact_check",
        route_name="ui_operations_stewardship_page",
        permission_gate=lambda context: can_view_operations_shell(context),
    ),
    NavigationDescriptor(
        section="Applications",
        key="orchestration",
        label="Orchestration",
        icon="account_tree",
        route_name="ui_operations_orchestration_page",
        permission_gate=lambda context: can_view_operations_shell(context),
    ),
    NavigationDescriptor(
        section="Applications",
        key="printing",
        label="Printing",
        icon="print",
        route_name="ui_operations_printing_page",
        permission_gate=lambda context: can_view_operations_shell(context),
    ),
    NavigationDescriptor(
        section="Applications",
        key="agent",
        label="Agent runs",
        icon="smart_toy",
        route_name="ui_operations_agent_page",
        permission_gate=lambda context: can_view_operations_shell(context),
    ),
)


WORKFLOW_ENTRY_DESCRIPTORS: tuple[WorkflowEntryDescriptor, ...] = (
    WorkflowEntryDescriptor(
        key="sample-accession-reference",
        route_name="lims_reference_sample_accession_page",
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.reference.view"
        ),
    ),
)


REFERENCE_ACTION_DESCRIPTORS: tuple[ActionDescriptor, ...] = (
    ActionDescriptor(
        key="reference-create-lab",
        title="Create lab",
        description="Register one tenant lab at a time using a dedicated lab form.",
        icon="add_business",
        route_name="lims_reference_create_lab_page",
        sequence=10,
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.reference.manage"
        ),
    ),
    ActionDescriptor(
        key="reference-create-study",
        title="Create study",
        description="Create one study and optionally attach its lead lab.",
        icon="schema",
        route_name="lims_reference_create_study_page",
        sequence=20,
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.reference.manage"
        ),
    ),
    ActionDescriptor(
        key="reference-create-site",
        title="Create site",
        description="Register one field or collection site and link it to study and lab selectors.",
        icon="location_city",
        route_name="lims_reference_create_site_page",
        sequence=30,
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.reference.manage"
        ),
    ),
    ActionDescriptor(
        key="reference-address-sync",
        title="Run geography sync",
        description="Start the Tanzania-backed geography import from a single sync action page.",
        icon="sync",
        route_name="lims_reference_address_sync_page",
        sequence=40,
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.reference.manage"
        ),
    ),
    ActionDescriptor(
        key="reference-sample-accession",
        title="Provision sample accession",
        description="Provision and inspect the canonical sample accession reference bundle that governs runtime execution across receiving adapters.",
        icon="conversion_path",
        workflow_key="sample-accession-reference",
        sequence=50,
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.reference.manage"
        ),
    ),
)


REFERENCE_OPERATION_PAGE_DESCRIPTOR = OperationPageDescriptor(
    key="lims-reference",
    title="Reference and geography",
    route_name="lims_reference_page",
    navigation_key="lims-reference",
    action_descriptors=REFERENCE_ACTION_DESCRIPTORS,
)


TASK_INBOX_ACTION_DESCRIPTORS: tuple[ActionDescriptor, ...] = (
    ActionDescriptor(
        key="task-open-receiving",
        title="Open receiving",
        description="Use the receiving launchpad while accession intake remains a transitional task-entry surface.",
        icon="inventory_2",
        route_name="lims_receiving_page",
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.artifact.view"
        ),
    ),
    ActionDescriptor(
        key="task-inspect-operations",
        title="Inspect operations",
        description="Review governed operation bundles and runtime history behind the current inbox items.",
        icon="conversion_path",
        workflow_key="sample-accession-reference",
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.reference.view"
        ),
    ),
)


TASK_INBOX_OPERATION_PAGE_DESCRIPTOR = OperationPageDescriptor(
    key="lims-tasks",
    title="Workflow task inbox",
    route_name="lims_task_inbox_page",
    navigation_key="lims-tasks",
    action_descriptors=TASK_INBOX_ACTION_DESCRIPTORS,
    shared_action_slot_enabled=True,
)


METADATA_ACTION_DESCRIPTORS: tuple[ActionDescriptor, ...] = (
    ActionDescriptor(
        key="metadata-create-vocabulary",
        title="Create vocabulary",
        description="Seed one controlled vocabulary from a dedicated create form.",
        icon="list_alt",
        route_name="lims_metadata_create_vocabulary_page",
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.metadata.manage"
        ),
    ),
    ActionDescriptor(
        key="metadata-create-schema",
        title="Create form + draft",
        description="Define form metadata first, then build the initial draft version with version-owned fields.",
        icon="schema",
        route_name="lims_metadata_create_schema_page",
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.metadata.manage"
        ),
    ),
    ActionDescriptor(
        key="metadata-create-binding",
        title="Create binding",
        description="Attach one published schema version to one sample type or workflow target.",
        icon="link",
        route_name="lims_metadata_create_binding_page",
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.metadata.manage"
        ),
    ),
    ActionDescriptor(
        key="metadata-publish-version",
        title="Publish version",
        description="Promote one draft schema version without mixing publishing with binding creation.",
        icon="publish",
        route_name="lims_metadata_publish_version_page",
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.metadata.manage"
        ),
    ),
)


RECEIVING_ACTION_DESCRIPTORS: tuple[ActionDescriptor, ...] = (
    ActionDescriptor(
        key="receiving-single",
        title="Single sample receipt",
        description="Launch the governed Sample Accession runtime from the single-sample receiving adapter, including QC and storage or rejection capture.",
        icon="move_to_inbox",
        route_name="lims_receiving_single_page",
        sequence=10,
        primary_action=True,
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.artifact.view"
        ),
    ),
    ActionDescriptor(
        key="receiving-batch",
        title="Batch manifest receipt",
        description="Launch governed Sample Accession runs from a batch manifest import with receipt, QC, and storage or rejection columns.",
        icon="upload_file",
        route_name="lims_receiving_batch_page",
        sequence=20,
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.artifact.view"
        ),
    ),
    ActionDescriptor(
        key="receiving-edc-import",
        title="Retrieve from EDC",
        description="Launch the governed Sample Accession runtime from an EDC-linked receiving adapter after import, QC, and storage or rejection capture.",
        icon="cloud_download",
        route_name="lims_receiving_edc_import_page",
        sequence=30,
        permission_gate=lambda context: has_lims_permission_in_context(
            context, "lims.artifact.view"
        ),
    ),
)


RECEIVING_OPERATION_PAGE_DESCRIPTOR = OperationPageDescriptor(
    key="lims-receiving",
    title="Receiving and accessioning",
    route_name="lims_receiving_page",
    navigation_key="lims-receiving",
    action_descriptors=RECEIVING_ACTION_DESCRIPTORS,
    fab_enabled=True,
    shared_action_slot_enabled=True,
)


STORAGE_ACTION_DESCRIPTORS: tuple[ActionDescriptor, ...] = (
    ActionDescriptor(
        key="storage-create-location",
        title="Create storage location",
        description="Build the storage hierarchy one node at a time so facilities, equipment, containers, and positions stay valid.",
        icon="add_home_work",
        route_name="lims_storage_create_location_page",
        sequence=10,
        enabled_gate=lambda context: has_lims_permission_in_context(
            context, "lims.storage.manage"
        ),
    ),
    ActionDescriptor(
        key="storage-record-placement",
        title="Record specimen placement",
        description="Log a biospecimen or pool placement event against the immutable storage history ledger.",
        icon="move_item",
        route_name="lims_storage_create_placement_page",
        sequence=20,
        required_states=("has-storage-locations",),
        data_gate=lambda context: bool(
            context.data_facts.get("has_placeable_artifacts")
        ),
        enabled_gate=lambda context: has_lims_permission_in_context(
            context, "lims.storage.manage"
        ),
    ),
    ActionDescriptor(
        key="storage-create-material",
        title="Create inventory material",
        description="Register consumables, kits, reagents, labels, and other reusable catalog entries.",
        icon="inventory_2",
        route_name="lims_storage_create_material_page",
        sequence=30,
        enabled_gate=lambda context: has_lims_permission_in_context(
            context, "lims.inventory.manage"
        ),
    ),
    ActionDescriptor(
        key="storage-receive-lot",
        title="Receive inventory lot",
        description="Capture lot receipt, storage, expiry, and opening stock in one dedicated lot form.",
        icon="local_shipping",
        route_name="lims_storage_create_lot_page",
        sequence=40,
        required_states=("has-inventory-materials",),
        enabled_gate=lambda context: has_lims_permission_in_context(
            context, "lims.inventory.manage"
        ),
    ),
    ActionDescriptor(
        key="storage-record-transaction",
        title="Record stock transaction",
        description="Post adjustments, reservations, releases, transfers, consumptions, and disposals to the lot ledger.",
        icon="sync_alt",
        route_name="lims_storage_create_transaction_page",
        sequence=50,
        required_states=("has-active-lots",),
        enabled_gate=lambda context: has_lims_permission_in_context(
            context, "lims.inventory.manage"
        ),
    ),
)


STORAGE_OPERATION_PAGE_DESCRIPTOR = OperationPageDescriptor(
    key="lims-storage",
    title="Storage and inventory administration",
    route_name="lims_storage_inventory_page",
    navigation_key="lims-storage",
    action_descriptors=STORAGE_ACTION_DESCRIPTORS,
    fab_enabled=True,
)


LIMS_DASHBOARD_ACTION_DESCRIPTORS: tuple[ActionDescriptor, ...] = (
    ActionDescriptor(
        key="task-inbox",
        title="Task inbox",
        description="Review open runtime work, approval queues, and the next governed step for each operation run.",
        icon="task",
        route_name="lims_task_inbox_page",
        enabled_gate=lambda context: has_lims_permission_in_context(
            context, "lims.workflow_task.view"
        ),
    ),
    ActionDescriptor(
        key="reference",
        title="Reference data",
        description="Manage labs, studies, sites, and address sync runs for the tenant.",
        icon="globe_location_pin",
        route_name="lims_reference_page",
        enabled_gate=lambda context: has_lims_permission_in_context(
            context, "lims.reference.view"
        ),
    ),
    ActionDescriptor(
        key="metadata",
        title="Metadata schemas",
        description="Define vocabularies, fields, schemas, and published bindings for configurable forms.",
        icon="schema",
        route_name="lims_metadata_page",
        enabled_gate=lambda context: has_lims_permission_in_context(
            context, "lims.metadata.view"
        ),
    ),
    ActionDescriptor(
        key="biospecimens",
        title="Biospecimens",
        description="Register sample types, create specimens, and assemble pools for downstream workflow steps.",
        icon="biotech",
        route_name="lims_biospecimens_page",
        enabled_gate=lambda context: has_lims_permission_in_context(
            context, "lims.artifact.view"
        ),
    ),
    ActionDescriptor(
        key="receiving",
        title="Receiving",
        description="Receive single samples, track manifests, and capture discrepancy workflows.",
        icon="inventory_2",
        route_name="lims_receiving_page",
        enabled_gate=lambda context: has_lims_permission_in_context(
            context, "lims.artifact.view"
        ),
    ),
    ActionDescriptor(
        key="processing",
        title="Processing",
        description="Create plate-based batches, review assignments, and trigger worksheet print jobs.",
        icon="science",
        route_name="lims_processing_page",
        enabled_gate=lambda context: has_lims_permission_in_context(
            context, "lims.artifact.view"
        ),
    ),
    ActionDescriptor(
        key="storage",
        title="Storage and inventory",
        description="Administer storage hierarchies, specimen placement, consumable materials, and stock-ledger activity.",
        icon="inventory",
        route_name="lims_storage_inventory_page",
        enabled_gate=lambda context: has_lims_permission_in_context(
            context, "lims.storage.view"
        )
        or has_lims_permission_in_context(context, "lims.inventory.view"),
    ),
)


OPERATIONS_DASHBOARD_ACTION_DESCRIPTORS: tuple[ActionDescriptor, ...] = (
    ActionDescriptor(
        key="stewardship",
        title="Stewardship",
        description="Open the stewardship workbench from the summary dashboard.",
        icon="fact_check",
        route_name="ui_operations_stewardship_page",
    ),
    ActionDescriptor(
        key="orchestration",
        title="Orchestration",
        description="Open the orchestration monitor from the summary dashboard.",
        icon="account_tree",
        route_name="ui_operations_orchestration_page",
    ),
    ActionDescriptor(
        key="agent",
        title="Agents",
        description="Open the agent monitor from the summary dashboard.",
        icon="smart_toy",
        route_name="ui_operations_agent_page",
    ),
    ActionDescriptor(
        key="printing",
        title="Printing",
        description="Open the printing monitor from the summary dashboard.",
        icon="print",
        route_name="ui_operations_printing_page",
    ),
)


def can_view_operations_shell(context: ShellResolutionContext) -> bool:
    if not roles_enforced():
        return True
    return bool(
        context.roles
        & {"catalog.reader", "catalog.editor", "policy.admin", "tenant.admin"}
    )


def can_view_user_portal_operations_link(context: ShellResolutionContext) -> bool:
    if not roles_enforced():
        return True
    return bool(context.roles & {"catalog.editor", "policy.admin", "tenant.admin"})


def has_lims_permission_in_context(
    context: ShellResolutionContext, permission_key: str
) -> bool:
    if not roles_enforced():
        return True
    return has_lims_permission(set(context.roles), permission_key)


def build_resolution_context(
    request: HttpRequest,
    *,
    page_key: str | None = None,
    route_name: str | None = None,
    page_states: Iterable[str] | None = None,
    data_facts: Mapping[str, Any] | None = None,
) -> ShellResolutionContext:
    tenant = getattr(request, "tenant", None)
    return ShellResolutionContext(
        request=request,
        page_key=page_key,
        route_name=route_name,
        tenant_schema=getattr(tenant, "schema_name", "public"),
        user_id=(request.headers.get("X-User-Id") or "anonymous").strip(),
        roles=frozenset(request_roles(request)),
        page_states=frozenset(page_states or ()),
        data_facts=dict(data_facts or {}),
    )


def resolve_workflow_entries(
    request: HttpRequest,
    *,
    page_key: str | None = None,
    route_name: str | None = None,
    descriptors: Iterable[WorkflowEntryDescriptor] | None = None,
) -> dict[str, WorkflowEntry]:
    context = build_resolution_context(
        request,
        page_key=page_key,
        route_name=route_name,
    )
    resolved: dict[str, WorkflowEntry] = {}
    for descriptor in descriptors or WORKFLOW_ENTRY_DESCRIPTORS:
        if descriptor.permission_gate is not None and not descriptor.permission_gate(
            context
        ):
            continue
        href = _reverse_route(descriptor.route_name)
        if href is None:
            continue
        resolved[descriptor.key] = WorkflowEntry(key=descriptor.key, href=href)
    return resolved


def resolve_navigation(
    request: HttpRequest,
    *,
    active_key: str,
    page_key: str | None = None,
    route_name: str | None = None,
    descriptors: Iterable[NavigationDescriptor],
    workflow_entries: Mapping[str, WorkflowEntry] | None = None,
) -> dict[str, Any]:
    context = build_resolution_context(
        request,
        page_key=page_key,
        route_name=route_name,
    )
    effective_workflow_entries = workflow_entries or resolve_workflow_entries(
        request,
        page_key=page_key,
        route_name=route_name,
    )
    sections: list[dict[str, Any]] = []
    section_index: dict[str, dict[str, Any]] = {}
    for descriptor in descriptors:
        if descriptor.permission_gate is not None and not descriptor.permission_gate(
            context
        ):
            continue
        href = _resolve_descriptor_href(
            descriptor.route_name,
            descriptor.workflow_key,
            effective_workflow_entries,
        )
        if href is None:
            continue
        section = section_index.get(descriptor.section)
        if section is None:
            section = {"label": descriptor.section, "items": []}
            section_index[descriptor.section] = section
            sections.append(section)
        section["items"].append(
            {
                "key": descriptor.key,
                "label": descriptor.label,
                "icon": descriptor.icon,
                "href": href,
                "is_active": descriptor.key == active_key,
            }
        )
    return {"sections": sections}


def with_navigation(
    payload: Mapping[str, Any], navigation: Mapping[str, Any]
) -> dict[str, Any]:
    return {**payload, "navigation": dict(navigation)}


def resolve_action_descriptors(
    request: HttpRequest,
    *,
    descriptors: Iterable[ActionDescriptor],
    page_key: str | None = None,
    route_name: str | None = None,
    page_states: Iterable[str] | None = None,
    data_facts: Mapping[str, Any] | None = None,
    workflow_entries: Mapping[str, WorkflowEntry] | None = None,
) -> list[dict[str, Any]]:
    return resolve_operation_cards(
        request,
        descriptors=descriptors,
        page_key=page_key,
        route_name=route_name,
        page_states=page_states,
        data_facts=data_facts,
        workflow_entries=workflow_entries,
    )


def resolve_operation_page(
    request: HttpRequest,
    *,
    descriptor: OperationPageDescriptor,
    page_states: Iterable[str] | None = None,
    data_facts: Mapping[str, Any] | None = None,
    allowed_action_payloads: Iterable[Mapping[str, Any]] | None = None,
    workflow_entries: Mapping[str, WorkflowEntry] | None = None,
) -> dict[str, Any]:
    action_cards = resolve_operation_cards(
        request,
        descriptors=descriptor.action_descriptors,
        page_key=descriptor.key,
        route_name=descriptor.route_name,
        page_states=page_states,
        data_facts=data_facts,
        allowed_action_payloads=allowed_action_payloads,
        workflow_entries=workflow_entries,
    )
    return {
        "key": descriptor.key,
        "title": descriptor.title,
        "route_name": descriptor.route_name,
        "navigation_key": descriptor.navigation_key,
        "action_cards": action_cards,
        "shared_action_slot": derive_operation_action_slot(
            action_cards,
            enabled=descriptor.shared_action_slot_enabled,
        ),
        "floating_action": derive_operation_fab(
            action_cards,
            enabled=descriptor.fab_enabled,
        ),
    }


def derive_operation_action_slot(
    action_cards: Iterable[Mapping[str, Any]], *, enabled: bool
) -> list[dict[str, Any]]:
    if not enabled:
        return []
    return [
        dict(card)
        for card in action_cards
        if card.get("enabled", True) and (card.get("resolved_url") or card.get("href"))
    ]


def derive_operation_fab(
    action_cards: Iterable[Mapping[str, Any]], *, enabled: bool
) -> dict[str, Any] | None:
    if not enabled:
        return None
    allowed_cards = [
        card
        for card in action_cards
        if card.get("enabled", True) and (card.get("resolved_url") or card.get("href"))
    ]
    if not allowed_cards:
        return None
    primary_card = next(
        (card for card in allowed_cards if card.get("primary_action")),
        allowed_cards[0],
    )
    href = primary_card.get("resolved_url") or primary_card.get("href")
    if not href:
        return None
    return {
        "key": primary_card["key"],
        "title": primary_card["title"],
        "icon": primary_card.get("icon") or "arrow_forward",
        "href": href,
        "resolved_url": href,
    }


def resolve_operation_cards(
    request: HttpRequest,
    *,
    descriptors: Iterable[ActionDescriptor] = (),
    page_key: str | None = None,
    route_name: str | None = None,
    page_states: Iterable[str] | None = None,
    data_facts: Mapping[str, Any] | None = None,
    allowed_action_payloads: Iterable[Mapping[str, Any]] | None = None,
    workflow_entries: Mapping[str, WorkflowEntry] | None = None,
) -> list[dict[str, Any]]:
    context = build_resolution_context(
        request,
        page_key=page_key,
        route_name=route_name,
        page_states=page_states,
        data_facts=data_facts,
    )
    effective_workflow_entries = workflow_entries or resolve_workflow_entries(
        request,
        page_key=page_key,
        route_name=route_name,
    )
    items: list[tuple[tuple[int, int], dict[str, Any]]] = []
    for index, descriptor in enumerate(descriptors):
        if descriptor.permission_gate is not None and not descriptor.permission_gate(
            context
        ):
            continue
        if descriptor.data_gate is not None and not descriptor.data_gate(context):
            continue
        if not _matches_required_states(
            descriptor.required_states, context.page_states
        ):
            continue
        href = _resolve_descriptor_href(
            descriptor.route_name,
            descriptor.workflow_key,
            effective_workflow_entries,
        )
        if href is None:
            continue
        items.append(
            (
                _operation_card_sort_key(descriptor.sequence, index),
                {
                    "key": descriptor.key,
                    "title": descriptor.title,
                    "description": descriptor.description,
                    "icon": descriptor.icon,
                    "href": href,
                    "resolved_url": href,
                    "enabled": (
                        True
                        if descriptor.enabled_gate is None
                        else descriptor.enabled_gate(context)
                    ),
                    "status": descriptor.status,
                    "sequence": descriptor.sequence,
                    "primary_action": descriptor.primary_action,
                    "workflow_key": descriptor.workflow_key,
                    "route_name": descriptor.route_name,
                },
            )
        )
    for index, payload in enumerate(allowed_action_payloads or ()):  # pragma: no branch
        normalized = _normalize_allowed_action_payload(
            payload,
            workflow_entries=effective_workflow_entries,
            fallback_index=index + len(items),
        )
        if normalized is None:
            continue
        items.append(normalized)
    return [item for _, item in sorted(items, key=lambda entry: entry[0])]


def _resolve_descriptor_href(
    route_name: str | None,
    workflow_key: str | None,
    workflow_entries: Mapping[str, WorkflowEntry],
) -> str | None:
    if route_name:
        return _reverse_route(route_name)
    workflow_entry = workflow_entries.get(workflow_key or "")
    if workflow_entry is None:
        return None
    return workflow_entry.href or None


def _reverse_route(route_name: str) -> str | None:
    try:
        return reverse(route_name)
    except NoReverseMatch:
        return None


def _matches_required_states(
    required_states: tuple[str, ...], page_states: frozenset[str]
) -> bool:
    if not required_states:
        return True
    return bool(page_states.intersection(required_states))


def _operation_card_sort_key(
    sequence: int | None, fallback_index: int
) -> tuple[int, int]:
    if sequence is None:
        return (1, fallback_index)
    return (0, sequence)


def _normalize_allowed_action_payload(
    payload: Mapping[str, Any],
    *,
    workflow_entries: Mapping[str, WorkflowEntry],
    fallback_index: int,
) -> tuple[tuple[int, int], dict[str, Any]] | None:
    route_name = payload.get("route_name")
    workflow_key = payload.get("workflow_key")
    resolved_url = payload.get("resolved_url") or payload.get("href")
    if route_name and workflow_key:
        raise ValueError(
            "operation action payloads must define at most one of route_name or workflow_key"
        )
    if resolved_url is None:
        resolved_url = _resolve_descriptor_href(
            route_name, workflow_key, workflow_entries
        )
    if not resolved_url:
        return None
    sequence = payload.get("sequence")
    item = {
        "key": str(payload.get("key") or payload.get("id") or fallback_index),
        "title": str(payload.get("title") or payload.get("label") or "Action"),
        "description": str(payload.get("description") or ""),
        "icon": str(payload.get("icon") or "play_arrow"),
        "href": resolved_url,
        "resolved_url": resolved_url,
        "enabled": bool(payload.get("enabled", True)),
        "status": payload.get("status"),
        "sequence": sequence,
        "primary_action": bool(payload.get("primary_action", False)),
        "workflow_key": workflow_key,
        "route_name": route_name,
    }
    return (_operation_card_sort_key(sequence, fallback_index), item)
