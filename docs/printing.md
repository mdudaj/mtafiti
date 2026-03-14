# Printing and gateway design notes

This note defines tenant-safe label printing using a gateway-based architecture.

## Goals

* Keep Kubernetes workloads isolated from direct printer network access.
* Provide reliable, auditable print execution for enterprise labeling.
* Support both Zebra (ZPL) and PDF/CUPS-style destinations through a controlled gateway.

## Architecture contract

* EDMP cluster never connects directly to site printers.
* Print jobs are requested in EDMP, then consumed and dispatched by a print gateway.
* RabbitMQ is the system transport for print lifecycle events.

## Print lifecycle

1. User submits print request.
2. System validates template, tenant scope, and authorization.
3. Print job is persisted with `pending` status.
4. Event is published (for example: `<tenant_id>.print.requested`).
5. Gateway pulls/subscribes and dispatches to local printer.
6. Gateway reports status (`completed`, `failed`, `retrying`).
7. EDMP finalizes audit record and job status.

## Gateway responsibilities

* Maintain secure outbound channel from site network to EDMP.
* Retry transient failures with bounded retry policy.
* Maintain offline queue while upstream is unavailable.
* Attach printer/driver metadata in completion/failure reports.

## Required metadata per print event

* `tenant_id`
* `correlation_id`
* `user_id` (if user-initiated)
* `timestamp`
* `job_id`

## Non-goals (this increment)

* Direct in-cluster printer management.
* Site-specific printer fleet provisioning automation.

## API and events (implemented scaffold slice)

Endpoints:

* `POST /api/v1/printing/jobs` (create `pending` print job)
* `GET /api/v1/printing/jobs`
* `GET /api/v1/printing/jobs/<job_id>`
* `POST /api/v1/printing/jobs/<job_id>/status` (`retrying | completed | failed`)

Events:

* `print.requested`
* `print.retrying`
* `print.completed`
* `print.failed`

## Standardized rendering stack (selected)

To support both Zebra and A4 label workflows with one predictable toolchain, EDMP standardizes on:

* `qrcode` for QR payload generation
* `reportlab` for PDF drawing/composition
* `pylabels` for sheet-label layouting (A4 labels-per-sheet scenarios)

Target usage by format:

* `zpl`: gateway receives ZPL-compatible payload/templates for Zebra-class printers
* `pdf`: backend generates A4 label-sheet PDF output (including 38mm x 21.2mm presets) for office printers

Current scaffold implementation includes a renderer abstraction (`core/printing_renderers.py`) that produces normalized preview output for `zpl` and `pdf` templates before dispatch.

### Zebra participant batch labels

`zpl` jobs now accept `payload.labels` as an array of label strings.  
When provided, preview rendering expands one ZPL block per label and stores `label_count` in `gateway_metadata.render_preview`.
Optional `payload.batch_count` repeats each input Zebra label N times before rendering (for example `5` prints five identical labels per subject code).
Each `payload.labels[]` entry may also be an object such as `{ "content": "ED-10101-01", "title": "Uyui DC", "text": "ED-10101-01" }` so Zebra templates can print a district heading above the QR and a caption below it.
Zebra template rendering also exposes derived `[[line1]]` and `[[line2]]` tokens for long label text, splitting after the numeric serial segment (for example `MLTP2-MBY-KWJ-001` / `BLD-6mls`).

Default participant-batch mode is also supported for Zebra jobs:
* provide `payload.participant_prefix`, `payload.range_start`, and `payload.range_end`
* EDMP auto-generates 9 labels per participant ID (`base`, `BLD-6mls`, `BLD-4mls`, `BLD-2mls`, `PLM1`, `PLM2`, `BLD-RNA`, `NA1`, `NA2`)
* optional `payload.serial_position = "at_end"` moves serial to the tail of each label
* optional `payload.label_suffixes` lets you override variants (use `"base"` for the root label)

For A4 sheet PDF generation:
* provide `payload.labels` as label lines
* each `payload.labels[]` entry may also be an object such as `{ "content": "ED-10101-01", "title": "Uyui DC", "text": "ED-10101-01" }`
* `content` is encoded into the QR code, `text` controls the bottom caption, and `title` renders as the top heading on the label
* optional `payload.pdf_sheet_preset` (currently `a4-38x21.2`)
* preset `a4-38x21.2` uses a fixed 65-up grid (5 x 13) tuned for 38mm x 21mm stock on A4 with fixed margins `(left=10mm, top=12mm, right=10mm, bottom=12mm)`
* optional `payload.pdf_offset_x_mm` / `payload.pdf_offset_y_mm` nudge the whole sheet layout when a printer needs small horizontal or vertical calibration
* optional `payload.batch_count` repeats each input label N times (for example `5` fills one row with identical labels)
* renderer composes QR+text labels per sheet and includes `sheet_preset` + `label_count` in preview metadata
* download preview PDF via `GET /api/v1/printing/jobs/<job_id>/preview.pdf` when preview contains inline `pdf_base64`

Default templates are provided for user selection in `/app`:
* `zebra/participant-batch` (Zebra QR 9-pack workflow)
* `a4/65-up` (A4 QR sheet workflow)

For deployments that want persisted DB records, load fixture seed data:

```bash
cd backend
python manage.py loaddata core/fixtures/printing_templates.json
```

Example payload:

```json
{
  "template_ref": "zebra/participant-batch",
  "output_format": "zpl",
  "destination": "zebra-printer-1",
  "payload": {
    "labels": [
      "MLTP2-MBY-KWJ-001",
      "MLTP2-MBY-KWJ-001-BLD-6mls",
      "MLTP2-MBY-KWJ-001-BLD-4mls",
      "MLTP2-MBY-KWJ-001-BLD-2mls",
      "MLTP2-MBY-KWJ-001-PLM1",
      "MLTP2-MBY-KWJ-001-PLM2",
      "MLTP2-MBY-KWJ-001-BLD-RNA",
      "MLTP2-MBY-KWJ-001-NA1",
      "MLTP2-MBY-KWJ-001-NA2"
    ]
  }
}
```
