---
created: 2026-10-26
updated: 2026-10-27
---

# Policy bundles and artifact contracts

Keep acceptance definitions and repository-specific Python checks in the target repository's
`.repo-policy/` directory. The installed package supplies the engine and automatic system checks;
the standalone setup skill supplies initial configuration without vendoring engine source.

```text
.repo-policy/
  policy.yaml                   # Manifest, global checks and explicit module lists
  requirements.txt              # Optional pinned external tool dependency
  checks/
    common.yaml                 # Check definitions, schema version 2
    api.yaml
  contracts/
    api-description.yaml        # Contract ID equals filename stem
  readme/
    api-description.md          # Optional explanation with the same ID
  rubrics/
    api-error-explanations.md    # Required if referenced by a rubric criterion
  scripts/
    check_api_errors.py         # Explicitly trusted external Python checker
  examples/
    api-description/            # Optional accepted/rejected examples
```

Only `policy.yaml` is required; create optional directories when needed. `requirements.txt`
is used by generic setup, while repositories with a tool manager can pin in their existing lock.
The four data directories (`checks`, `contracts`, `readme`, `rubrics`) are flat; their filenames
use lowercase ID syntax and `.yaml` or `.md` respectively. Scripts may use Python packages and
nested `.py` files. Examples can contain arbitrary regular files. Symlinks anywhere in the policy
directory are rejected. Generated `__pycache__` and `.DS_Store` entries are ignored.

All configuration resource paths, artifact patterns and plugin commands are relative to the
repository root, including when the manifest is nested. Moving a YAML file does not rebase paths.
Default discovery reads exactly `.repo-policy/policy.yaml`, never a parent directory or the old
root `.repo-policy.yaml`. There is one policy format, **version 2**, with no legacy fallback.
`--config PATH` can explicitly select another version-2 manifest inside a policy directory;
the same directory structure and system checks apply there.

## Manifest and thematic registries

Example `.repo-policy/policy.yaml`:

```yaml
version: 2
exclude: ['dist/*', 'build/*']
registries:
  - .repo-policy/checks/common.yaml
  - .repo-policy/checks/api.yaml
checks: [readme, data-syntax]
contracts:
  - .repo-policy/contracts/api-description.yaml
```

`registries` and `contracts` explicitly list local files; recursive imports, remote imports,
environment expansion and executable discovery are unsupported. Every registry and contract
file present in the corresponding directory must be listed. Unknown top-level policy entries,
wrong extensions, orphan contract explanations and missing declared resources are errors.
Registration order never overrides definitions. A registry makes definitions available; its
checks run when selected by `checks` or a contract criterion. The same check can serve several
contracts. An unreferenced definition does not run.

Example `.repo-policy/checks/common.yaml`:

```yaml
version: 2
rules:
  - id: readme
    kind: required-path
    path: README.md
  - id: data-syntax
    kind: syntax
    files: ['*.json', '*.yaml', '*.yml']
```

Registries permit only `version`, `rules` and `plugins`. Their check entries use the existing
[rule schema](configuration.md) and [explicit plugin protocol](plugins.md). Small manifests may
also define inline `rules`/`plugins`; these are always active. Keep growing definitions in
thematic registries. Root-level `exclude`, `exceptions` and `max_file_bytes` apply across the
assembled policy. Reasoned exceptions refer to actual check IDs, including registry definitions.

## Contracts and selection

Example `.repo-policy/contracts/api-description.yaml`:

```yaml
contract_version: 1
id: api-description
files: ['docs/api/*']
exclude: ['docs/api/archive/*']
entrypoints: [docs/api/README.md]
criteria:
  - id: metadata
    rule: api-metadata
  - id: error-coverage
    rule: api-error-coverage
```

The referenced check IDs must exist in loaded registries or inline definitions. Each criterion
has a local ID and exactly one `rule` or `rubric` reference. Contract IDs and check/plugin IDs
share one global unique namespace; criterion IDs are unique within their contract, identified
as `contract-id/criterion-id`. All IDs match `[a-z][a-z0-9-]{0,63}`. `engine` and `system-*` are
reserved. Explanation naming is exact: `readme/<contract-id>.md`, with no explanation required.
The explanation provides rationale and examples; criteria remain in the contract and referenced
rubrics, never implicitly extracted from prose.

