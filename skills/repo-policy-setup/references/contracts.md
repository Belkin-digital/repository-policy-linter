---
created: 2026-10-26
updated: 2026-10-27
---

# Bundle configuration and contract navigation

The only default manifest is `.repo-policy/policy.yaml`, schema `version: 2`. All resource
paths and artifact selectors are repository-relative. Do not add a legacy root config or
vendor the engine. Optional directories are created when used, without empty placeholders.

- `checks/<topic>.yaml`: `version: 2`, `rules` and/or `plugins`; explicitly listed in manifest
  `registries`. Definitions run when referenced in manifest `checks` or a contract criterion.
- `contracts/<id>.yaml`: explicitly listed in manifest `contracts`; `contract_version: 1`,
  `id`, nonempty `files`, optional `exclude`/`when`, nonempty `entrypoints`, nonempty `criteria`.
- `readme/<id>.md`: optional contract explanation. Match the ID exactly; keep normative
  criteria in the YAML and referenced rubrics.
- `rubrics/<name>.md`: required local resource when a criterion references it.
- `scripts/`: repository-specific Python check implementations, including nested `.py` modules.
- `examples/`: optional regular-file examples. No symlinks in the policy directory.

Check/plugin and contract IDs share a global namespace. Criterion IDs are local to their
contract. IDs use `[a-z][a-z0-9-]{0,63}`; `engine` and `system-*` are reserved. Each criterion
has `id` and exactly one `rule: <check-id>` or `rubric: <repo-relative-md-path>`.
Repository-level `required-path`, `version-increment` and `scope: repository` plugins retain their structural meaning
even when the artifact selection is empty. File checks use the intersection of contract selectors
and check selectors. All matching contracts add requirements. Keep general checks active via
the manifest's `checks` list.

Contract example (requires check `spec-metadata` in a loaded registry):

```yaml
contract_version: 1
id: specification
files: ['specs/*']
entrypoints: [specs/README.md]
criteria:
  - id: metadata
    rule: spec-metadata
```

To select by artifact metadata as well as path, add conditions to the contract:

```yaml
when:
  frontmatter:
    artifact_type: specification
    status: [draft, approved]
```

All fields must match: a string is exact equality; a nonempty string list is an allowed-value
set. Keys are literal top-level names and values must be strings, without coercion or regexp
matching. Missing metadata/fields or non-string values do not match. Without `when`, contracts
remain path-only. Invalid YAML headers, duplicate keys, aliases and unterminated headers fail
with exit 2; they cannot silently exclude an artifact. The header is bounded by the configured
`max_file_bytes`, independent of the body, and needs no Markdown extra.

Apply the same scope to machine checks and rubric handoffs. `--commit` uses committed metadata;
contract/rubric edits include all currently matching artifacts. Keep unconditional validation
of required tags and allowed artifact types when removing a tag must not disable obligations.
Pin a build that supports `when`; older builds reject it. Do not invent nested lookups or
expression syntax. Keep existing path selectors and navigation entrypoints alongside conditions.

Merge `repo_policy_contracts: [specification]` into the frontmatter of each declared scope
entrypoint, using an existing `README.md` or `AGENTS.md` at the scope root. Add local Markdown
links to the contract and its explanation when present, preserving existing content/dates.
Root `AGENTS.md` must carry `repo_policy_root: .repo-policy` in frontmatter when contracts
exist. Explain its navigation route: inspect scope metadata, read `contracts/<id>.yaml` and
optional `readme/<id>.md`, or run `repo-policy explain <id>` before editing. Preserve any
CLAUDE import/symlink convention. Removing a pointer must not deactivate a contract.

The base engine checks directory structure, unique IDs, references and navigation on every
run. Do not configure these as removable rules. Resolve system failures before enabling
plugins. Register Python scripts as explicit JSON/regex plugins, for example:

```yaml
version: 2
plugins:
  - id: spec-links
    command: [python, .repo-policy/scripts/check_spec_links.py, '{files}']
    format: json
    files: ['specs/*.md']
```

Use the repository's pinned Python runtime; review code and commands before `--allow-plugins`.
Scripts execute with caller permissions and are not sandboxed. Never copy package built-ins
into `scripts/`. Rubric criteria remain `needs_review` and produce hashed `review_requests` for
the current harness. Follow the [review handoff](reviews.md); the core performs no LLM calls,
dispatches no agents and invents no verdicts. Pending review does not itself fail machine checks.

For cross-file/required metadata checks, engine 0.4.0 supports `scope: repository` on a plugin.
It runs even with no selected/input files; `files`/`exclude` declare permitted diagnostic paths,
including missing required files. File selection/global exclusions/contract selectors do not
waive it; explicit reasoned exceptions can. Review commands before `--allow-plugins`. The checker
must not expect `.git` in committed snapshots. Use ordinary file scope for artifact checks.

For immutable creation fields, a `frontmatter` rule may opt into `preserve_keys: [created]`
with the same `mapping_path` as its required keys. It compares typed values at the same Git path;
Git history is then required. It does not infer rename lineage, original authorship or semantic
freshness. Preserve existing dates and establish missing values from evidence.

After configuration, inspect `explain <id>`, run all/changed checks and repository tests.
A partial check's exit 0 does not establish full contract acceptance. Report any non-satisfied
contract criteria and the same bundle/toolchain requirements for local, CI and AF execution.
