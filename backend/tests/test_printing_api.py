import base64
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


@pytest.mark.django_db(transaction=True)
def test_print_gateway_lifecycle_and_heartbeat():
    host, _ = _create_tenants()
    client = Client()

    created = client.post(
        '/api/v1/printing/gateways',
        data=json.dumps(
            {
                'gateway_ref': 'gw-dc-a-01',
                'display_name': 'DC-A Gateway',
                'status': 'offline',
                'capabilities': ['zpl'],
                'metadata': {'site': 'dc-a'},
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert created.status_code == 201
    gateway_id = created.json()['id']

    listed = client.get('/api/v1/printing/gateways', HTTP_HOST=host)
    assert listed.status_code == 200
    assert len(listed.json()['items']) == 1

    heartbeat = client.post(
        f'/api/v1/printing/gateways/{gateway_id}/heartbeat',
        data=json.dumps(
            {
                'status': 'online',
                'capabilities': ['zpl', 'pdf'],
                'metadata': {'driver': 'zebra'},
                'version': '1.2.3',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json()['status'] == 'online'
    assert heartbeat.json()['last_seen_version'] == '1.2.3'
    assert heartbeat.json()['last_heartbeat_at'] is not None

    filtered = client.get('/api/v1/printing/gateways?status=online', HTTP_HOST=host)
    assert filtered.status_code == 200
    assert len(filtered.json()['items']) == 1


@pytest.mark.django_db(transaction=True)
def test_print_gateway_role_and_token_enforcement(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    host, _ = _create_tenants()
    client = Client()

    denied_create = client.post(
        '/api/v1/printing/gateways',
        data=json.dumps({'gateway_ref': 'gw-1', 'display_name': 'GW 1'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert denied_create.status_code == 403

    created = client.post(
        '/api/v1/printing/gateways',
        data=json.dumps({'gateway_ref': 'gw-1', 'display_name': 'GW 1'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert created.status_code == 201
    gateway_id = created.json()['id']

    denied_heartbeat = client.post(
        f'/api/v1/printing/gateways/{gateway_id}/heartbeat',
        data=json.dumps({'status': 'online'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert denied_heartbeat.status_code == 403

    monkeypatch.setenv('EDMP_PRINT_GATEWAY_HEARTBEAT_TOKEN', 'secret-token')
    bad_token = client.post(
        f'/api/v1/printing/gateways/{gateway_id}/heartbeat',
        data=json.dumps({'status': 'online'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_PRINT_GATEWAY_TOKEN='wrong',
    )
    assert bad_token.status_code == 403

    ok_token = client.post(
        f'/api/v1/printing/gateways/{gateway_id}/heartbeat',
        data=json.dumps({'status': 'online'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_PRINT_GATEWAY_TOKEN='secret-token',
    )
    assert ok_token.status_code == 200


@pytest.mark.django_db(transaction=True)
def test_print_template_lifecycle_and_tenant_scope():
    host_a, host_b = _create_tenants()
    client = Client()

    created = client.post(
        '/api/v1/printing/templates',
        data=json.dumps(
            {
                'name': 'Shipping Label',
                'template_ref': 'label/shipping-v2',
                'output_format': 'zpl',
                'content': '^XA^FO20,20^FDOrder:^FS',
                'sample_payload': {'order_id': 'SO-123'},
            }
        ),
        content_type='application/json',
        HTTP_HOST=host_a,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created.status_code == 201
    assert created.json()['template_ref'] == 'label/shipping-v2'

    listed_a = client.get('/api/v1/printing/templates', HTTP_HOST=host_a)
    assert listed_a.status_code == 200
    assert len(listed_a.json()['items']) == 1

    listed_b = client.get('/api/v1/printing/templates', HTTP_HOST=host_b)
    assert listed_b.status_code == 200
    assert listed_b.json()['items'] == []


@pytest.mark.django_db(transaction=True)
def test_print_job_stores_render_preview_from_template():
    host, _ = _create_tenants()
    client = Client()
    template = client.post(
        '/api/v1/printing/templates',
        data=json.dumps(
            {
                'name': 'Preview Template',
                'template_ref': 'label/preview-v1',
                'output_format': 'pdf',
                'content': 'QR [[content]] for [[order_id]]',
                'sample_payload': {'content': 'ABC', 'order_id': 'SO-1'},
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert template.status_code == 201

    created = client.post(
        '/api/v1/printing/jobs',
        data=json.dumps(
            {
                'template_ref': 'label/preview-v1',
                'output_format': 'pdf',
                'destination': 'printer-a',
                'payload': {'content': 'XYZ', 'order_id': 'SO-2'},
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created.status_code == 201
    preview = created.json()['gateway_metadata']['render_preview']
    assert preview['engine'] == 'qrcode-reportlab-pylabels'
    assert preview['rendered'] == 'QR XYZ for SO-2'


@pytest.mark.django_db(transaction=True)
def test_zebra_batch_labels_render_preview():
    host, _ = _create_tenants()
    client = Client()
    template = client.post(
        '/api/v1/printing/templates',
        data=json.dumps(
            {
                'name': 'Zebra Participant Labels',
                'template_ref': 'zebra/participant-batch',
                'output_format': 'zpl',
                'content': '^XA^FO40,40^BQN,2,6^FDQA,[[label]]^FS^XZ',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert template.status_code == 201

    labels = [
        'MLTP2-MBY-KWJ-001',
        'MLTP2-MBY-KWJ-001-BLD-6mls',
        'MLTP2-MBY-KWJ-001-BLD-4mls',
        'MLTP2-MBY-KWJ-001-BLD-2mls',
        'MLTP2-MBY-KWJ-001-PLM1',
        'MLTP2-MBY-KWJ-001-PLM2',
        'MLTP2-MBY-KWJ-001-BLD-RNA',
        'MLTP2-MBY-KWJ-001-NA1',
        'MLTP2-MBY-KWJ-001-NA2',
    ]
    created = client.post(
        '/api/v1/printing/jobs',
        data=json.dumps(
            {
                'template_ref': 'zebra/participant-batch',
                'output_format': 'zpl',
                'destination': 'zebra-printer-1',
                'payload': {'labels': labels},
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created.status_code == 201
    preview = created.json()['gateway_metadata']['render_preview']
    assert preview['engine'] == 'zpl-inline'
    assert preview['batch_count'] == 1
    assert preview['label_count'] == 9
    assert 'MLTP2-MBY-KWJ-001-BLD-RNA' in preview['rendered']


@pytest.mark.django_db(transaction=True)
def test_zebra_batch_count_repeats_each_label():
    host, _ = _create_tenants()
    client = Client()
    template = client.post(
        '/api/v1/printing/templates',
        data=json.dumps(
            {
                'name': 'Zebra Energy Batch',
                'template_ref': 'zebra/energy-batch',
                'output_format': 'zpl',
                'content': '^XA^FO40,40^BQN,2,6^FDQA,[[label]]^FS^FO40,200^A0N,28,28^FD[[label]]^FS^XZ',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert template.status_code == 201

    created = client.post(
        '/api/v1/printing/jobs',
        data=json.dumps(
            {
                'template_ref': 'zebra/energy-batch',
                'output_format': 'zpl',
                'destination': 'zebra-printer-1',
                'payload': {
                    'labels': ['ED-10101-01', 'ED-10101-02'],
                    'batch_count': 5,
                },
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created.status_code == 201
    preview = created.json()['gateway_metadata']['render_preview']
    assert preview['engine'] == 'zpl-inline'
    assert preview['batch_count'] == 5
    assert preview['label_count'] == 10
    assert preview['rendered'].count('ED-10101-01') == 10
    assert preview['rendered'].count('ED-10101-02') == 10


@pytest.mark.django_db(transaction=True)
def test_zebra_labels_accept_title_and_text_metadata():
    host, _ = _create_tenants()
    client = Client()
    template = client.post(
        '/api/v1/printing/templates',
        data=json.dumps(
            {
                'name': 'Zebra District Labels',
                'template_ref': 'zebra/district-labels',
                'output_format': 'zpl',
                'content': '^XA^PW200^LL200^LH0,0^FO34,76^BQN,2,4^FDQA,[[content]]^FS^FO10,178^A0N,14,14^FB180,1,0,C,0^FD[[text]]^FS^FO10,194^A0N,10,10^FB180,1,0,C,0^FD[[title]]^FS^XZ',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert template.status_code == 201

    created = client.post(
        '/api/v1/printing/jobs',
        data=json.dumps(
            {
                'template_ref': 'zebra/district-labels',
                'output_format': 'zpl',
                'destination': 'zebra-printer-1',
                'payload': {
                    'labels': [
                        {
                            'content': 'ED-50509-01',
                            'text': 'ED-50509-01',
                            'title': 'Nanyumbu DC',
                        }
                    ],
                },
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created.status_code == 201
    preview = created.json()['gateway_metadata']['render_preview']
    assert preview['engine'] == 'zpl-inline'
    assert preview['batch_count'] == 1
    assert preview['label_count'] == 1
    assert 'ED-50509-01' in preview['rendered']
    assert 'Nanyumbu DC' in preview['rendered']


@pytest.mark.django_db(transaction=True)
def test_zebra_labels_expose_split_line_tokens():
    host, _ = _create_tenants()
    client = Client()
    template = client.post(
        '/api/v1/printing/templates',
        data=json.dumps(
            {
                'name': 'Zebra Split Labels',
                'template_ref': 'zebra/split-labels',
                'output_format': 'zpl',
                'content': '^XA^FO10,10^FD[[line1]]^FS^FO10,30^FD[[line2]]^FS^XZ',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert template.status_code == 201

    created = client.post(
        '/api/v1/printing/jobs',
        data=json.dumps(
            {
                'template_ref': 'zebra/split-labels',
                'output_format': 'zpl',
                'destination': 'zebra-printer-1',
                'payload': {
                    'labels': ['MLTP2-MBY-KWJ-001-BLD-6mls'],
                },
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created.status_code == 201
    preview = created.json()['gateway_metadata']['render_preview']
    assert 'MLTP2-MBY-KWJ-001' in preview['rendered']
    assert 'BLD-6mls' in preview['rendered']


@pytest.mark.django_db(transaction=True)
def test_zebra_default_batch_from_participant_range():
    host, _ = _create_tenants()
    client = Client()
    template = client.post(
        '/api/v1/printing/templates',
        data=json.dumps(
            {
                'name': 'Zebra Participant Labels',
                'template_ref': 'zebra/participant-range',
                'output_format': 'zpl',
                'content': '^XA^FO40,40^BQN,2,6^FDQA,[[label]]^FS^XZ',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert template.status_code == 201

    created = client.post(
        '/api/v1/printing/jobs',
        data=json.dumps(
            {
                'template_ref': 'zebra/participant-range',
                'output_format': 'zpl',
                'destination': 'zebra-printer-1',
                'payload': {
                    'participant_prefix': 'MLTP2-MBY-KWJ-',
                    'range_start': 1,
                    'range_end': 2,
                },
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created.status_code == 201
    assert len(created.json()['payload']['labels']) == 18
    assert created.json()['payload']['labels'][0] == 'MLTP2-MBY-KWJ-001'
    assert created.json()['payload']['labels'][9] == 'MLTP2-MBY-KWJ-002'


@pytest.mark.django_db(transaction=True)
def test_zebra_range_supports_serial_at_end_and_custom_suffixes():
    host, _ = _create_tenants()
    client = Client()
    template = client.post(
        '/api/v1/printing/templates',
        data=json.dumps(
            {
                'name': 'Zebra Participant Labels',
                'template_ref': 'zebra/participant-range-end',
                'output_format': 'zpl',
                'content': '^XA^FO40,40^BQN,2,6^FDQA,[[label]]^FS^XZ',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert template.status_code == 201

    created = client.post(
        '/api/v1/printing/jobs',
        data=json.dumps(
            {
                'template_ref': 'zebra/participant-range-end',
                'output_format': 'zpl',
                'destination': 'zebra-printer-1',
                'payload': {
                    'participant_prefix': 'MLTP2-MBY-KWJ',
                    'range_start': 1,
                    'range_end': 1,
                    'serial_position': 'at_end',
                    'label_suffixes': ['base', 'BLD-6mls'],
                },
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created.status_code == 201
    labels = created.json()['payload']['labels']
    assert labels == ['MLTP2-MBY-KWJ-001', 'MLTP2-MBY-KWJ-BLD-6mls-001']


@pytest.mark.django_db(transaction=True)
def test_pdf_sheet_preview_with_labels_and_preset():
    host, _ = _create_tenants()
    client = Client()
    template = client.post(
        '/api/v1/printing/templates',
        data=json.dumps(
            {
                'name': 'A4 Sheet Template',
                'template_ref': 'a4/qr-sheet',
                'output_format': 'pdf',
                'content': 'QR [[content]]',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert template.status_code == 201

    created = client.post(
        '/api/v1/printing/jobs',
        data=json.dumps(
            {
                'template_ref': 'a4/qr-sheet',
                'output_format': 'pdf',
                'destination': 'office-printer-1',
                'payload': {
                    'labels': ['A4-001', 'A4-002', 'A4-003'],
                    'pdf_sheet_preset': 'a4-38x21.2',
                },
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created.status_code == 201
    preview = created.json()['gateway_metadata']['render_preview']
    assert preview['engine'] == 'qrcode-reportlab-pylabels'
    assert preview['sheet_preset'] == 'a4-38x21.2'
    assert preview['label_count'] == 3
    assert preview['layout']['grid'] == [5, 13]
    assert preview['layout']['label_size_mm'] == [38.0, 21.0]
    assert preview['layout']['margin_mm'] == [10.0, 12.0, 10.0, 12.0]
    assert 'pdf_base64' in preview or 'render_error' in preview


@pytest.mark.django_db(transaction=True)
def test_a4_65_labels_preview_downloadable_when_available():
    host, _ = _create_tenants()
    client = Client()
    template = client.post(
        '/api/v1/printing/templates',
        data=json.dumps(
            {
                'name': 'A4 65-up',
                'template_ref': 'a4/65-up',
                'output_format': 'pdf',
                'content': 'QR [[content]]',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert template.status_code == 201

    labels = [f'A4-{idx:03d}' for idx in range(1, 66)]
    created = client.post(
        '/api/v1/printing/jobs',
        data=json.dumps(
            {
                'template_ref': 'a4/65-up',
                'output_format': 'pdf',
                'destination': 'office-printer-1',
                'payload': {
                    'labels': labels,
                    'pdf_sheet_preset': 'a4-38x21.2',
                },
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created.status_code == 201
    preview = created.json()['gateway_metadata']['render_preview']
    assert preview['label_count'] == 65
    if 'pdf_base64' not in preview:
        assert 'render_error' in preview
        return
    downloaded = client.get(
        f"/api/v1/printing/jobs/{created.json()['id']}/preview.pdf",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert downloaded.status_code == 200
    assert downloaded['Content-Type'] == 'application/pdf'
    assert downloaded.content[:4] == b'%PDF'


@pytest.mark.django_db(transaction=True)
def test_pdf_sheet_batch_count_repeats_labels_per_row():
    host, _ = _create_tenants()
    client = Client()
    template = client.post(
        '/api/v1/printing/templates',
        data=json.dumps(
            {
                'name': 'A4 Batch Rows',
                'template_ref': 'a4/batch-rows',
                'output_format': 'pdf',
                'content': 'QR [[content]]',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert template.status_code == 201

    created = client.post(
        '/api/v1/printing/jobs',
        data=json.dumps(
            {
                'template_ref': 'a4/batch-rows',
                'output_format': 'pdf',
                'destination': 'office-printer-1',
                'payload': {
                    'labels': ['BATCH-001'],
                    'pdf_sheet_preset': 'a4-38x21.2',
                    'batch_count': 5,
                },
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created.status_code == 201
    preview = created.json()['gateway_metadata']['render_preview']
    assert preview['batch_count'] == 5
    assert preview['label_count'] == 5


@pytest.mark.django_db(transaction=True)
def test_pdf_sheet_labels_accept_title_metadata():
    host, _ = _create_tenants()
    client = Client()
    template = client.post(
        '/api/v1/printing/templates',
        data=json.dumps(
            {
                'name': 'A4 District Labels',
                'template_ref': 'a4/district-labels',
                'output_format': 'pdf',
                'content': 'QR [[content]]',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert template.status_code == 201

    created = client.post(
        '/api/v1/printing/jobs',
        data=json.dumps(
            {
                'template_ref': 'a4/district-labels',
                'output_format': 'pdf',
                'destination': 'office-printer-1',
                'payload': {
                    'labels': [
                        {
                            'content': 'ED-10101-01',
                            'title': 'Uyui DC',
                            'text': 'ED-10101-01',
                        }
                    ],
                    'pdf_sheet_preset': 'a4-38x21.2',
                },
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created.status_code == 201
    preview = created.json()['gateway_metadata']['render_preview']
    assert preview['label_count'] == 1
    assert 'pdf_base64' in preview or 'render_error' in preview
    if 'pdf_base64' not in preview:
        return
    pdf_bytes = base64.b64decode(preview['pdf_base64'])
    assert pdf_bytes[:4] == b'%PDF'
