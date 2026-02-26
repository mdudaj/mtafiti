from core.events import build_event_payload
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
