from __future__ import annotations

from django.conf import settings
from django.template import TemplateDoesNotExist
from django.template.loader import get_template

MATERIAL_BASE_TEMPLATE_CANDIDATES = (
    "material/layout/base.html",
    "material/frontend/base.html",
    "material/base.html",
)
FALLBACK_BASE_TEMPLATE = "core/ui/base_fallback.html"


def resolve_ui_base_template() -> str:
    if not settings.EDMP_UI_MATERIAL_ENABLED:
        return FALLBACK_BASE_TEMPLATE

    for template_name in MATERIAL_BASE_TEMPLATE_CANDIDATES:
        try:
            get_template(template_name)
            return template_name
        except TemplateDoesNotExist:
            continue
    return FALLBACK_BASE_TEMPLATE
