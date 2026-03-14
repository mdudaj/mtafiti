from __future__ import annotations

import base64
import io
import re
from typing import Any


TOKEN_PATTERN = re.compile(r"\[\[\s*([a-zA-Z0-9_]+)\s*\]\]")
MM_TO_PT = 72.0 / 25.4
MAX_INLINE_PDF_LABELS = 120
PDF_SHEET_PRESETS = {
    'a4-38x21.2': {
        'page_size_mm': (210.0, 297.0),
        'label_size_mm': (38.0, 21.0),
        'grid': (5, 13),  # 65-up
        'gap_mm': (0.0, 0.0),
        'margin_mm': (10.0, 12.0, 10.0, 12.0),
    }
}


def _replace_tokens(text: str, payload: dict[str, Any]) -> str:
    return TOKEN_PATTERN.sub(
        lambda match: '' if payload.get(match.group(1)) is None else str(payload.get(match.group(1))),
        text or '',
    )


def _normalize_labels(payload: dict[str, Any]) -> list[str]:
    labels = payload.get('labels')
    if isinstance(labels, list):
        normalized = [str(item).strip() for item in labels if str(item).strip()]
    else:
        normalized = []
    if not normalized:
        single = str(payload.get('label') or payload.get('content') or '').strip()
        if single:
            normalized = [single]
    return normalized


def _normalize_pdf_label_entries(payload: dict[str, Any]) -> list[dict[str, str]]:
    labels = payload.get('labels')
    normalized: list[dict[str, str]] = []
    if isinstance(labels, list):
        for item in labels:
            if isinstance(item, dict):
                content = str(item.get('content') or item.get('label') or '').strip()
                if not content:
                    continue
                title = str(item.get('title') or '').strip()
                text = str(item.get('text') or content).strip() or content
                normalized.append({'content': content, 'text': text, 'title': title})
                continue
            content = str(item).strip()
            if content:
                normalized.append({'content': content, 'text': content, 'title': ''})
    if not normalized:
        content = str(payload.get('label') or payload.get('content') or '').strip()
        if content:
            normalized = [
                {
                    'content': content,
                    'text': str(payload.get('text') or content).strip() or content,
                    'title': str(payload.get('title') or '').strip(),
                }
            ]
    return normalized


def _zpl_qr_block(label: str) -> str:
    return (
        f"^XA^PW200^LL200^LH0,0^FO40,76^BQN,2,4^FDQA,{label}"
        f"^FS^FO10,170^A0N,13,13^FB180,1,0,C,0^FD{label}^FS^XZ"
    )


def _normalize_pdf_sheet_preset(payload: dict[str, Any]) -> str:
    value = str(payload.get('pdf_sheet_preset') or '').strip()
    return value if value in PDF_SHEET_PRESETS else 'a4-38x21.2'


def _coerce_mm_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _resolve_pdf_sheet_layout(
    payload: dict[str, Any], preset_key: str
) -> dict[str, Any]:
    preset = dict(PDF_SHEET_PRESETS[preset_key])
    margin_left, margin_top, margin_right, margin_bottom = preset.get(
        'margin_mm',
        (0.0, 0.0, 0.0, 0.0),
    )
    offset_x = _coerce_mm_number(payload.get('pdf_offset_x_mm')) or 0.0
    offset_y = _coerce_mm_number(payload.get('pdf_offset_y_mm')) or 0.0
    preset['margin_mm'] = (
        margin_left + offset_x,
        margin_top + offset_y,
        margin_right - offset_x,
        margin_bottom - offset_y,
    )
    return preset


def _expand_pdf_batch_labels(
    labels: list[dict[str, str]], payload: dict[str, Any]
) -> tuple[list[dict[str, str]], int]:
    batch_count = payload.get('batch_count')
    if not isinstance(batch_count, int) or batch_count <= 1:
        return labels, 1
    expanded: list[dict[str, str]] = []
    for item in labels:
        expanded.extend([item.copy() for _ in range(batch_count)])
    return expanded, batch_count


def _expand_zpl_batch_labels(
    labels: list[dict[str, str]], payload: dict[str, Any]
) -> tuple[list[dict[str, str]], int]:
    batch_count = payload.get('batch_count')
    if not isinstance(batch_count, int) or batch_count <= 1:
        return labels, 1
    expanded: list[dict[str, str]] = []
    for item in labels:
        expanded.extend([item.copy() for _ in range(batch_count)])
    return expanded, batch_count


