---
created: 2026-10-27
updated: 2026-10-29
---

# Discovery and rule design

Use the narrow installation route for install/update tasks. Use the full inventory and catalog
when translating instructions or extending coverage. A large existing repository does not by
itself authorize an audit of every document. Preserve accepted work when continuing a migration.

## Scope and baseline

Resolve the selected Git root, current revision and status. Read applicable AGENTS/CLAUDE,
contribution guidance, existing policy, dependency manager, hook/CI and automation registry.
Search for existing generators, exporters and link/mirror tools by function and content as well
as filename. Reading a procedure as a normative source does not execute its commands or MCP work.

Identify the maintained canonical instructions, generated/imported copies and symlinks. Before
touching existing files record the relevant current bytes/hash, modes, symlink targets and index
state, including affected untracked data. HEAD alone cannot identify the user's preexisting dirty
changes. Keep scoped snapshots with appropriate access; do not publish secrets/raw input or scan
other workspaces to install one repository. See [preservation](data-preservation.md).

For updates, record why a new engine/guidance version is needed. Preserve the dependency manager
and current pins unless the task requires a change. Inventory output can summarize classes with
representative files; do not dump thousands of paths into the conversation.

## Artifact and source inventory

Classify by role, not extension: maintained author documents, native skills, generated indexes,
mirrors, external originals, released reports, archives and temporary material have different
obligations. Record paths/type/audience, native schema, canonical source, editability, known
history, navigation role and existing validator/generator. Preserve legitimate variants of a type;
an export file can be a UI artifact without becoming a technical report to satisfy a web schema.

For each normative source record its path, section, revision/hash, role and applicability.
Root instructions, scoped rules, commands, skills, README, templates and normative data can all
matter. A generated copy is not another authority; a template example is not a required enum,
calendar, status or field. Resolve source precedence and conflicts before enforcing a new meaning.
An inventoried source hash proves identity and inclusion, not full coverage of its contents.

Keep one canonical definition of executable requirements: policy/contract or the existing
validator's data. Instructions retain IDs, links, explanation and procedures. Generate duplicate
representations or check their consistency; do not maintain separate handwritten enums. A link
to SSOT may be sufficient for a short document; requiring it to repeat a table can be a checker bug.

## Inputs and proof classes

| Class | Required input | Appropriate implementation / limit |
| --- | --- | --- |
| M: snapshot fact | Selected files or full graph | Schema, arithmetic, IDs, existing links; does not prove meaning |
| D: change fact | Exact baseline/current bytes, paths and modes | Preservation/history mechanism; a current file alone is insufficient |
| X: external fact | Explicit revision-bound evidence snapshot | Separately acquired evidence, then offline validation |
| O: action or judgment | Responsible person or trusted harness | Procedure, real authorization or acceptance; not automatically a rubric |

M/D/X are machine candidates only with sufficient inputs. For required X input, define trigger,
revision, scope, collection time, completeness/pagination and provenance. Missing/stale input fails
when applicable; it need not block unrelated edits when the trigger is absent. Test both branches.
No hidden GitHub/Tracker/MCP network call belongs in routine lint. Hashes alone do not authenticate
the collection or prove its freshness. Leave unimplemented X visibly uncovered.

For every proposed rule ask whether simple, reliable machine enforcement is reasonable. Prefer
an installed built-in, a specialist check-only tool, then a small adapter using existing parsers
and public project APIs. A shared missing input/interface may justify an upstream mechanism;
domain policy stays in the target. Do not copy engine code or search another clone for a missing
baseline. Keep publication/PR/merge authority separate and prepare the exact diff/destination.

## Rule design card

This is an installation work product, **not engine configuration or a new CLI schema**:

```yaml
id: preserve-creation-metadata
source: rules/document-lifecycle.md#creation
source_revision: recorded-source-hash
class: D
fact: existing typed creation metadata is unchanged
applies_to: active authored documents; native skills use their own metadata mapping
inputs: exact selected baseline and current content
implementation: installed built-in where sufficient; otherwise reviewed adapter
missing_input: fail when applicable
does_not_prove: original authorship or meaningful updated-date freshness
examples: [valid-edit, changed-value, removed-key, legitimate-native-skill]
legacy: selected adoption mode and its decision source
state: proposed
```

Also specify selectors/ID uniqueness scope, severity/enforcement, exclusions, canonical definition,
positive and nearby valid counterexamples, negative cases and tests. A check name is not coverage.
Track proposed/accepted/implemented/verified/deferred requirements separately. New requirements,
contradictions or unknown facts need their actual evidence/owner decision; do not invent dates,
owners, durations, priorities or test results for a green report.

Verify glob semantics in the installed engine: `*` can match `/`; a middle `**/` must not be
assumed to match zero directories. Test active card, nested appendix, template, index, archive,
released copy, raw input and native SKILL where applicable. For [conditional contracts](contracts.md),
unconditionally validate mandatory classification metadata so deleting/changing a tag cannot
disable its obligations. No regex, nested lookup or type coercion is implied by `when.frontmatter`.

Use structured YAML/Markdown parsing, preserving strict header/type/duplicate-key behavior.
An example AC heading inside a fence is not an authored AC section. Do not prohibit extra fields
or reclassify correct artifacts without a source requirement. [Rule library](rule-library.md)
provides optional candidates; choose and adapt them, never import them as universal obligations.

For rubric proposals, use [reviews](reviews.md) only in approved scope. Explain why deterministic
checks are insufficient, what is reviewed, when it reruns and the expected resource cost.
An instruction-migration request does not silently authorize quality reviews of every file.
