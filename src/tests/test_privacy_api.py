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
        tenant_a = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f"Tenant A {uuid.uuid4().hex[:6]}")
        tenant_a.save()
        Domain(domain=host_a, tenant=tenant_a, is_primary=True).save()
        tenant_b = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f"Tenant B {uuid.uuid4().hex[:6]}")
        tenant_b.save()
        Domain(domain=host_b, tenant=tenant_b, is_primary=True).save()
    return host_a, host_b


@pytest.mark.django_db(transaction=True)
def test_privacy_profile_and_consent_lifecycle():
    host, _ = _create_tenants()
    client = Client()
    created = client.post(
        '/api/v1/privacy/profiles',
        data=json.dumps(
            {
                'name': 'PII profile',
                'lawful_basis': 'consent',
                'consent_required': True,
                'privacy_flags': ['contains_pii'],
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert created.status_code == 201
    profile_id = created.json()['id']
    assert created.json()['consent_state'] == 'unknown'

    listed = client.get('/api/v1/privacy/profiles', HTTP_HOST=host)
    assert listed.status_code == 200
    assert len(listed.json()['items']) == 1

    updated = client.patch(
        f'/api/v1/privacy/profiles/{profile_id}',
        data=json.dumps({'privacy_flags': ['contains_pii', 'restricted_transfer']}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert updated.status_code == 200
    assert updated.json()['privacy_flags'] == ['contains_pii', 'restricted_transfer']

    consent = client.post(
        '/api/v1/privacy/consent-events',
        data=json.dumps({'profile_id': profile_id, 'consent_state': 'granted', 'reason': 'user acceptance'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert consent.status_code == 201
    assert consent.json()['consent_state'] == 'granted'

    events = client.get(f'/api/v1/privacy/consent-events?profile_id={profile_id}', HTTP_HOST=host)
    assert events.status_code == 200
    assert len(events.json()['items']) == 1


@pytest.mark.django_db(transaction=True)
def test_privacy_is_tenant_scoped():
    host_a, host_b = _create_tenants()
    client = Client()
    created = client.post(
        '/api/v1/privacy/profiles',
        data=json.dumps({'name': 'Tenant A profile', 'lawful_basis': 'contract'}),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert created.status_code == 201
    profile_id = created.json()['id']

    assert len(client.get('/api/v1/privacy/profiles', HTTP_HOST=host_a).json()['items']) == 1
    assert client.get('/api/v1/privacy/profiles', HTTP_HOST=host_b).json()['items'] == []
    assert client.get(f'/api/v1/privacy/profiles/{profile_id}', HTTP_HOST=host_b).status_code == 404
    assert (
        client.post(
            '/api/v1/privacy/consent-events',
            data=json.dumps({'profile_id': profile_id, 'consent_state': 'granted'}),
            content_type='application/json',
            HTTP_HOST=host_b,
        ).status_code
        == 404
    )
    assert client.get('/api/v1/privacy/actions', HTTP_HOST=host_b).json()['items'] == []


@pytest.mark.django_db(transaction=True)
def test_privacy_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    host, _ = _create_tenants()
    client = Client()

    denied_create = client.post(
        '/api/v1/privacy/profiles',
        data=json.dumps({'name': 'P', 'lawful_basis': 'contract'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_create.status_code == 403

    created = client.post(
        '/api/v1/privacy/profiles',
        data=json.dumps({'name': 'P', 'lawful_basis': 'contract'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='policy.admin',
    )
    assert created.status_code == 201
    profile_id = created.json()['id']

    denied_read = client.get('/api/v1/privacy/profiles', HTTP_HOST=host)
    assert denied_read.status_code == 403
    allowed_read = client.get('/api/v1/privacy/profiles', HTTP_HOST=host, HTTP_X_USER_ROLES='catalog.reader')
    assert allowed_read.status_code == 200

    denied_patch = client.patch(
        f'/api/v1/privacy/profiles/{profile_id}',
        data=json.dumps({'name': 'P2'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_patch.status_code == 403

    allowed_patch = client.patch(
        f'/api/v1/privacy/profiles/{profile_id}',
        data=json.dumps({'name': 'P2'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert allowed_patch.status_code == 200

    denied_consent = client.post(
        '/api/v1/privacy/consent-events',
        data=json.dumps({'profile_id': profile_id, 'consent_state': 'withdrawn'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_consent.status_code == 403

    created_action = client.post(
        '/api/v1/privacy/actions',
        data=json.dumps({'profile_id': profile_id, 'action_type': 'policy.re_evaluate'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='policy.admin',
    )
    assert created_action.status_code == 201
    action_id = created_action.json()['id']

    denied_decision = client.post(
        f'/api/v1/privacy/actions/{action_id}/decision',
        data=json.dumps({'decision': 'approve'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_decision.status_code == 403

    allowed_decision = client.post(
        f'/api/v1/privacy/actions/{action_id}/decision',
        data=json.dumps({'decision': 'approve'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert allowed_decision.status_code == 200


@pytest.mark.django_db(transaction=True)
def test_privacy_actions_lifecycle_from_consent_withdrawal():
    host, _ = _create_tenants()
    client = Client()
    created = client.post(
        '/api/v1/privacy/profiles',
        data=json.dumps({'name': 'PII profile', 'lawful_basis': 'consent'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    profile_id = created.json()['id']

    withdrawn = client.post(
        '/api/v1/privacy/consent-events',
        data=json.dumps(
            {
                'profile_id': profile_id,
                'consent_state': 'withdrawn',
                'reason': 'user request',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert withdrawn.status_code == 201

    actions = client.get(
        f'/api/v1/privacy/actions?profile_id={profile_id}',
        HTTP_HOST=host,
    )
    assert actions.status_code == 200
    assert len(actions.json()['items']) == 3
    action = actions.json()['items'][0]
    assert action['status'] == 'requested'

    approved = client.post(
        f"/api/v1/privacy/actions/{action['id']}/decision",
        data=json.dumps({'decision': 'approve'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert approved.status_code == 200
    assert approved.json()['status'] == 'approved'

    executed = client.post(
        f"/api/v1/privacy/actions/{action['id']}/execute",
        data=json.dumps({'evidence': {'ticket': 'PRIV-101'}}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert executed.status_code == 200
    assert executed.json()['status'] == 'executed'
    assert executed.json()['evidence'] == {'ticket': 'PRIV-101'}
