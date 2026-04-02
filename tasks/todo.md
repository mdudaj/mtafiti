# Task Tracking

- Issue #136: implement the reusable action-card component and bounded card-grid rendering contract.
- Plan:
	- extract a shared action-card partial and bounded grid wrapper under `src/core/templates/core/ui/includes/`
	- convert the repeated LIMS launchpad card markup to the shared includes without reopening resolver logic
	- add rendering-focused regression coverage for grid and action-card markers in `src/tests/test_lims_ui.py`
	- run targeted UI tests and the full merge gate