import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from lims.models import TanzaniaAddressSyncRun, TanzaniaDistrict, TanzaniaRegion, TanzaniaStreet, TanzaniaWard
from lims.services import process_tanzania_address_sync_run


def _create_lims_host(client: Client, route_slug: str) -> tuple[str, str]:
    control_host = "control.example"
    created_tenant = client.post(
        "/api/v1/tenants",
        data=json.dumps(
            {
                "name": f"Tenant {uuid.uuid4().hex[:6]}",
                "domain": f"tenant-{uuid.uuid4().hex[:6]}.example",
            }
        ),
        content_type="application/json",
        HTTP_HOST=control_host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert created_tenant.status_code == 201
    tenant_id = created_tenant.json()["id"]
    created_route = client.post(
        "/api/v1/tenants/services",
        data=json.dumps(
            {
                "tenant_id": tenant_id,
                "service_key": "lims",
                "tenant_slug": route_slug,
                "base_domain": "mtafiti.apps.nimr.or.tz",
            }
        ),
        content_type="application/json",
        HTTP_HOST=control_host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert created_route.status_code == 201
    host = created_route.json()["domain"]
    schema_name = client.get("/api/v1/lims/summary", HTTP_HOST=host, HTTP_X_USER_ROLES="lims.admin").json()["tenant_schema"]
    return host, schema_name


@pytest.mark.django_db(transaction=True)
def test_tanzania_address_sync_run_is_resumable_and_polite():
    pages = {
        "https://www.tanzaniapostcode.com/": '<a href="/regions/kilimanjaro">Kilimanjaro</a>',
        "https://www.tanzaniapostcode.com/regions/kilimanjaro": '<a href="/districts/moshi">Moshi</a>',
        "https://www.tanzaniapostcode.com/districts/moshi": '<a href="/wards/majengo">Majengo</a>',
        "https://www.tanzaniapostcode.com/wards/majengo": '<a href="/streets/sokoine-road">Sokoine Road</a>',
        "https://www.tanzaniapostcode.com/streets/sokoine-road": "<html><body><h1>Sokoine Road</h1><p>Postcode 25112</p></body></html>",
    }

    def _fake_fetch(url: str) -> str:
        return pages[url]

    with schema_context("public"):
        pass

    client = Client()
    _, schema_name = _create_lims_host(client, "tenant-sync")
    with schema_context(schema_name):
        run = TanzaniaAddressSyncRun.objects.create(request_budget=2, throttle_seconds=1)

        first = process_tanzania_address_sync_run(run, fetcher=_fake_fetch)
        assert first["status"] == TanzaniaAddressSyncRun.Status.PAUSED
        assert first["pages_processed"] == 2
        run.refresh_from_db()
        run.next_not_before_at = None
        run.save(update_fields=["next_not_before_at"])

        second = process_tanzania_address_sync_run(run, fetcher=_fake_fetch)
        assert second["status"] == TanzaniaAddressSyncRun.Status.PAUSED
        assert second["pages_processed"] == 4
        run.refresh_from_db()
        run.next_not_before_at = None
        run.save(update_fields=["next_not_before_at"])

        third = process_tanzania_address_sync_run(run, fetcher=_fake_fetch)
        assert third["status"] == TanzaniaAddressSyncRun.Status.COMPLETED
        assert third["pages_processed"] == 5
        assert TanzaniaRegion.objects.get().name == "Kilimanjaro"
        assert TanzaniaDistrict.objects.get().name == "Moshi"
        assert TanzaniaWard.objects.get().name == "Majengo"
        assert TanzaniaStreet.objects.get().postcode == "25112"


@pytest.mark.django_db(transaction=True)
def test_address_sync_api_creates_run_and_dispatches_task(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host, schema_name = _create_lims_host(client, "tenant-sync-api")
    queued: dict[str, str] = {}

    def _fake_delay(**kwargs):
        queued.update(kwargs)

    monkeypatch.setattr("lims.views.sync_tanzania_address_run.delay", _fake_delay)

    response = client.post(
        "/api/v1/lims/reference/address-sync-runs",
        data=json.dumps({"mode": "incremental", "request_budget": 3, "throttle_seconds": 2}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
        HTTP_X_USER_ID="sync-admin",
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["mode"] == "incremental"
    assert payload["request_budget"] == 3
    assert queued["tenant_schema"] == schema_name
    assert queued["run_id"] == payload["id"]

    with schema_context(schema_name):
        run = TanzaniaAddressSyncRun.objects.get(id=payload["id"])
        assert run.triggered_by == "sync-admin"
