# Task Tracking

- Issue #148: clean up Sample Accession reference and receiving UI migration.
- Plan:
	- inspect the current Sample Accession reference page, receiving launchpad, and receiving entry pages to find where transitional and governed-runtime ownership language is still mixed
	- keep the scope limited to UI copy, page payload language, and focused UI assertions without drifting into runtime services or reference-bundle logic
	- implement the smallest behavior-safe wording and presentation updates needed to make governed runtime ownership and receiving-adapter semantics explicit
	- add focused UI tests covering the resulting reference-operation and receiving migration language