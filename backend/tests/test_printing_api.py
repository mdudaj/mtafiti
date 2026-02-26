import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from tenants.models import Domain, Tenant


def _create_tenants():
    host_a = f"tenanta-{uuid.uuid4().hex[:6]}.example"
    host_b = f"tenantb-{uuid.uuid4().hex[:6]}.example"
    with schema_context('public'):
        tenant_a = Tenant(
            schema_name=f't_{uuid.uuid4().hex[:8]}',
            name=f"Tenant A {uuid.uuid4().hex[:6]}",
        )
        tenant_a.save()
        Domain(domain=host_a, tenant=tenant_a, is_primary=True).save()
        tenant_b = Tenant(
            schema_name=f't_{uuid.uuid4().hex[:8]}',
            name=f"Tenant B {uuid.uuid4().hex[:6]}",
        )
        tenant_b.save()
        Domain(domain=host_b, tenant=tenant_b, is_primary=True).save()
    return host_a, host_b


@pytest.mark.django_db(transaction=True)
def test_print_job_lifecycle():
    host, _ = _create_tenants()
    client = Client()

    created = client.post(
        '/api/v1/printing/jobs',
        data=json.dumps(
            {
                'template_ref': 'label/shipping-v1',
                'output_format': 'zpl',
                'destination': 'printer-a',
                'payload': {'order_id': 'SO-001'},
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert created.status_code == 201
    job_id = created.json()['id']
    assert created.json()['status'] == 'pending'

    retrying = client.post(
        f'/api/v1/printing/jobs/{job_id}/status',
        data=json.dumps(
            {
                'status': 'retrying',
                'retry_count': 1,
                'gateway_metadata': {'site': 'dc-a'},
                'error_message': 'spool unavailable',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert retrying.status_code == 200
    assert retrying.json()['status'] == 'retrying'
    assert retrying.json()['retry_count'] == 1

    completed = client.post(
        f'/api/v1/printing/jobs/{job_id}/status',
        data=json.dumps({'status': 'completed', 'gateway_metadata': {'driver': 'zebra'}}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert completed.status_code == 200
    assert completed.json()['status'] == 'completed'

    listed = client.get('/api/v1/printing/jobs', HTTP_HOST=host)
    assert listed.status_code == 200
    assert len(listed.json()['items']) == 1

    filtered = client.get('/api/v1/printing/jobs?status=completed', HTTP_HOST=host)
    assert filtered.status_code == 200
    assert len(filtered.json()['items']) == 1


@pytest.mark.django_db(transaction=True)
def test_print_jobs_are_tenant_scoped():
    host_a, host_b = _create_tenants()
    client = Client()

    created = client.post(
        '/api/v1/printing/jobs',
        data=json.dumps(
            {
                'template_ref': 'label/shipping-v1',
                'output_format': 'pdf',
                'destination': 'printer-a',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert created.status_code == 201
    job_id = created.json()['id']

    list_a = client.get('/api/v1/printing/jobs', HTTP_HOST=host_a)
    assert list_a.status_code == 200
    assert len(list_a.json()['items']) == 1

    list_b = client.get('/api/v1/printing/jobs', HTTP_HOST=host_b)
    assert list_b.status_code == 200
    assert list_b.json()['items'] == []

    detail_b = client.get(f'/api/v1/printing/jobs/{job_id}', HTTP_HOST=host_b)
    assert detail_b.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_printing_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    host, _ = _create_tenants()
    client = Client()

    denied_create = client.post(
        '/api/v1/printing/jobs',
        data=json.dumps(
            {
                'template_ref': 'label/shipping-v1',
                'output_format': 'zpl',
                'destination': 'printer-a',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert denied_create.status_code == 403

    created = client.post(
        '/api/v1/printing/jobs',
        data=json.dumps(
            {
                'template_ref': 'label/shipping-v1',
                'output_format': 'zpl',
                'destination': 'printer-a',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created.status_code == 201
    job_id = created.json()['id']

    denied_status = client.post(
        f'/api/v1/printing/jobs/{job_id}/status',
        data=json.dumps({'status': 'completed'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_status.status_code == 403

    allowed_status = client.post(
        f'/api/v1/printing/jobs/{job_id}/status',
        data=json.dumps({'status': 'completed'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert allowed_status.status_code == 200

    denied_read = client.get('/api/v1/printing/jobs', HTTP_HOST=host)
    assert denied_read.status_code == 403
    allowed_read = client.get(
        '/api/v1/printing/jobs',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert allowed_read.status_code == 200