def _build_zpl_label_context(
    payload: dict[str, Any], label_entry: dict[str, str]
) -> dict[str, Any]:
    label = label_entry['content']
    text = label_entry.get('text') or label
    title = label_entry.get('title') or ''
    line1 = text
    line2 = ''
    segments = [segment for segment in text.split('-') if segment]
    for index, segment in enumerate(segments):
        if segment.isdigit():
            line1 = '-'.join(segments[: index + 1])
            line2 = '-'.join(segments[index + 1 :])
            break
    return {
        **payload,
        **label_entry,
        'label': label,
        'content': label,
        'text': text,
        'title': title,
        'line1': line1,
        'line2': line2,
    }


def _draw_centered_text(
    pdf: Any,
    text: str,
    *,
    font_name: str,
    font_size: float,
    x: float,
    y: float,
    width: float,
) -> None:
    text_width = pdf.stringWidth(text, font_name, font_size)
    pdf.setFont(font_name, font_size)
    pdf.drawString(x + ((width - text_width) / 2), y, text)


def _render_a4_pdf_sheet(
    labels: list[dict[str, str]], preset: dict[str, Any]
) -> tuple[str | None, str | None]:
    try:
        import qrcode
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        return None, f'missing_pdf_dependencies: {exc}'

    page_w_mm, page_h_mm = preset['page_size_mm']
    label_w_mm, label_h_mm = preset['label_size_mm']
    cols, rows = preset.get('grid', (0, 0))
    gap_x_mm, gap_y_mm = preset['gap_mm']
    margin_left_mm, margin_top_mm, margin_right_mm, margin_bottom_mm = preset.get(
        'margin_mm',
        (0.0, 0.0, 0.0, 0.0),
    )

    page_w_pt = page_w_mm * MM_TO_PT
    page_h_pt = page_h_mm * MM_TO_PT
    label_w_pt = label_w_mm * MM_TO_PT
    label_h_pt = label_h_mm * MM_TO_PT
    gap_x_pt = gap_x_mm * MM_TO_PT
    gap_y_pt = gap_y_mm * MM_TO_PT
    margin_left_pt = margin_left_mm * MM_TO_PT
    margin_top_pt = margin_top_mm * MM_TO_PT
    margin_right_pt = margin_right_mm * MM_TO_PT
    margin_bottom_pt = margin_bottom_mm * MM_TO_PT

    if not cols or not rows:
        usable_w_pt = page_w_pt - margin_left_pt - margin_right_pt
        usable_h_pt = page_h_pt - margin_top_pt - margin_bottom_pt
        cols = max(1, int((usable_w_pt + gap_x_pt) // (label_w_pt + gap_x_pt)))
        rows = max(1, int((usable_h_pt + gap_y_pt) // (label_h_pt + gap_y_pt)))
    labels_per_page = rows * cols

    pdf_buffer = io.BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=(page_w_pt, page_h_pt))
    pdf.setFont('Helvetica', 7)

    for index, label_entry in enumerate(labels):
        page_index = index % labels_per_page
        if page_index == 0 and index > 0:
            pdf.showPage()
            pdf.setFont('Helvetica', 7)
        row = page_index // cols
        col = page_index % cols
        x = margin_left_pt + (col * (label_w_pt + gap_x_pt))
        y = page_h_pt - margin_top_pt - label_h_pt - (row * (label_h_pt + gap_y_pt))

        label = label_entry['content']
        text = label_entry.get('text') or label
        title = label_entry.get('title') or ''

        qr = qrcode.QRCode(box_size=2, border=1)
        qr.add_data(label)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color='black', back_color='white').get_image()
        max_text_width = label_w_pt - 4

        if title:
            title = title[:34]
            text = text[:34]
            title_font_size = 5.5
            while (
                title_font_size > 4
                and pdf.stringWidth(title, 'Helvetica-Bold', title_font_size) > max_text_width
            ):
                title_font_size -= 0.5
            text_font_size = 6
            while (
                text_font_size > 4.5
                and pdf.stringWidth(text, 'Helvetica', text_font_size) > max_text_width
            ):
                text_font_size -= 0.5
            spacing = 2
            top_padding = 2
            bottom_padding = 2
            title_y = y + label_h_pt - title_font_size - top_padding
            text_y = y + bottom_padding
            qr_max_height = title_y - text_y - text_font_size - (spacing * 2)
            qr_size = min(label_w_pt * 0.48, max(14, qr_max_height))
            qr_x = x + ((label_w_pt - qr_size) / 2)
            qr_y = text_y + text_font_size + spacing
            _draw_centered_text(
                pdf,
                title,
                font_name='Helvetica-Bold',
                font_size=title_font_size,
                x=x,
                y=title_y,
                width=label_w_pt,
            )
            pdf.drawInlineImage(qr_img, qr_x, qr_y, qr_size, qr_size)
            _draw_centered_text(
                pdf,
                text,
                font_name='Helvetica',
                font_size=text_font_size,
                x=x,
                y=text_y,
                width=label_w_pt,
            )
            continue

        qr_size = min(label_h_pt * 0.58, label_w_pt * 0.54)
        text = text[:48]
        font_size = 7
        while font_size > 5 and pdf.stringWidth(text, 'Helvetica', font_size) > max_text_width:
            font_size -= 1
        text_width = pdf.stringWidth(text, 'Helvetica', font_size)
        spacing = 2
        group_height = qr_size + spacing + font_size
        group_y = y + ((label_h_pt - group_height) / 2)
        qr_x = x + ((label_w_pt - qr_size) / 2)
        qr_y = group_y + font_size + spacing
        text_x = x + ((label_w_pt - text_width) / 2)
        text_y = group_y
        pdf.setFont('Helvetica', font_size)
        pdf.drawInlineImage(qr_img, qr_x, qr_y, qr_size, qr_size)
        pdf.drawString(text_x, text_y, text)

    pdf.save()
    encoded = base64.b64encode(pdf_buffer.getvalue()).decode('ascii')
    return encoded, None


def render_label_preview(*, output_format: str, template_content: str, payload: dict[str, Any]) -> dict[str, Any]:
    if output_format == 'zpl':
        labels = _normalize_pdf_label_entries(payload)
        if labels:
            labels, batch_count = _expand_zpl_batch_labels(labels, payload)
            if template_content:
                rendered_blocks = []
                for label_entry in labels:
                    rendered_blocks.append(
                        _replace_tokens(
                            template_content,
                            _build_zpl_label_context(payload, label_entry),
                        )
                    )
                return {
                    'engine': 'zpl-inline',
                    'batch_count': batch_count,
                    'label_count': len(rendered_blocks),
                    'rendered': '\n'.join(rendered_blocks),
                }
            return {
                'engine': 'zpl-inline',
                'batch_count': batch_count,
                'label_count': len(labels),
                'rendered': '\n'.join(_zpl_qr_block(label['content']) for label in labels),
            }
        rendered = _replace_tokens(template_content, payload)
        return {'engine': 'zpl-inline', 'batch_count': 1, 'label_count': 1, 'rendered': rendered}
    if output_format == 'pdf':
        preset_key = _normalize_pdf_sheet_preset(payload)
        preset = _resolve_pdf_sheet_layout(payload, preset_key)
        labels = _normalize_pdf_label_entries(payload)
        labels, batch_count = _expand_pdf_batch_labels(labels, payload)
        if labels:
            response = {
                'engine': 'qrcode-reportlab-pylabels',
                'sheet_preset': preset_key,
                'label_count': len(labels),
                'batch_count': batch_count,
                'layout': {
                    'grid': preset.get('grid'),
                    'label_size_mm': preset.get('label_size_mm'),
                    'page_size_mm': preset.get('page_size_mm'),
                    'margin_mm': preset.get('margin_mm'),
                },
            }
            if len(labels) > MAX_INLINE_PDF_LABELS:
                response['rendered'] = 'sheet payload too large for inline preview'
                response['render_warning'] = (
                    f'inline pdf disabled when labels>{MAX_INLINE_PDF_LABELS}'
                )
                return response
            pdf_base64, render_error = _render_a4_pdf_sheet(labels, preset)
            response['rendered'] = _replace_tokens(template_content, payload)
            if pdf_base64:
                response['pdf_base64'] = pdf_base64
            if render_error:
                response['render_error'] = render_error
            return response
        rendered = _replace_tokens(template_content, payload)
        return {
            'engine': 'qrcode-reportlab-pylabels',
            'sheet_preset': preset_key,
            'label_count': 1,
            'batch_count': batch_count,
            'layout': {
                'grid': preset.get('grid'),
                'label_size_mm': preset.get('label_size_mm'),
                'page_size_mm': preset.get('page_size_mm'),
                'margin_mm': preset.get('margin_mm'),
            },
            'rendered': rendered,
        }
    rendered = _replace_tokens(template_content, payload)
    return {'engine': 'raw', 'rendered': rendered}
