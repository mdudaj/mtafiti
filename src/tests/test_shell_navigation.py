import pytest
from django.test import RequestFactory
from django.urls import reverse

from core.navigation import (
    ActionDescriptor,
    NavigationDescriptor,
    OperationPageDescriptor,
    WorkflowEntry,
    resolve_action_descriptors,
    resolve_navigation,
    resolve_operation_cards,
    resolve_operation_page,
)


def test_navigation_descriptor_requires_exactly_one_target():
    with pytest.raises(ValueError):
        NavigationDescriptor(
            section="Applications",
            key="invalid",
            label="Invalid",
            icon="block",
        )

    with pytest.raises(ValueError):
        NavigationDescriptor(
            section="Applications",
            key="invalid",
            label="Invalid",
            icon="block",
            route_name="user_portal_dashboard_page",
            workflow_key="workflow-entry",
        )


def test_resolve_navigation_excludes_disallowed_and_unresolved_descriptors():
    request = RequestFactory().get("/")
    user_portal_url = reverse("user_portal_dashboard_page")
    navigation = resolve_navigation(
        request,
        active_key="home",
        descriptors=(
            NavigationDescriptor(
                section="Applications",
                key="home",
                label="Home",
                icon="home",
                route_name="user_portal_dashboard_page",
            ),
            NavigationDescriptor(
                section="Applications",
                key="denied",
                label="Denied",
                icon="lock",
                route_name="user_portal_dashboard_page",
                permission_gate=lambda _request: False,
            ),
            NavigationDescriptor(
                section="Applications",
                key="missing",
                label="Missing workflow",
                icon="conversion_path",
                workflow_key="missing-workflow",
            ),
        ),
    )

    assert navigation == {
        "sections": [
            {
                "label": "Applications",
                "items": [
                    {
                        "key": "home",
                        "label": "Home",
                        "icon": "home",
                        "href": user_portal_url,
                        "is_active": True,
                    }
                ],
            }
        ]
    }


def test_resolve_navigation_supports_workflow_entries():
    request = RequestFactory().get("/")
    sample_accession_url = reverse("lims_reference_sample_accession_page")
    navigation = resolve_navigation(
        request,
        active_key="sample-accession",
        descriptors=(
            NavigationDescriptor(
                section="Workflows",
                key="sample-accession",
                label="Sample accession",
                icon="conversion_path",
                workflow_key="sample-accession",
            ),
        ),
        workflow_entries={
            "sample-accession": WorkflowEntry(
                key="sample-accession",
                href=sample_accession_url,
            )
        },
    )

    assert navigation["sections"][0]["items"][0]["href"] == sample_accession_url
    assert navigation["sections"][0]["items"][0]["is_active"] is True


def test_action_descriptor_requires_exactly_one_target():
    with pytest.raises(ValueError):
        ActionDescriptor(
            key="invalid",
            title="Invalid",
            description="Missing target",
            icon="block",
        )

    with pytest.raises(ValueError):
        ActionDescriptor(
            key="invalid",
            title="Invalid",
            description="Conflicting target",
            icon="block",
            route_name="lims_reference_page",
            workflow_key="sample-accession",
        )


def test_operation_page_descriptor_requires_surface_binding():
    with pytest.raises(ValueError):
        OperationPageDescriptor(
            key="receiving",
            title="Receiving",
        )


def test_resolve_action_descriptors_supports_workflow_entries():
    request = RequestFactory().get("/")
    sample_accession_url = reverse("lims_reference_sample_accession_page")
    actions = resolve_action_descriptors(
        request,
        descriptors=(
            ActionDescriptor(
                key="sample-accession",
                title="Provision sample accession",
                description="Open the canonical workflow entry.",
                icon="conversion_path",
                workflow_key="sample-accession",
            ),
            ActionDescriptor(
                key="missing",
                title="Missing",
                description="This should be filtered out.",
                icon="block",
                workflow_key="missing-workflow",
            ),
        ),
        workflow_entries={
            "sample-accession": WorkflowEntry(
                key="sample-accession",
                href=sample_accession_url,
            )
        },
    )

    assert actions == [
        {
            "key": "sample-accession",
            "title": "Provision sample accession",
            "description": "Open the canonical workflow entry.",
            "icon": "conversion_path",
            "href": sample_accession_url,
            "resolved_url": sample_accession_url,
            "enabled": True,
            "status": None,
            "sequence": None,
            "primary_action": False,
            "workflow_key": "sample-accession",
            "route_name": None,
        }
    ]


