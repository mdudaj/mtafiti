# Task Tracking

- Pause note: work on the ontology-driven admin shell stack is paused for review before returning to this project after another task.

- Issue #133: implement reusable FAB and shared action-slot workflow behavior.
- Status: completed local implementation on `feat/reusable-fab-action-slot-workflow-behavior`.
- Delivered:
  - extended the resolved operation-page pipeline so one descriptor set can derive both FAB output and a shared non-floating action-slot payload from the same allowed actions
  - kept workflow resolution server-side by reusing resolved `route_name` and `workflow_key` outputs instead of constructing workflow URLs in templates or client code
  - proved the behavior on the receiving launchpad as the FAB-authoritative surface and the task inbox as the shared action-slot fallback surface
  - added focused resolver and UI regressions for shared action-slot derivation, workflow-backed actions, and FAB plus fallback consistency
- Validation:
  - `../.venv/bin/python -m pytest tests/test_shell_navigation.py -q`
  - `../.venv/bin/python -m pytest tests/test_lims_ui.py -q -k 'receiving_operation_page_derives_fab_from_primary_action or reference_operation_page_suppresses_fab_without_changing_cards or receiving_and_task_inbox_pages_render_shared_action_slot_behavior'`
  - `../.venv/bin/python -m pytest tests/test_lims_ui.py -q`
  - `bash .github/scripts/local_fast_feedback.sh --full-gate` → `299 passed, 2 deselected`
