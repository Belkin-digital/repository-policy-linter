---
created: 2026-10-29
updated: 2026-10-29
---

# Optional rule library

Candidates generalized from existing installations. Choose them against the selected project's
norms, roles and adoption decisions; neither the starter nor `configure.py` enables this library.
No rubric contract or automatic reviewer is included. Semantic remainder stays an explicit
limitation until a separately approved review is designed.

**Runnable examples** below ship actual YAML/Python and have disposable positive/negative tests.
**Adapter recipes** describe useful checks but ship no implementation. A recipe is not an engine
kind or a supported configuration field. Do not copy a command pointing to a nonexistent checker.
Use the [design card](rule-design.md#rule-design-card), [adoption guidance](data-preservation.md)
and [acceptance cases](acceptance.md) before enabling any candidate.

## Runnable examples

For each standalone registry, copy it into the target's `.repo-policy/checks/`, explicitly add its
path to manifest `registries` and select the desired IDs in `checks`. Merge rather than replace
an existing bundle. Adapt selectors/exclusions first; example paths/types are not project mandates.
IDs prefixed `example-` prevent accidental collision, but still inspect existing IDs.

### Foundation

[foundation.yaml](../assets/examples/foundation.yaml) has independent candidates:

| ID | Proves / does not prove | Adoption and negative case |
| --- | --- | --- |
| `example-readme` | A required regular README exists, even with empty selection; not useful content | Choose the actual entrypoint; delete it and check an empty selection |
| `example-data-syntax` | Selected JSON/YAML parses with duplicate-key rejection; not domain validity | Exclude preserved nonconforming inputs by role, with separate integrity checks; duplicate key must fail |
| `example-authored-newline` | Selected authored docs end in LF; not permission to alter raw bytes | Warning, no safe fix; missing LF must remain unchanged after check/fix |

Reuse the starter equivalents when appropriate rather than adding duplicates. These examples
exclude illustrative raw/released paths from authored text rules; they do not exempt their integrity.

### Authored dates and native skill metadata

[documentation.yaml](../assets/examples/documentation.yaml) separates authored documents from
native skills. `example-document-dates` requires creation/update keys and preserves existing
typed creation values; `example-native-skill-metadata` checks name/description presence, while
`example-native-skill-dates` uses `mapping_path: [metadata]` for dates.

Requires engine 0.4.0+ for `preserve_keys`, with local Git history. It does not prove date accuracy,
valid date format, full native skill schema, meaningful update freshness or rename ancestry.
Choose real authored paths before enabling; do not backfill originals or unknown dates. Tests
must cover changed/removed creation data, a new path, a native skill and protected raw exclusions.
Use an existing native skill validator for its complete schema.

### Classification before conditional contracts

The [typed-artifacts example](../assets/examples/typed-artifacts/policy.yaml) is a complete optional
policy bundle, with [registry](../assets/examples/typed-artifacts/checks/specifications.yaml),
[contract](../assets/examples/typed-artifacts/contracts/example-specification.yaml) and
[adapter](../assets/examples/typed-artifacts/scripts/check_spec_type.py). Copy/merge its resources
into the corresponding `.repo-policy/` directories; register every resource explicitly.

`example-specification-type` runs unconditionally on authored specification paths. It rejects a
missing, unknown or incorrectly typed `artifact_type`, even if that would stop the conditional
`example-specification` contract from matching. The contract then requires ID/title fields.
README and native skills elsewhere retain their own schemas. It proves classification and key
presence, not the completeness or correctness of a specification.

The illustrative canonical type is `specification` under `specs/`; adapt it only after identifying
the real artifact family and legitimate variants. Supply an existing `specs/README.md` scope
entrypoint with `repo_policy_contracts: [example-specification]`, a local contract link, and root
AGENTS frontmatter `repo_policy_root: .repo-policy`. See [navigation requirements](contracts.md).
Do not overwrite a target manifest or change a valid type to make a schema easier.

This is an explicit trusted file plugin, enabled with `--allow-plugins` after code review. It uses
the installed engine's strict parser/path helpers, caps input at 1 MiB and emits sanitized JSON.
Those helper imports are version-coupled example code, not a new stable public API; pin and test
the selected runtime (the helpers are present in 0.4.x). Tests include removed/unknown/numeric tag,
fenced fake metadata, damaged header, native SKILL isolation and exact committed inputs without
`.git`. If your existing classifier already does this, reuse it instead of adding another parser.

### Navigation

[navigation.yaml](../assets/examples/navigation.yaml) uses `example-document-navigation` to check
authored docs reachable from an actual `AGENTS.md`. It needs the `[markdown]` extra. Choose roots,
target classes, exclusions and archived/original handling from real entrypoints.

It proves graph reachability, not relevance or truth of links. Directory links resolve README.md,
not REGISTRY.md. A useful fixture is `AGENTS → docs/README → docs/REGISTRY → docs/guide`.
Remove a link or target, disconnect a group and check changed mode. Also test excluded transit:
rule target exclusion retains traversal; global exclusion removes the node. Mirrors can be
excluded as targets while remaining subject to an independent correspondence check.

## Adapter recipes

These need a project implementation and meaningful tests. Prefer the existing native tool/API;
review execution, limit inputs and use repository scope for cross-file/required-resource facts.
Every candidate below has a separate proof limit and adoption choice.

| Candidate | Required inputs and proved fact | Adoption, negative example and proof limit |
| --- | --- | --- |
| Artifact identity/references | Accepted ID scope and full graph; unique active IDs and resolvable typed references | Decide local vs global identity and archive roles; duplicate ID or deleted target must fail even with unchanged referers; existence does not prove semantic relation |
| Generated registry drift | Same canonical parser/model and reviewed read-only generator; generated representation matches source | Establish manual/unknown-field round-trip first; altered row fails without any byte/mode/index write; current output is not more truthful than unknown historical data |
| Native format/schema | Existing validator with pinned schema/tool version; structured format conforms | Choose each native role; malformed field fails, legitimate variant passes; syntax/schema does not prove content completeness |
| Original integrity | Provenance registry, exact saved bytes/size/SHA and accepted operations; registered original is unchanged | Register/move/derive explicitly; a modified original fails, checker never refreshes its own hash; identity does not prove authorship or permission |
| Historical adoption | Accepted rule/class boundary plus fixed path/content baseline as needed; identifies new/changed editions | Missing/old dates and new paths must follow the selected model; changed body must not update its own exemption; a date alone is not immutable history |
| Report arithmetic | Report's own declared rows/totals/counting model; internal numbers agree | Preserve released results; mismatched total fails without rebuilding from today's sources; consistency is not a new test execution or sufficient coverage |
| Mirror drift | Canonical files, registered ownership and target map; mirrors correspond | Manual/unknown target must fail before overwrite; sync is a separate authorized action; byte equality does not prove every agent loads the skill |
| Norm-source mapping | Source revisions and explicit mapping; detects changed/unmapped normative sources | Require a meaningful mapping review, not auto-rehash; new source triggers unresolved coverage; a hash inventory does not prove every norm implemented |
| Visible-text terminology | Canonical glossary, audience/exporter/quote/adoption profile; matches accepted lexical rules | Exercise the same examples at real entrypoints; allowed code/URL differs from prose; no universal English ban or semantic translation verdict |
| External evidence consistency | Separately acquired revision/scope/time/completeness-bound snapshot; offline references agree | Missing/stale evidence fails only on its required trigger; unrelated edit without trigger passes; no implicit network or forged approval |
| Change preservation | Supported exact baseline/current paths, bytes, modes and operations; accepted changes preserve required facts | Test rename/delete/type/mode/missing history; 0.4.x `preserve_keys` is only same-path metadata, not arbitrary plugin Git context; report capability gaps instead of looking for another clone |

For terminology use the [language profile](language-policy.md); for originals/adoption use
[preservation](data-preservation.md); for mirrors and link moves use
[instruction migration](instruction-migration.md). Do not transplant client IDs, calendars,
enums, folders, cutoffs or a per-commit version policy from another project.
