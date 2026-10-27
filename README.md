---
created: 2026-10-26
updated: 2026-10-27
---

# Repository Policy Linter

Lightweight local repository policies for **Codex, Claude Code, CI and Agent Factory**.
One versioned `.repo-policy/` bundle and engine, the same diagnostics on every execution backend.
Python 3.11+; one core runtime dependency (PyYAML); no telemetry, network calls or LLM service.
Optional Markdown reachability checks use the `[markdown]` extra (markdown-it-py and mdurl).

**Status:** working version 0.3.0. Public source:
[Belkin-digital/repository-policy-linter](https://github.com/Belkin-digital/repository-policy-linter).
Build the distributable wheel from this checkout. The package is not published on PyPI;
do not assume `pip install repository-policy-linter` will retrieve this project.

## Quick start from this checkout

```bash
git clone https://github.com/Belkin-digital/repository-policy-linter.git
cd repository-policy-linter
uv sync --frozen
uv run --frozen repo-policy --version
uv run --frozen repo-policy check --all --allow-plugins
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen uv build
```

## Policy checks in this project

This source repository uses its own engine from the current checkout and the dev tools
locked in `uv.lock`. It does not depend on its previously built wheel. For other repositories,
the setup skill installs the versioned engine as an external dependency.

Install the local Git hook once, then use the same policy commands as Codex, Claude and CI:

```bash
uv run --frozen pre-commit install
uv run --frozen repo-policy check --changed --allow-plugins
uv run --frozen repo-policy check --all --allow-plugins
uv run --frozen pre-commit run --all-files
uv run --frozen repo-policy fix --all --allow-plugins --dry-run
```

The policy checks required source/test directories, metadata, lockfile, agent instructions,
the setup skill and CI/hook configuration. It validates skill frontmatter and JSON/YAML,
checks final newlines, and delegates Python linting to the pinned Ruff plugin. pre-commit
also checks Python formatting. Both hooks are check-only. A missing required path fails even
when the selected changed-file set is empty. The policy hook always runs a full check, including
deletion-only commits. Scratch files under `work/` are excluded.

The built-in `package-version-increment` rule requires a higher SemVer before each commit.
Pending tracked changes compare against HEAD; clean checkouts and `--commit` compare against
the first parent. The rule runs even for deletion-only/empty selections and never edits the
version. CI fetches both commits. See [versioning](docs/releasing.md) and the
[rule contract](docs/configuration.md#version-increments).

Markdown also requires `created` and `updated` in frontmatter; native `SKILL.md` files
store them under `metadata`. Existing creation dates are preserved. This is a presence
check, not date-format/chronology validation or automatic timestamp maintenance.
See the [frontmatter experiment](docs/frontmatter-experiment-2026-10-26.md).

Every Markdown document must also be reachable by local links from `AGENTS.md`, through
the [documentation index](docs/README.md) or other linked guides. This repository checks
the entire navigation graph in every selection mode. See the
[reachability experiment](docs/reachability-experiment-2026-10-26.md).

## Install the engine in another repository

Install the **external package**, not the source tree:

```bash
python3 -m venv /path/to/target/.venv-policy
/path/to/target/.venv-policy/bin/python -m pip install /absolute/path/to/repository_policy_linter-0.3.0-py3-none-any.whl
cd /path/to/target
.venv-policy/bin/repo-policy init
.venv-policy/bin/repo-policy check --all
.venv-policy/bin/repo-policy check --changed
.venv-policy/bin/repo-policy check --changed --base main --format json
.venv-policy/bin/repo-policy fix --dry-run
.venv-policy/bin/repo-policy explain final-newline
```

On Windows use `.venv-policy\Scripts\python.exe` and `.venv-policy\Scripts\repo-policy.exe`.
Add the tool environment to target ignore rules. Runtime dependencies can be installed from
an internal wheelhouse using pip's `--no-index --find-links`; dependency installation may need
network access otherwise, while the engine itself does not.

For the optional `markdown-reachable` rule, install the same approved wheel with its extra:
`python -m pip install '/absolute/path/to/repository_policy_linter-0.3.0-py3-none-any.whl[markdown]'`.
Pin the extra and transitive dependencies in the target toolchain for local/CI/AF parity.
This checkout's dev lock already includes the Markdown parser.

## CLI contract

| Command/option | Behavior |
| --- | --- |
| `check` | Read-only engine checks; external tools must be configured as check-only |
| `fix` | Only append final newline for `final-newline` rules with `safe_fix: true` |
| `fix --dry-run` | Return diagnostics and `fixable` flags without modifying files |
| `explain [kind-or-id]` | Explain kinds/system checks or resolve a check/contract ID with its optional explanation |
| `init` | Create `.repo-policy/policy.yaml` and a common check registry; refuse to overwrite |
| `--all` | Default: tracked and unignored untracked files; excludes apply |
| `--changed` | Staged + unstaged + untracked; deleted files omitted; supports unborn Git HEAD |
| `--changed --base REF` | Diff from merge-base(HEAD, REF), including working changes and untracked files |
| `--commit REF` | Check exact committed bytes/policy against the first parent, excluding dirty working/index changes; check-only |
| `--files a b` | Explicit root-relative regular files (for hooks); exclusions still apply |
| `--root PATH` | Explicit root; changed mode requires the Git root |
| `--config PATH` | Root-relative version-2 manifest, default `.repo-policy/policy.yaml`; no legacy fallback |
| `--format json` | Stable schema version 1, ordered file/line/column/rule diagnostics |
| `--fail-on warning` | Lower failure threshold; default `error` |
| `--allow-plugins` | Explicit trust decision to run configured executable commands |

Exit codes: **0** no diagnostics at threshold, **1** policy violations remain,
**2** configuration/usage/filesystem/Git/plugin execution failure, **130** interrupted.
JSON configuration/execution errors carry `error` and `exit_code: 2`; argparse usage
errors are human-readable stderr. `fix` reports remaining violations after fixes; per-file
atomic writes are not a repository-wide transaction. A later failure can follow an earlier fix.

Rubric obligations are separate from machine return codes. `review_requests` contains stable
artifact/contract jobs with raw-byte hashes; pending review keeps `needs_review` and does not
itself return 1. The current harness dispatches reviewers, stores verdicts and coordinates fixes
before claiming acceptance. Contract/rubric edits include all related artifacts, even unchanged
ones. See [commit snapshots and the review handoff](docs/rubric-review.md).

Required-path checks always run, including empty changed selections, so deleting a required
document or directory cannot hide behind a filtered file list. Run from root or provide `--root`.
No implicit upward config search. Outside Git, all mode walks files with the documented built-in
directory exclusions; `.gitignore` is only interpreted by Git, not reimplemented.

## Rules and plugins

Keep thematic definitions in `.repo-policy/checks/`, artifact contracts in `contracts/`,
optional same-ID explanations in `readme/`, and repository-specific Python checkers in `scripts/`.
Contracts select checks by ID, artifact path and optional `when.frontmatter` conditions such
as `artifact_type: requirement`. Scope README/AGENTS frontmatter carries
`repo_policy_contracts`; root AGENTS documents ID resolution. Structure, unique IDs and
navigation are checked automatically by the base engine, independently of file selection.
See [policy bundles and contracts](docs/policy-bundles.md) for the schema and complete examples.

Built-in policies cover required files/directories, forbidden paths/text, required text,
file size, final newlines, JSON/YAML parsing, top-level data keys, Markdown YAML frontmatter
and Markdown reachability from explicit entrypoints.
Code, specs, binary assets and arbitrary files participate by their configured paths;
language semantics belong to specialized tools. See [configuration](docs/configuration.md)
and [plugin protocol](docs/plugins.md). No specialist linter logic is copied into this engine.

## Install the setup skill, then apply it to selected repositories

From this source checkout, install only the small skill folder:

```bash
# Codex personal scope; use an explicitly chosen destination
python3 scripts/install_skill.py --destination "$HOME/.agents/skills/repo-policy-setup"
# Claude Code personal scope
python3 scripts/install_skill.py --destination "$HOME/.claude/skills/repo-policy-setup"
```

For a team, choose `TARGET/.agents/skills/repo-policy-setup` (Codex) or
`TARGET/.claude/skills/repo-policy-setup` (Claude). Installer preserves a different existing
skill and treats identical installs as no-ops. The skill is also under `skills/` in the source
distribution; it is intentionally separate from the engine wheel.

Open the selected target repo in its agent, then invoke:

```text
Codex: $repo-policy-setup Install the linter in this repository using the supplied 0.3.0 wheel.
Claude Code: /repo-policy-setup Install the linter in this repository using the supplied wheel.
```

The agent inspects repository rules, pins the external dependency, adds/merges config, pre-commit
and CI, updates maintained agent instructions, runs checks and target tests. No engine copy and
no mass rollout. The helper defaults to preview and preserves pre-existing files; detailed
integration guidance is in the [skill](skills/repo-policy-setup/SKILL.md).

These discovery locations and invocation forms follow the official
[Codex customization guide](https://learn.chatgpt.com/docs/customization/overview) and
[Claude Code skills guide](https://code.claude.com/docs/en/skills).

## Local → platform continuity

Keep policy, engine version and plugin locks in the repository. Run `repo-policy-af` inside
the selected AF Runner checkout with the same flags. It calls the same engine and produces
identical reports plus a conservative AF output fragment. It does not register a platform skill.
See the [verified AF integration assessment](docs/agent-factory.md) and
[push/PR observation backlog](docs/platform-backlog.md) for a gradual migration with parity checks.

## Development and limitations

```bash
uv sync --frozen
uv run python -m unittest discover -s tests -v
uv run ruff check .
uv run ruff format --check .
uv run repo-policy check --all --allow-plugins
uv run pre-commit run --all-files
uv build
```

CI is configured for unit/integration tests, Ruff, policy checks and a wheel-install smoke test on Python
3.11–3.14 (Linux) and 3.12 (Windows). See [security](SECURITY.md), [release procedure](docs/releasing.md)
and [changelog](CHANGELOG.md). A Python parser and trusted regex rules do not constitute a
complete semantic validator. External commands run with caller permissions and need an OS
sandbox for untrusted repositories. No deployed AF end-to-end test or package release is claimed.
