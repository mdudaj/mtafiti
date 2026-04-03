# Task Tracking

- Issue #147: harden Sample Accession receiving adapters to governed runtime.
- Plan:
	- inspect the current Sample Accession single, batch, and EDC adapter paths in `src/lims/services.py` and related APIs/tests to find where governed runtime evidence still differs by initiation mode
	- keep the scope limited to runtime adapter behavior, explicit accepted or rejected branch handling, and auditable submission or discrepancy outcomes without drifting into reference-bundle or UI cleanup work
	- implement the smallest behavior-safe hardening needed to make adapter parity across initiation modes explicit in `OperationRun`, `TaskRun`, `SubmissionRecord`, approvals, discrepancies, and storage or disposition outcomes
	- add focused tests proving governed runtime parity and explicit branch evidence across the affected Sample Accession initiation modes