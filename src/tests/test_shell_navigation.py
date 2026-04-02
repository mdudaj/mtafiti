import pytest
from django.test import RequestFactory
from django.urls import reverse

from core.navigation import (
    ActionDescriptor,
    NavigationDescriptor,
    WorkflowEntry,
    resolve_action_descriptors,
    resolve_navigation,
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
            "enabled": True,
            "status": None,
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
            "enabled": True,
            "status": None,
        },
        {
            "key": "disabled",
            "title": "Disabled action",
            "description": "This action is disabled.",
            "icon": "block",
            "href": user_portal_url,
            "enabled": False,
            "status": None,
        },
    ]
