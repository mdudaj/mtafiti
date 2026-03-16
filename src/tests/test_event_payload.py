import pytest

from core.events import build_event_payload, validate_event_payload
from core.logging import correlation_id_var, request_id_var, user_id_var


def test_event_payload_contains_required_metadata_fields():
    payload = build_event_payload(event_type='print.requested', tenant_id='tenant-a', user_id='user-1')

    assert payload['tenant_id'] == 'tenant-a'
    assert payload['event_type'] == 'print.requested'
    assert payload['correlation_id']
    assert payload['timestamp']
    assert payload['user_id'] == 'user-1'


def test_event_payload_uses_request_context_defaults_when_not_explicit():
    corr_token = correlation_id_var.set('corr-ctx')
    user_token = user_id_var.set('user-ctx')
    req_token = request_id_var.set('req-ctx')
    try:
        payload = build_event_payload(event_type='print.requested', tenant_id='tenant-a')
    finally:
        correlation_id_var.reset(corr_token)
        user_id_var.reset(user_token)
        request_id_var.reset(req_token)

    assert payload['correlation_id'] == 'corr-ctx'
    assert payload['user_id'] == 'user-ctx'
    assert payload['request_id'] == 'req-ctx'


def test_event_payload_schema_validation_for_domain_and_audit_events():
    domain_payload = build_event_payload(
        event_type='agent.run.created',
        tenant_id='tenant-a',
        data={
            'id': 'a',
            'prompt': 'p',
            'allowed_tools': [],
            'timeout_seconds': 60,
            'status': 'queued',
        },
    )
    validate_event_payload(domain_payload)

    audit_payload = build_event_payload(
        event_type='audit.agent.run.created',
        tenant_id='tenant-a',
        data={
            'action': 'agent.run.created',
            'resource_type': 'agent_run',
            'resource_id': 'a',
            'details': {'status': 'queued'},
        },
    )
    validate_event_payload(audit_payload)


def test_event_payload_schema_validation_rejects_missing_required_fields():
    invalid_domain_payload = build_event_payload(
        event_type='orchestration.run.queued',
        tenant_id='tenant-a',
        data={'id': 'r1'},
    )
    with pytest.raises(ValueError):
        validate_event_payload(invalid_domain_payload)

    invalid_audit_payload = build_event_payload(
        event_type='audit.orchestration.run.queued',
        tenant_id='tenant-a',
        data={'action': 'orchestration.run.queued', 'resource_type': 'orchestration_run'},
    )
    with pytest.raises(ValueError):
        validate_event_payload(invalid_audit_payload)
