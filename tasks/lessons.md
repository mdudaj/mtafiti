# Lessons

- Issue #132 references a missing `specs/011-ontology-driven-admin-shell` bundle, so implementation scope has to be derived from `docs/workflow-ui.md` plus the current core and LIMS shell code.
- The `/app` user portal and the broader workspace shell do not share the same operations-link visibility contract; keep those descriptor sets separate when extending the registry.
- Shared action descriptors need both visibility and enabled-state hooks; storage and inventory launchpads use the latter to preserve role-aware cards without reintroducing inline action dictionaries.
- Exploratory subagent results are useful for narrowing searches, but any reported file path still needs direct workspace validation before it informs a patch.
- Once registry-backed surfaces are complete, remaining page-local navigation should use named routes in templates or view helpers rather than expanding the descriptor layer beyond its target surface.
- After route normalization lands, the most brittle follow-up surface is test expectations; use Django `reverse(...)` in navigation-sensitive regressions so future route refactors do not recreate literal-path churn.
- After normalizing page routes, check Python payload builders and seeded workflow config for leftover absolute strings too; those runtime URLs should also resolve through named routes so task clients and canonical workflow bundles stay aligned.
- When page tests need query strings, build them from `reverse(...)` first and append the query suffix rather than hardcoding the full path; those banner/filter assertions are another easy place for route literals to linger.
- For static template-side API selector URLs, prefer `{% url %}` plus a query suffix over hardcoded `/api/v1/...` strings; that keeps shared includes aligned with canonical API names without forcing a larger dynamic-JS routing refactor.