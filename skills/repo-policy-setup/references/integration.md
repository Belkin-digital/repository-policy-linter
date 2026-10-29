---
created: 2026-10-26
updated: 2026-10-29
---

# Integration details

Use this stage after [discovery](rule-design.md). Installation-only configures the selected
checks; migration additionally uses [preservation/adoption](data-preservation.md) and the
[acceptance record](acceptance.md). Neither route automatically enables new rubric or a blocking gate.

## External dependency and portability

The upstream source is
[Belkin-digital/repository-policy-linter](https://github.com/Belkin-digital/repository-policy-linter);
its [README](https://github.com/Belkin-digital/repository-policy-linter/blob/main/README.md)
documents building the wheel and installing the standalone skill. Record the chosen source
commit when building a wheel. Links to `main` are documentation entrypoints, not immutable
dependency pins or evidence of a package release.

Use an actual published version from the official
[PyPI project](https://pypi.org/project/repository-policy-linter/), after checking its source URLs,
or a wheel with an immutable digest. Never infer publication from a source version alone.
For an available registry version, preview the helper with:

```text
python3 <skill>/scripts/configure.py --root <target> --engine 'repository-policy-linter==0.4.2'
```

For a version not yet published, use the actual built wheel instead (replace the example
source/digest; an illustrative URL is not a published artifact):

```text
python3 <skill>/scripts/configure.py --root <target> --engine 'repository-policy-linter @ file:///absolute/path/to/repository_policy_linter-0.4.2-py3-none-any.whl#sha256=<actual-64-hex-digest>'
```

Preview first, then repeat with `--apply`. Target dependency files are left unchanged if they
exist; inspect `matches: false` and reconcile manually. The helper accepts exact package versions
or credential-free wheel URLs with SHA-256; it does not resolve existence or install anything.
It refuses symlink output files and existing managed instruction sections are preserved.
The engine wheel is an external dependency; config, locks and integration snippets belong in target.
For a portable rollout publish the exact wheel in an approved internal artifact store and use its
HTTPS URL + digest in local/CI/AF installation. Lock transitive dependencies through the target's
manager or an offline wheelhouse; `==` pins alone are not a full supply-chain lock.

Record four independent results: distribution identity (version/source commit/digest), availability
through its declared channel, cold installation without a previous editable engine, and operation
of the target integration. Source-build is another valid selected route: pin the exact source and
build backend/dependencies, build in an isolated tree and record the resulting wheel digest.
A local cache or feature branch is not a durable artifact channel for another machine.

Use the existing tool manager/lock. Include needed extras, parsers, specialist tools and transitive
dependencies; include build tools for source-build. The canonical launcher must run that environment
and put its tools on PATH, so plugin `python` does not depend on an arbitrary shell. Verify actual
package version/import location and distribution identity; an equal version string alone does
not prove equal installed bytes. Do not introduce a second launcher if the manager already provides it.

### Capability selection

These are engine capabilities, separate from the version of this standalone skill:

| Capability | Released engine baseline / constraint |
| --- | --- |
| Version-2 bundles, exact `--commit`, hashed review requests | 0.1.0 onward; use the selected version's schema |
| `when.frontmatter` exact strings / allowed lists | 0.2.0 onward; unconditional tag validation still needed |
| Version increment after opt-in fixes | 0.3.1 onward; Git baseline/history required |
| `scope: repository`, `preserve_keys` | 0.4.0 onward; preservation is typed and same-path |
| Arbitrary plugin before/after Git context | Not supplied by 0.4.x; do not invent `context` or `{context}` configuration |

Verify the actual distribution and version-specific API before applying examples. Committed
plugin snapshots have no `.git`; do not locate a different checkout to manufacture history.
For a general missing capability, prepare an isolated upstream change with compatibility tests;
keep domain rules in the consumer. Updating a pin needs a real available artifact and the task's
authority; submitting a PR does not authorize merge, tag, package publication or another rollout.

## Helper preview, conflicts and writes

`configure.py` remains a standard-library bootstrap, independent of the installed engine. Default
mode previews; `--apply` scaffolds only. Its existing `applied`, `actions`, `engine` and
`portable_source` fields remain, with additional evidence boundaries:

| Output | Meaning |
| --- | --- |
| `source_kind` | Syntactic `registry`, `https_wheel` or `local_wheel`; not a reachability result |
| `verification` | Availability `not_verified`, cold install and CI `not_run`; helper does not perform them |
| `portable_source` | Legacy non-file-URL hint only; true is not verified portability |
| `actions[].matches` | Exact requested bytes, or managed-section bytes, match existing content |
| `reconciliation_required` | Preserved differences requiring inspection; not permission to overwrite |
| `write_preflight` | Best-effort filesystem access check, not a transaction or tool-permission guarantee |
| `planned_writes` / `completed_writes` | Requested write set versus writes actually completed |

`applied: true` means the requested scaffold writes completed; preserved conflicts and runtime/CI
verification can still be outstanding. Existing policy/dependency files and managed sections are
never replaced. An existing bundle does not receive an undeclared starter module. Append preserves
the exact existing instruction prefix, BOM, line endings, trailing blank lines and mode.

All planned writes are preflighted before applying. A detected denial blocks all writes. An
unexpected mid-write failure returns exit 2 with JSON listing completed/remaining writes and an
uncertain file; inspect their bytes and permission boundaries before retry. Do not assume rollback
or silently redirect the canonical source to another folder. Invalid symlinks/markers are rejected.

By default the delivered AGENTS/CLAUDE section covers machine checks, navigation, rule design and
the requirement to leave existing reviews pending. For already-approved rubric obligations, add
`--rubric-handoff` together with `--instructions` to request full harness instructions. This does
not create rubric contracts or authorize their implementation/run. If a block already exists,
inspect its mismatch and merge approved changes at the maintained source; do not downgrade its
existing approved review obligations. See [instruction migration](instruction-migration.md).

## Markdown navigation policies

For `markdown-reachable`, install the same approved distribution with its `[markdown]` extra.
The helper accepts `repository-policy-linter[markdown]==0.4.2` or
`repository-policy-linter[markdown] @ <approved-wheel-URL>#sha256=<actual-digest>` as well as
the existing base requirement forms. Keep parser and transitive dependency pins identical
in local, CI and AF environments. No extra is needed for the base rules.

Choose explicit, existing repository-relative roots such as `AGENTS.md` and the selected
installed `.agents/skills/<name>/SKILL.md` or `.claude/skills/<name>/SKILL.md`. Do not treat
every skill as an implicit root or rely on personal skill paths outside the checkout.
The rule walks actual local Markdown/HTML links through all documents, even in changed mode.
Code examples and plain-text paths are not links. Missing roots fail the check.
Make new docs reachable through relevant guides or an index; preserve navigation conventions.
The CLI does not auto-insert links. Before enforcing, inspect the full graph report, repair
real gaps and retest link deletion in a disposable repository. Global exclusions remove
nodes; rule exclusions/exceptions suppress targets while preserving transit through them.

## pre-commit

Merge one local hook into existing `repos:`; retain comments, stages, exclusions and other hooks.
Use the existing environment manager when it provides a deterministic entry command:

```yaml
repos:
  - repo: local
    hooks:
      - id: repo-policy
        name: Repository policy
        language: system
        entry: .venv-policy/bin/repo-policy check --all
        pass_filenames: false
        always_run: true
        types: [file]
        require_serial: true
```

On Windows choose the `Scripts/repo-policy.exe` path or the repository's cross-platform launcher.
`always_run` and the all-file selection also enforce required paths on deletion-only commits.
A filename-only hook can be skipped when a commit only deletes a required document; use that
optimization only alongside a separate always-running structural check. Add `--allow-plugins`
only after reviewing the commands. A portable alternative is
`language: python` with exact engine `additional_dependencies`; specialist tools must then also
exist in that hook environment. Run `pre-commit validate-config` and `pre-commit run --all-files`.
Install Git hooks only when target setup authorization covers it; never overwrite custom hook
scripts. pre-commit normally stashes unstaged changes; direct CLI always checks working-tree
contents, not an independent index snapshot. Hook-only checks are not the platform trust boundary.
Describe each existing step separately: a newly added read-only policy step does not make an
older mutating hook read-only. Preserve its chosen behavior and report which steps write or stage.
See [official local-hook guidance](https://pre-commit.com/#repository-local-hooks).

## CI

If the repository requires a version increase per commit, explicitly add the built-in
`version-increment` rule with a canonical version source and an extraction regex containing
`(?P<version>...)`. Require an engine build from 0.3.1 onward. It runs even for deletion-only
changes, uses HEAD for pending tracked changes and first-parent comparison for clean/commit
checks. Stage new files before the final check; unrelated untracked files do not change the
baseline. Fetch at least two commits in CI; missing history is an error. Do not enable this rule
by default in projects without a versioning convention, or invent auto-increment fixes.

Extend existing CI with a pinned dependency installation and `repo-policy check --all`; prefer a
native manager/lock. For a PR incremental mode fetch sufficient history and use
`check --changed --base <trusted base ref>`. Missing history fails; never silently replace the base.
Establish baseline violations in a nonblocking pilot before enforcing. Do not run fix automatically
in CI. Keep plugins in a separately reviewed, pinned environment, with no credentials for fork runs.
Engine/runtime changes and policy changes must be visible in review.

Observation uses an explicit pilot or nonblocking integration, not an invented engine flag or a
forged success exit. Retain the actual failed report while the accepted adoption/repair plan is
resolved. Enable blocking only within the agreed rule/adoption scope. First-parent comparison
can use two commits; arbitrary merge-base checks may require more history. Local, index and exact
commit checks are distinct; neither an engine CI run nor workflow YAML proves target CI passed.

## Agent instructions

Keep definitions in `.repo-policy/` and explicitly connect thematic registries/contracts through
`policy.yaml`. Follow [contracts and ID navigation](contracts.md) for scope metadata and root
AGENTS guidance. Add commands and links to the maintained AGENTS/CLAUDE source, preserving
symlink/import/generated conventions;
the helper refuses a symlink rather than replacing it. If `.claude` is generated, update its source
and run the existing generator only when authorized. Record the clean/known-violations baseline.
Keep agent procedures and authorization requirements at their maintained source. Before moving
instructions or changing mirrors/roots, follow [the migration recipe](instruction-migration.md).

## AF Runner / platform observation

The platform uses the exact same package, policy and plugin toolchain. Within the selected checkout:

```text
repo-policy-af --root /session/work/repos/selected --session-root /session --output-dir /session/runs/<run-id>/policy-output --all
```

The wrapper returns the policy exit code, `report.json` and `outputs.fragment.json`. It never
overwrites Runner's result manifest. Runner can merge the fragment after applying its own artifact
and access policy; `publish` defaults to false. Do not invent Skill manifests: the AF native format
is a versioned declarative integration contract, not a `protocol: shell` package installer.

For gradual migration, run trusted push/PR checks on the exact head SHA in observation mode,
compare normalized local/Runner diagnostics using identical pins, then enable required checks by
explicit repository selection. Store SHA/config/engine/toolchain provenance, deduplicate events,
reject stale results and keep fork execution isolated. Server-side checks must use an approved
policy baseline so an agent cannot disable its own gate by changing config in the PR.
