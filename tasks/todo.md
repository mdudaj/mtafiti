# Task Tracking

- Issue #131: implement django-material admin shell contract and proving surfaces.
- Status: completed local implementation on `feat/django-material-shell-proving-surfaces`.
- Delivered:
  - promoted `lims_dashboard_page` to an explicit proving surface for the shared shell `page_actions` and `workflow_guidance` slots
  - promoted `lims_reference_create_lab_page` to an explicit proving surface for the shared shell `page_heading`, `page_actions`, and `page_content` slots
  - kept the create-lab reference selector URL contract intact while moving the page onto shell-slot blocks
  - added focused UI regression coverage for dashboard and CRUD shell-slot rendering
- Validation:
  - `../.venv/bin/python -m pytest tests/test_lims_ui.py -q -k 'reference_forms_expose_slug_and_address_selectors or shell_proving_surfaces_render_shared_slots_for_dashboard_and_crud'`
  - `../.venv/bin/python -m pytest tests/test_lims_ui.py -q -k 'lims_html_pages_render_with_role_aware_actions or shell_proving_surfaces_render_shared_slots_for_dashboard_and_crud'`
  - pending full gate: `.github/scripts/local_fast_feedback.sh --full-gate`
