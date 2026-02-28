import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

import core.events as events
from tenants.models import Domain, Tenant


def _create_tenant_host() -> str:
    host = f"tenanta-{uuid.uuid4().hex[:6]}.example"
    with schema_context('public'):
        tenant = Tenant(
            schema_name=f't_{uuid.uuid4().hex[:8]}',
            name=f"Tenant A {uuid.uuid4().hex[:6]}",
        )
        tenant.save()
        Domain(domain=host, tenant=tenant, is_primary=True).save()
    return host


@pytest.mark.django_db(transaction=True)
def test_mutating_flows_emit_schema_compliant_domain_and_audit_events(monkeypatch):
    host = _create_tenant_host()
    client = Client()
    emitted: list[dict] = []

    def fake_publish_event(*, exchange, routing_key, payload, rabbitmq_url=None):
        emitted.append({'exchange': exchange, 'routing_key': routing_key, 'payload': payload})

    monkeypatch.setenv('RABBITMQ_URL', 'amqp://test/')
    monkeypatch.setenv('EDMP_EVENT_EXCHANGE', 'edmp.events')
    monkeypatch.setattr(events, 'publish_event', fake_publish_event)

    workflow_definition = client.post(
        '/api/v1/workflows/definitions',
        data=json.dumps({'name': 'Policy Review', 'domain_ref': 'policy'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='policy.admin',
        HTTP_X_USER_ID='user-1',
    )
    assert workflow_definition.status_code == 201

    stewardship_item = client.post(
        '/api/v1/stewardship/items',
        data=json.dumps({'item_type': 'quality_exception', 'subject_ref': 'asset:db.orders'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
        HTTP_X_USER_ID='user-1',
    )
    assert stewardship_item.status_code == 201

    agent_run = client.post(
        '/api/v1/agent/runs',
        data=json.dumps({'prompt': 'summarize', 'allowed_tools': ['catalog.search']}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
        HTTP_X_USER_ID='user-1',
    )
    assert agent_run.status_code == 201

    ingestion = client.post(
        '/api/v1/ingestions',
        data=json.dumps({'connector': 'dbt', 'source': {}}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
        HTTP_X_USER_ID='user-1',
    )
    assert ingestion.status_code == 201

    orchestration_workflow = client.post(
        '/api/v1/orchestration/workflows',
        data=json.dumps(
            {
                'name': 'sync',
                'steps': [{'step_id': 's1', 'ingestion_id': ingestion.json()['id']}],
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='policy.admin',
        HTTP_X_USER_ID='user-1',
    )
    assert orchestration_workflow.status_code == 201

    for item in emitted:
        events.validate_event_payload(item['payload'])

    event_types = [item['payload']['event_type'] for item in emitted]
    assert any(event_type.startswith('workflow.') for event_type in event_types)
    assert any(event_type.startswith('stewardship.item.') for event_type in event_types)
    assert any(event_type.startswith('agent.run.') for event_type in event_types)
    assert any(event_type.startswith('orchestration.workflow.') for event_type in event_types)
    assert any(event_type.startswith('audit.') for event_type in event_types)
