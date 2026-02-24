from core.events import build_event_payload


def test_event_payload_contains_required_metadata_fields():
    payload = build_event_payload(event_type='print.requested', tenant_id='tenant-a', user_id='user-1')

    assert payload['tenant_id'] == 'tenant-a'
    assert payload['event_type'] == 'print.requested'
    assert payload['correlation_id']
    assert payload['timestamp']
    assert payload['user_id'] == 'user-1'

