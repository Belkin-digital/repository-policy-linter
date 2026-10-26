---
name: repo-policy-setup
description: Install or update Repository Policy Linter in a chosen existing repository, configure shared policy rules, and integrate agent instructions, pre-commit and CI without copying the engine. Use for local Codex/Claude setup and migration to an AF Runner with the same policy.
metadata:
  created: '2026-10-26'
  updated: '2026-10-26'
---

# Repository Policy Linter setup

Project source: [Belkin-digital/repository-policy-linter](https://github.com/Belkin-digital/repository-policy-linter).
The [upstream skill folder](https://github.com/Belkin-digital/repository-policy-linter/tree/main/skills/repo-policy-setup)
contains this skill and its helpers. Use the project's
[build and installation instructions](https://github.com/Belkin-digital/repository-policy-linter/blob/main/README.md)
to obtain the engine separately; a source repository is not a published PyPI distribution.

Work only in the repository selected by the user. Installing this skill does not authorize
changing other repositories. The engine is an external, versioned dependency; never copy
`src/repo_policy` into the target or invent a published package/remote URL.

1. Read applicable `AGENTS.md`, `CLAUDE.md`, contribution rules and existing dependency,
   pre-commit and CI configuration. Inspect Git status; preserve unrelated edits, comments,
   YAML anchors and symlinks. Determine the repository root explicitly.
2. Resolve an available immutable engine distribution: a published exact version, or an
   approved wheel/artifact URL with SHA-256. For this unreleased version use the built wheel
   from the [source repository](https://github.com/Belkin-digital/repository-policy-linter)
   at a recorded commit SHA. Keep the distribution accessible to both local and platform
   execution; a `file://` URL is a local pilot, not a portable platform installation.
3. Use [scripts/configure.py](scripts/configure.py) with `--root` and `--engine` to preview
   changes (default is dry-run), then `--apply` to create the `.repo-policy/policy.yaml`
   version-2 manifest, common registry and `.repo-policy/requirements.txt` pin. Existing bundles
   and dependency files are preserved byte-for-byte; reconcile differences directly. The helper
   does not inject undeclared modules into an existing bundle. Use `--instructions`
   only when adding a short managed section to the existing instruction file is appropriate.
   The helper neither installs packages nor changes hooks, commits, pushes or global settings.
4. Install the dependency through the repository's existing dev-tool manager, or an isolated
   environment. For a generic repository:
   `python3 -m venv .venv-policy`, then `.venv-policy/bin/python -m pip install -r .repo-policy/requirements.txt`.
   On Windows use `.venv-policy\Scripts\python.exe`. Add this environment to existing ignore
   rules. When using a lock manager, resolve and commit its lock. Avoid global installation.
5. Start with `.repo-policy/policy.yaml`; configure only policies supported by actual repository
   conventions. Use existing specialized tools for syntax/style/domain semantics (Ruff,
   markdownlint, yamllint, Spectral, ESLint, etc.), with pinned versions and read-only commands.
   Generic text rules are not semantic validators. Read [references/integration.md](references/integration.md)
   for plugin trust, pre-commit, CI and AF migration. Review commands before `--allow-plugins`.
   If enabling Markdown reachability, use the `[markdown]` package extra and choose only
   existing repository-local entrypoints; follow the navigation guidance in that reference.
   Read [references/contracts.md](references/contracts.md) when adding thematic registries,
   artifact contracts, same-ID explanations, scope navigation or repository-specific Python checks.
   The engine always validates policy structure, IDs and navigation; do not configure copies
   of its `system-*` checks. There is no legacy root-config discovery.
6. Integrate with existing pre-commit/CI by a small targeted merge; never replace their files.
   Run the same check locally and in CI; keep hooks check-only. Preserve AGENTS/CLAUDE linking
   conventions (including generated `.claude` files); add one short invocation reference at
   the maintained source, rather than competing policy text in several files.
7. Run `repo-policy check --all`, then `repo-policy check --changed`; use `--format json` for
   automation. Run repository-mandated tests and the affected CI/pre-commit checks. Establish
   an initial report before changing policies to avoid a sudden unreviewed enforcement gate.
   `fix --dry-run` previews; `fix` only appends final newlines for opted-in rules. Never run
   tool auto-fixes under the guise of safe engine fixes.
8. For rubric contracts read [references/reviews.md](references/reviews.md) and add the handoff
   instructions to the maintained root AGENTS/CLAUDE source. The current harness owns subagent
   dispatch, hash-matched verdicts and repair iterations. Review every `review_requests` entry;
   machine exit 0 alone does not establish acceptance. Use `--commit <SHA>` for committed inputs.

Report files changed, dependency source/version, diagnostics, tests, and any remaining
platform portability gaps. Repeating setup must not duplicate sections or overwrite policy.
For AF retain exactly the same policy, engine, tool locks and selection; change execution
transport only. No platform SkillVersion/Resource/AgentVersion exists until AF Core persisted it.
