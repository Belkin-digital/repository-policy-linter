---
created: 2026-10-27
updated: 2026-10-27
---

# Turning repository instructions into checks

For every new rule or acceptance requirement ask: "Can the linter enforce this reasonably,
reliably and simply?" If yes, implement enforcement in the shared policy/engine. Prefer existing
built-ins, native specialist tools and small reviewed repository-specific adapters. Store Python
adapters in `.repo-policy/scripts/` and register their thematic modules explicitly. Keep one policy
and pinned engine/toolchain for local agents, hooks, CI and AF. Native tools remain check-only;
review their commands before enabling `--allow-plugins`. They run with caller permissions.

Record the exact fact a check proves. Parsed metadata, AST checks and native tool diagnostics
are appropriate for structural facts. The presence of words in instructions does not prove that
an agent followed them; a changed test file does not prove meaningful compatibility coverage.
Keep semantic judgment, permission evidence and operational execution with the responsible
harness/person when no simple reliable check exists. Explain the limitation and record coverage.

Before implementing a new rubric check, changing its criteria or expanding its scope/triggers,
always obtain explicit user approval. Explain what deterministic checks cannot establish,
which artifacts/criteria will be reviewed, when reviews run and the expected resource cost.
Implement only the approved scope. Do not add automatic review costs through a starter template.
Existing approved obligations use the [review handoff](reviews.md); machine exit 0 is not rubric
acceptance. Keep complete hash-matched requests/verdicts in ignored run output, outside policy.

Apply portable principles according to the selected repository's actual conventions:

- Preserve unrelated edits, comments, local configuration and existing integration conventions.
  Merge hooks/CI and instruction sections; use disposable repositories for integration tests.
- Keep engine installation external to the skill and target sources. Resolve an actual immutable
  distribution and dependency lock; skill installation does not authorize an engine upgrade,
  another repository's deployment, publication or platform object creation.
- Before editing contracted artifacts, inspect scope IDs and resolve their YAML/rubrics and
  optional same-ID explanations. Selectors determine applicability; pointers aid discovery.
- Keep maintained documents reachable through the repository's chosen entrypoints when adopting
  Markdown navigation. If it uses date metadata, preserve known `created`; native skill dates
  belong under `metadata`. Establish missing dates from evidence; do not invent authorship.
  With local Git history, `preserve_keys: [created]` enforces existing typed values. It cannot
  prove original authorship or decide whether a prose change warrants refreshing `updated`.
- Adopt version checks only when the repository requires them. Choose its authoritative source,
  keep mirrors/current changelog/examples consistent, and fetch required history in CI. This
  project's Python layout, dependency count and per-commit version bumps are local conventions.
- Use `scope: repository` for cross-file metadata checks which must run with empty selection;
  use ordinary file plugins for selected-artifact checks. Review code and bound its inputs.
  Both are explicit trusted plugins, not a sandbox or a substitute for an approved policy baseline.
- Keep fixes opt-in. The engine's safe fixer only adds final newlines; date repair, version
  selection and semantic fixes remain explicit edits. Rerun the relevant checks afterward.

Copy the universal decision rule and rubric approval requirement into the maintained target
AGENTS/CLAUDE source. Explain its policy entrypoint, ID navigation, check commands, plugin trust
and already-approved review handoff. Configure repository-specific requirements from its own
instructions; do not rely on an agent finding the upstream project's AGENTS file.
