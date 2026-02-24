import json
import uuid

import pytest
from django.test import Client


@pytest.mark.django_db(transaction=True)
def test_tenant_admin_api_can_create_tenant_and_route_requests():
    host = f"tenant-{uuid.uuid4().hex[:6]}.example"
    control_host = 'control.example'

    client = Client()
    created = client.post(
        '/api/v1/tenants',
        data=json.dumps({'name': 'Tenant A', 'domain': host}),
        content_type='application/json',
        HTTP_HOST=control_host,
    )
    assert created.status_code == 201
    schema_name = created.json()['schema_name']

    tenants = client.get('/api/v1/tenants', HTTP_HOST=control_host)
    assert tenants.status_code == 200
    assert any(t['schema_name'] == schema_name for t in tenants.json()['items'])

    routed = client.get('/', HTTP_HOST=host)
    assert routed.status_code == 200
    assert routed.json()['schema'] == schema_name

