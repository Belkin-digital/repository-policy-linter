---
created: 2026-10-26
updated: 2026-10-27
---

# Changelog

## 0.5.1 — 2026-10-27

- Make Git context fixtures independent of Windows autocrlf defaults and avoid removing
  read-only Git objects when checking a non-Git root. Runtime Git-context behavior is unchanged.

## 0.5.0 — 2026-10-27

- Add opt-in repository plugin Git contexts with exact two-tree baselines, deletions,
  tracked/untracked state and post-check integrity verification.
- Add caller-supplied context input outside the checkout and bounded exact local Git queries.
- Keep legacy plugins/report v1 compatible; reject context-enabled fixes before writes.
- Support depth-two snapshot comparisons without requiring unrelated grandparents.

## 0.4.1 — 2026-10-27

- Add a manually dispatched, tag-verified PyPI release workflow with a check-only rehearsal,
  locked tests/build verification and an isolated Trusted Publishing job.
- Document first-time PyPI account/publisher setup and version-pinned registry installation,
  keeping digest-pinned wheels available for versions not yet released.
- Include official source, documentation and issue URLs in distribution metadata.
- Exclude local app configuration from source archives and reject release archive files that
  do not match the selected Git tag's tracked source bytes.

## 0.4.0 — 2026-10-27

- Repository-scoped plugins run even for empty or deletion-only selections and may report
  declared missing metadata files. File-scoped plugins retain their existing behavior.
- Optional frontmatter `preserve_keys` compares existing typed values with a local Git baseline,
  including nested skill metadata and exact committed snapshots.
- Enforce release/version consistency, core dependency/import constraints, standalone skill
  boundaries, and locked check-only hook/CI configuration through the project's own policy.
- Carry universal rule-design, rubric approval and integration guidance in the standalone
  setup skill and its generated target instructions; document rule coverage and remaining limits.

## 0.3.2 — 2026-10-27

- Require evaluating each new rule for simple, reliable linter enforcement, and obtain user
  approval before implementing or expanding resource-intensive rubric checks.

## 0.3.1 — 2026-10-27

- Evaluate the version gate after opt-in fixes, so newline repairs on a clean checkout also
  require a version increment before their changes can pass the machine gate.

## 0.3.0 — 2026-10-27

- Built-in `version-increment` check with strict SemVer precedence, local Git baselines and
  exact commit handling; unchanged/decreased versions fail even with empty/deletion-only selection.
- Enable the version gate in this repository's policy and fetch the first parent in CI.

## 0.2.0 — 2026-10-27

- Optional `when.frontmatter` contract selection by exact string fields or allowed-value
  lists, shared by machine/plugin scopes and hashed rubric review requests in commit snapshots.
- Synchronized package/runtime/lock versions and current installation examples; require a
  version increment and changelog update before every project commit.

## 0.1.0 — 2026-10-26

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
