import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context
from django.db import IntegrityError

from lims.models import Country, District, Postcode, Region, Street, TanzaniaAddressSyncRun, Ward
from lims.services import process_tanzania_address_sync_run
from lims.tasks import sync_tanzania_address_run


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
        assert Country.objects.get().code == "TZ"
        assert Region.objects.get().name == "Kilimanjaro"
        assert District.objects.get().name == "Moshi"
        assert Ward.objects.get().name == "Majengo"
        assert Street.objects.get().name == "Sokoine Road"
        assert Postcode.objects.get().code == "25112"


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
    assert payload["country_code"] == "TZ"
    assert payload["processed_count"] == 0
    assert payload["failure_count"] == 0
    assert payload["progress_percent"] == 0
    assert queued["tenant_schema"] == schema_name
    assert queued["run_id"] == payload["id"]

    with schema_context(schema_name):
        run = TanzaniaAddressSyncRun.objects.get(id=payload["id"])
        assert run.triggered_by == "sync-admin"


@pytest.mark.django_db(transaction=True)
def test_tanzania_address_sync_handles_concurrent_region_insert_conflict(monkeypatch):
    pages = {
        "https://www.tanzaniapostcode.com/": '<a href="/regions/arusha">Arusha</a>',
    }

    def _fake_fetch(url: str) -> str:
        return pages[url]

    client = Client()
    _, schema_name = _create_lims_host(client, "tenant-sync-race")
    with schema_context(schema_name):
        country, _ = Country.objects.get_or_create(
            code="TZ",
            defaults={"name": "Tanzania", "slug": "tanzania"},
        )
        Region.objects.create(
            country=country,
            name="Arusha",
            slug="arusha",
            source_path="/regions/arusha",
            source_url="https://www.tanzaniapostcode.com/regions/arusha",
            is_active=True,
        )
        run = TanzaniaAddressSyncRun.objects.create(request_budget=1, throttle_seconds=1)

        original_update_or_create = Region.objects.update_or_create
        state = {"raised": False}

        def _raising_update_or_create(*args, **kwargs):
            if not state["raised"]:
                state["raised"] = True
                raise IntegrityError("duplicate key value violates unique constraint")
            return original_update_or_create(*args, **kwargs)

        monkeypatch.setattr(Region.objects, "update_or_create", _raising_update_or_create)

        result = process_tanzania_address_sync_run(run, fetcher=_fake_fetch)

        assert result["status"] == TanzaniaAddressSyncRun.Status.PAUSED
        assert Region.objects.filter(country=country, name="Arusha").count() == 1


@pytest.mark.django_db(transaction=True)
def test_tanzania_address_sync_marks_run_failed_on_unexpected_error():
    client = Client()
    _, schema_name = _create_lims_host(client, "tenant-sync-failure")
    with schema_context(schema_name):
        run = TanzaniaAddressSyncRun.objects.create(request_budget=1, throttle_seconds=1)

        def _broken_fetch(_url: str) -> str:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            process_tanzania_address_sync_run(run, fetcher=_broken_fetch)

        run.refresh_from_db()
        assert run.status == TanzaniaAddressSyncRun.Status.FAILED
        assert run.last_error == "boom"
        assert run.stats["failure_count"] == 1


@pytest.mark.django_db(transaction=True)
def test_tanzania_address_sync_coalesces_duplicate_district_links_on_same_page():
    pages = {
        "https://www.tanzaniapostcode.com/": '<a href="/regions/arusha">Arusha</a>',
        "https://www.tanzaniapostcode.com/regions/arusha": (
            '<a href="/districts/arusha-a">Arusha</a>'
            '<a href="/districts/arusha-b">Arusha</a>'
        ),
    }

    def _fake_fetch(url: str) -> str:
        return pages[url]

    client = Client()
    _, schema_name = _create_lims_host(client, "tenant-sync-duplicate-district")
    with schema_context(schema_name):
        run = TanzaniaAddressSyncRun.objects.create(request_budget=2, throttle_seconds=1)

        result = process_tanzania_address_sync_run(run, fetcher=_fake_fetch)

        assert result["status"] == TanzaniaAddressSyncRun.Status.PAUSED
        arusha_region = Region.objects.get(name="Arusha")
        districts = District.objects.filter(region=arusha_region, name="Arusha")
        assert districts.count() == 1


@pytest.mark.django_db(transaction=True)
def test_sync_task_auto_reschedules_paused_run(monkeypatch):
    client = Client()
    _, schema_name = _create_lims_host(client, "tenant-sync-auto-resume")
    scheduled: dict[str, object] = {}

    with schema_context(schema_name):
        run = TanzaniaAddressSyncRun.objects.create(
            request_budget=1,
            throttle_seconds=1,
            checkpoint={"queue": [{"level": "region", "url": "https://example.test/next"}]},
        )

        def _fake_process(_run):
            _run.status = TanzaniaAddressSyncRun.Status.PAUSED
            _run.next_not_before_at = None
            _run.save(update_fields=["status", "next_not_before_at", "updated_at"])
            return {
                "id": str(_run.id),
                "status": TanzaniaAddressSyncRun.Status.PAUSED,
                "queue_size": 1,
            }

        def _fake_apply_async(*, kwargs, countdown):
            scheduled["kwargs"] = kwargs
            scheduled["countdown"] = countdown

        monkeypatch.setattr("lims.tasks.process_tanzania_address_sync_run", _fake_process)
        monkeypatch.setattr(sync_tanzania_address_run, "apply_async", _fake_apply_async)

        sync_tanzania_address_run(tenant_schema=schema_name, run_id=str(run.id))

    assert scheduled["kwargs"] == {"tenant_schema": schema_name, "run_id": str(run.id)}
    assert scheduled["countdown"] == 1
