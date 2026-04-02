# Task Tracking

- Issue #135: implement operation-page descriptor resolution and deterministic action filtering.
- Plan:
	- define the operation-page and action-card resolver contract in `src/core/navigation.py`
	- route existing launchpad payloads through the shared resolver without expanding into rendering-only work
	- add targeted resolver and launchpad regression tests
	- run targeted validation for navigation and LIMS/operations UI payloads