# Task Tracking

- Issue #146: harden Sample Accession reference bundle publication invariants.
- Plan:
	- inspect the current Sample Accession reference-bundle publication path in `src/lims/services.py` and related tests to find where authored-version immutability and provisioning idempotence are currently implicit
	- map the selected issue boundary to the validated `specs/006-sample-accession-reference-operation/` split so this branch stays limited to publication invariants rather than adapter or UI cleanup work
	- implement the smallest behavior-safe hardening needed to make operation, workflow, and package publication rules explicit and reviewable
	- add focused tests proving published-version immutability, reference-bundle idempotence, and any explicit SOP or runtime-default metadata expectations touched by the change