Contract file selection uses the same case-sensitive POSIX `fnmatch` dialect as rules:
`*` matches `/`, so `docs/api/*` includes descendants. Leading `**/` also matches zero directory
levels. This is not path regexp or gitignore; use explicit `exclude` for suppressions.
File checks use the intersection of contract selectors and check selectors. Multiple matching
contracts add requirements; none can override another or weaken global checks. Required-path
and version-increment checks retain their structural meaning and run even when the artifact is
missing or selection is empty. Graph checks traverse all Markdown, while contract scope restricts
their target set.

### Selecting by frontmatter

Contracts may additionally declare `when.frontmatter`. For example, the same contract can
select requirements throughout a repository without relying on their directory names:

```yaml
contract_version: 1
id: requirement-quality
files: ['**/*.md']
when:
  frontmatter:
    artifact_type: requirement
    status: [draft, approved]
entrypoints: [AGENTS.md]
criteria:
  - id: explanation
    rubric: .repo-policy/rubrics/requirement-quality.md
```

An artifact with `artifact_type: requirement` and `status: draft` or `status: approved` in its
opening YAML frontmatter matches. The root navigation entrypoint must declare this contract
ID, and the referenced rubric must exist, just as for path-only contracts.

- `files`, `exclude` and the metadata conditions are combined: the path must match and
  **every** named field must match. A string means exact equality; a nonempty list of strings
  means any of those values. Comparisons are case-sensitive, with no glob/regexp expansion
  or type coercion. Quote YAML values that would otherwise become booleans, numbers or dates.
- Field names are literal top-level keys. `metadata.artifact_type` names a literal dotted
  key, not a nested lookup. Nested predicates and arbitrary expressions are unsupported.
- Missing frontmatter, empty frontmatter, missing fields and non-string field values do not
  match. Without `when`, selection retains its existing path-only behavior, including for
  files that have no parseable frontmatter.
- An opening `---` must have a closing `---`. Malformed/non-mapping YAML, duplicate keys,
  aliases, invalid UTF-8 or NUL within the header fail with exit **2** rather than silently
  skipping the contract. Only path candidates are inspected, after exclusions. Matching
  candidates are considered even in a partial check, so an unselected malformed header
  cannot silently make the applicability set incomplete.
- Headers use LF or CRLF; the selector caches parsed headers per run and bounds them by
  `max_file_bytes`.
  The selector does not decode or load the body; machine checks keep their existing body
  limits. Conditions need only the core PyYAML dependency, not the Markdown extra.

This is an optional extension of `contract_version: 1`; manifests remain `version: 2`.
Pin an engine build that supports conditions: older builds reject the unknown field. The
same predicate controls scoped machine checks, trusted plugins, graph targets, contract
results and rubric requests. Global checks and structural requirements remain in force.

`--commit` reads metadata from the exact committed snapshot, never from dirty working files.
A contract or rubric edit rechecks all **currently matching** artifacts, including unchanged
ones. Editing an artifact's type can move it into or out of a contract. If tags are mandatory,
keep an unconditional base contract/check that validates their presence and allowed values;
conditional selection alone does not prevent someone from removing/changing a tag. Enforcement
of approved policy baselines remains the surrounding platform's responsibility.

## Discovering contracts before editing

Each contract declares one or more repository-local `README.md` or `AGENTS.md` entrypoints.
Put the following metadata in `docs/api/README.md` (merge with its existing frontmatter):

```yaml
---
repo_policy_contracts: [api-description]
---
```

Add human-readable links below the metadata:

```markdown
- [api-description](../../.repo-policy/contracts/api-description.yaml)
  — [explanation](../../.repo-policy/readme/api-description.md).
```