def test_resolve_action_descriptors_reports_enabled_state():
    request = RequestFactory().get("/")
    user_portal_url = reverse("user_portal_dashboard_page")
    actions = resolve_action_descriptors(
        request,
        descriptors=(
            ActionDescriptor(
                key="enabled",
                title="Enabled action",
                description="This action is enabled.",
                icon="check",
                route_name="user_portal_dashboard_page",
            ),
            ActionDescriptor(
                key="disabled",
                title="Disabled action",
                description="This action is disabled.",
                icon="block",
                route_name="user_portal_dashboard_page",
                enabled_gate=lambda _context: False,
            ),
        ),
    )

    assert actions == [
        {
            "key": "enabled",
            "title": "Enabled action",
            "description": "This action is enabled.",
            "icon": "check",
            "href": user_portal_url,
            "resolved_url": user_portal_url,
            "enabled": True,
            "status": None,
            "sequence": None,
            "primary_action": False,
            "workflow_key": None,
            "route_name": "user_portal_dashboard_page",
        },
        {
            "key": "disabled",
            "title": "Disabled action",
            "description": "This action is disabled.",
            "icon": "block",
            "href": user_portal_url,
            "resolved_url": user_portal_url,
            "enabled": False,
            "status": None,
            "sequence": None,
            "primary_action": False,
            "workflow_key": None,
            "route_name": "user_portal_dashboard_page",
        },
    ]


def test_resolve_operation_cards_orders_sequences_before_fallback_order():
    request = RequestFactory().get("/")
    user_portal_url = reverse("user_portal_dashboard_page")

    cards = resolve_operation_cards(
        request,
        descriptors=(
            ActionDescriptor(
                key="fallback-first",
                title="Fallback first",
                description="First authored fallback.",
                icon="looks_one",
                route_name="user_portal_dashboard_page",
            ),
            ActionDescriptor(
                key="sequenced-two",
                title="Sequenced two",
                description="Second by sequence.",
                icon="filter_2",
                route_name="user_portal_dashboard_page",
                sequence=20,
            ),
            ActionDescriptor(
                key="sequenced-one",
                title="Sequenced one",
                description="First by sequence.",
                icon="filter_1",
                route_name="user_portal_dashboard_page",
                sequence=10,
                primary_action=True,
            ),
            ActionDescriptor(
                key="fallback-second",
                title="Fallback second",
                description="Second authored fallback.",
                icon="looks_two",
                route_name="user_portal_dashboard_page",
            ),
        ),
    )

    assert [card["key"] for card in cards] == [
        "sequenced-one",
        "sequenced-two",
        "fallback-first",
        "fallback-second",
    ]
    assert cards[0]["resolved_url"] == user_portal_url
    assert cards[0]["primary_action"] is True


def test_resolve_operation_cards_filters_by_required_state_and_data_gate():
    request = RequestFactory().get("/")

    cards = resolve_operation_cards(
        request,
        descriptors=(
            ActionDescriptor(
                key="open-only",
                title="Open only",
                description="Only visible while open.",
                icon="draft",
                route_name="user_portal_dashboard_page",
                required_states=("open",),
            ),
            ActionDescriptor(
                key="data-only",
                title="Data only",
                description="Only visible when data is available.",
                icon="database",
                route_name="user_portal_dashboard_page",
                data_gate=lambda context: bool(context.data_facts.get("has_batches")),
            ),
        ),
        page_states=("open",),
        data_facts={"has_batches": False},
    )

    assert [card["key"] for card in cards] == ["open-only"]


def test_resolve_operation_cards_supports_allowed_action_payloads():
    request = RequestFactory().get("/")
    sample_accession_url = reverse("lims_reference_sample_accession_page")

    cards = resolve_operation_cards(
        request,
        allowed_action_payloads=(
            {
                "key": "missing-route",
                "title": "Missing route",
                "route_name": "does_not_exist",
            },
            {
                "key": "workflow-card",
                "title": "Workflow card",
                "description": "Uses workflow resolution.",
                "icon": "conversion_path",
                "workflow_key": "sample-accession",
                "sequence": 5,
            },
            {
                "key": "resolved-card",
                "title": "Resolved card",
                "description": "Uses a direct resolved URL.",
                "icon": "link",
                "resolved_url": reverse("user_portal_dashboard_page"),
            },
        ),
        workflow_entries={
            "sample-accession": WorkflowEntry(
                key="sample-accession",
                href=sample_accession_url,
            )
        },
    )

    assert [card["key"] for card in cards] == ["workflow-card", "resolved-card"]
    assert cards[0]["resolved_url"] == sample_accession_url


def test_resolve_operation_page_uses_descriptor_identity_for_context():
    request = RequestFactory().get("/")
    operation_page = resolve_operation_page(
        request,
        descriptor=OperationPageDescriptor(
            key="receiving-operations",
            title="Receiving operations",
            route_name="lims_receiving_page",
            action_descriptors=(
                ActionDescriptor(
                    key="stateful-card",
                    title="Stateful card",
                    description="Only visible for queued state.",
                    icon="hourglass_top",
                    route_name="lims_receiving_single_page",
                    required_states=("queued",),
                ),
            ),
        ),
        page_states=("queued",),
    )

    assert operation_page["key"] == "receiving-operations"
    assert [card["key"] for card in operation_page["action_cards"]] == ["stateful-card"]
    assert operation_page["floating_action"] is None


