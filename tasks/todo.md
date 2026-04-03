# Task Tracking

- Issue #137: implement proving operation pages and FAB derivation from allowed actions.
- Plan:
	- adopt explicit operation-page descriptors on three proving LIMS launchpads: route-heavy receiving, mixed reference, and state-sensitive storage
	- derive optional FAB behavior from the resolved allowed card set without introducing a second action authority
	- add resolver and UI regressions proving workflow-backed cards, state-sensitive filtering, and FAB suppression behavior
	- run targeted navigation and LIMS UI validation before deciding whether a full gate is necessary