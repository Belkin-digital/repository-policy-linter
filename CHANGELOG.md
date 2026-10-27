---
created: 2026-10-26
updated: 2026-10-27
---

# Changelog

## 0.1.0 — 2026-10-26

- Optional `when.frontmatter` contract selection by exact string fields or allowed-value
  lists, shared by machine/plugin scopes and hashed rubric review requests in commit snapshots.
- Exact local-object `--commit` snapshots, first-parent change selection and check-only execution.
- Hashed per-artifact/contract `review_requests`, full invalidation on contract/shared-rubric
  changes, machine-success versus pending-review separation and harness reviewer/repair guidance.
- Single version-2 `.repo-policy/policy.yaml` entrypoint, explicit thematic registries, scoped
  artifact contracts, optional same-ID explanations and ID navigation in scope README/AGENTS.
- Automatic, unsuppressible policy structure/ID/reference/navigation checks in the base engine;
  additive contract results, explicit pending rubric review and repository-local Python checkers.
- Nested starter bundle and dependency pin in the standalone setup skill; no legacy config mode.
- Versioned check/fix/explain CLI, YAML rules, stable JSON diagnostics, Git selections and exceptions.
- Ten built-in rule kinds and explicit local Ruff/JSON/regex command plugins.
- Optional frontmatter `mapping_path` for nested metadata, with literal-key compatibility.
- Markdown reachability from explicit roots, optional existing parser, full-graph incremental
  checks and additive JSON graph summaries; no automatic link insertion.
- Conservative setup skill and idempotent installer for Codex/Claude; no engine copying.
- Same-engine AF Runner bridge, source-grounded integration assessment and webhook migration backlog.
- Tests, locked development toolchain, CI and wheel-install smoke verification.