def test_resolve_operation_page_derives_floating_action_from_primary_allowed_card():
    request = RequestFactory().get("/")
    operation_page = resolve_operation_page(
        request,
        descriptor=OperationPageDescriptor(
            key="receiving-operations",
            title="Receiving operations",
            route_name="lims_receiving_page",
            fab_enabled=True,
            action_descriptors=(
                ActionDescriptor(
                    key="disabled-primary",
                    title="Disabled primary",
                    description="Should not become the FAB.",
                    icon="block",
                    route_name="user_portal_dashboard_page",
                    primary_action=True,
                    enabled_gate=lambda _context: False,
                ),
                ActionDescriptor(
                    key="single-receipt",
                    title="Single receipt",
                    description="Explicit primary action.",
                    icon="move_to_inbox",
                    route_name="lims_receiving_single_page",
                    primary_action=True,
                ),
                ActionDescriptor(
                    key="batch-receipt",
                    title="Batch receipt",
                    description="Secondary action.",
                    icon="upload_file",
                    route_name="lims_receiving_batch_page",
                ),
            ),
        ),
    )

    assert [card["key"] for card in operation_page["action_cards"]] == [
        "disabled-primary",
        "single-receipt",
        "batch-receipt",
    ]
    assert operation_page["floating_action"] == {
        "key": "single-receipt",
        "title": "Single receipt",
        "icon": "move_to_inbox",
        "href": reverse("lims_receiving_single_page"),
        "resolved_url": reverse("lims_receiving_single_page"),
    }


def test_resolve_operation_page_derives_shared_action_slot_from_allowed_cards():
    request = RequestFactory().get("/")
    operation_page = resolve_operation_page(
        request,
        descriptor=OperationPageDescriptor(
            key="receiving-operations",
            title="Receiving operations",
            route_name="lims_receiving_page",
            fab_enabled=True,
            shared_action_slot_enabled=True,
            action_descriptors=(
                ActionDescriptor(
                    key="disabled-primary",
                    title="Disabled primary",
                    description="Should not appear in the shared action slot.",
                    icon="block",
                    route_name="user_portal_dashboard_page",
                    primary_action=True,
                    enabled_gate=lambda _context: False,
                ),
                ActionDescriptor(
                    key="single-receipt",
                    title="Single receipt",
                    description="Explicit primary action.",
                    icon="move_to_inbox",
                    route_name="lims_receiving_single_page",
                    primary_action=True,
                ),
                ActionDescriptor(
                    key="batch-receipt",
                    title="Batch receipt",
                    description="Secondary action.",
                    icon="upload_file",
                    route_name="lims_receiving_batch_page",
                ),
            ),
        ),
    )

    assert [item["key"] for item in operation_page["shared_action_slot"]] == [
        "single-receipt",
        "batch-receipt",
    ]
    assert operation_page["shared_action_slot"][0]["resolved_url"] == reverse(
        "lims_receiving_single_page"
    )


def test_resolve_operation_page_shared_action_slot_keeps_workflow_urls_server_side():
    request = RequestFactory().get("/")
    sample_accession_url = reverse("lims_reference_sample_accession_page")
    operation_page = resolve_operation_page(
        request,
        descriptor=OperationPageDescriptor(
            key="task-inbox",
            title="Task inbox",
            route_name="lims_task_inbox_page",
            shared_action_slot_enabled=True,
            action_descriptors=(
                ActionDescriptor(
                    key="inspect-operations",
                    title="Inspect operations",
                    description="Workflow-backed action.",
                    icon="conversion_path",
                    workflow_key="sample-accession",
                ),
            ),
        ),
        workflow_entries={
            "sample-accession": WorkflowEntry(
                key="sample-accession",
                href=sample_accession_url,
            )
        },
    )

    assert operation_page["shared_action_slot"] == [
        {
            "key": "inspect-operations",
            "title": "Inspect operations",
            "description": "Workflow-backed action.",
            "icon": "conversion_path",
            "href": sample_accession_url,
            "resolved_url": sample_accession_url,
            "enabled": True,
            "status": None,
            "sequence": None,
            "primary_action": False,
            "workflow_key": "sample-accession",
            "route_name": None,
        }
    ]


def test_resolve_operation_page_suppresses_fab_without_changing_allowed_cards():
    request = RequestFactory().get("/")
    operation_page = resolve_operation_page(
        request,
        descriptor=OperationPageDescriptor(
            key="reference-operations",
            title="Reference operations",
            route_name="lims_reference_page",
            fab_enabled=False,
            action_descriptors=(
                ActionDescriptor(
                    key="create-lab",
                    title="Create lab",
                    description="Route backed.",
                    icon="add_business",
                    route_name="lims_reference_create_lab_page",
                ),
                ActionDescriptor(
                    key="sample-accession",
                    title="Provision sample accession",
                    description="Workflow backed.",
                    icon="conversion_path",
                    workflow_key="sample-accession",
                ),
            ),
        ),
        workflow_entries={
            "sample-accession": WorkflowEntry(
                key="sample-accession",
                href=reverse("lims_reference_sample_accession_page"),
            )
        },
    )

    assert [card["key"] for card in operation_page["action_cards"]] == [
        "create-lab",
        "sample-accession",
    ]
    assert operation_page["floating_action"] is None