Link explanations only when they exist. A scope entrypoint covers descendants; do not repeat
the index in every nested folder. The YAML contract is authoritative: removing a navigation
pointer cannot deactivate its criteria. The built-in check reads declared entrypoints even
when excluded or absent from `--changed`/`--files`. It also checks unknown or duplicate IDs in
annotated README/AGENTS files discovered across the repository, independent of policy excludes.
Policy examples are excluded from this extra navigation-index scan.

When contracts exist, root `AGENTS.md` must declare `repo_policy_root: .repo-policy` in its
frontmatter (or the explicitly selected policy directory). Describe the route there: inspect
scope metadata, resolve `.repo-policy/contracts/<id>.yaml` and optional `.repo-policy/readme/<id>.md`,
then read criteria before editing. An alternative that resolves the same IDs is:

```bash
repo-policy explain api-description
```

It returns the contract, its path and optional explanation path/content without running plugins.
The same command resolves check IDs and the built-in `system-*` check descriptions.
Configured IDs take precedence over rule-kind names; `explain --kind syntax` explicitly
selects built-in kind help even if a contract or check is named `syntax`.

## Python check implementations

Repository-specific checker code lives in `.repo-policy/scripts/`; the package's own built-in
system checks stay in the installed engine. Merely adding a `.py` file does not execute it.
Declare a plugin in a thematic registry, reference its ID globally or from a contract, pin its
runtime/dependencies, and explicitly authorize invocation with `--allow-plugins`:

```yaml
version: 2
plugins:
  - id: api-error-coverage
    command: [python, .repo-policy/scripts/check_api_errors.py, '{files}']
    format: json
    files: ['docs/api/*.md']
```

The script receives selected root-relative filenames and emits JSON diagnostics to stdout.
It runs in the checkout with caller permissions and environment. This is not a sandbox;
platform checks of untrusted code require external containment. The repository's reviewed
[setup asset checker](../.repo-policy/scripts/check_setup_assets.py) is a working example.

## Automatic system checks and results

These checks ship in the base engine, without optional dependencies or configuration entries:

| ID | Enforcement |
| --- | --- |
| `system-policy-structure` | Validate directory layout, schemas, declared resources, filenames and references |
| `system-unique-ids` | Reject duplicate/reserved check and contract IDs; duplicate criterion IDs within a contract |
| `system-contract-navigation` | Validate scope ID indexes and the root navigation location |
| `system-contract-review` | Generate hashed external review requests for rubric criteria |

Configuration/structure/ID failures return **2** before fixes or plugin execution. Navigation
violations produce ordinary, non-fixable error diagnostics and return **1**. These checks cannot
be removed through `checks`, contract selectors, file selection, exclusions or reasoned exceptions.
The configuration lists no `system-*` entries. Only the final-newline rule supports engine fixes.

JSON diagnostics retain schema version **1** and the existing fields and ordering. With contracts,
the report additionally includes `contracts`, sorted by ID, containing targets, checked files and
per-criterion statuses: `satisfied`, `failed`, `partial`, `not_evaluated`, or `needs_review`.
A successful partial lint run does not establish complete artifact acceptance. Acceptance requires
the global/system checks to pass and all mandatory contract criteria to be satisfied.
A failed mandatory criterion returns 1 even if its check emits only warning/info diagnostics.
For commit-scoped acceptance the harness handles the current affected artifacts; unchanged,
unaffected files can leave a broader contract summary `partial` or `not_evaluated`.

A rubric criterion uses `rubric: .repo-policy/rubrics/<name>.md` instead of `rule`. The referenced
file must exist. Selected or invalidated artifacts produce `needs_review` and hashed
`review_requests`; pending review alone does not fail machine checks. The current harness must
dispatch subagents, store input-matched verdicts and coordinate repairs. The core never contacts
an LLM, imports verdicts or pretends to have assessed prose. See the
[commit and review protocol](rubric-review.md) for hashes, invalidation and the completion gate.

Keep execution reports outside the policy source. The AF bridge still writes into the selected
session output directory outside the checkout and invokes exactly the same engine. See
[Agent Factory integration](agent-factory.md) for execution boundaries and policy baseline trust.
