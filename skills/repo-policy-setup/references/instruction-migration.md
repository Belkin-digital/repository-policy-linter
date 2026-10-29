---
created: 2026-10-29
updated: 2026-10-29
---

# Instruction migration, mirrors and navigation

Use only when the task includes changing instruction delivery, canonical paths or navigation.
Installing the linter does not require moving all rules/commands into skills or choosing `.agents`.

Record the chosen canonical source, each agent's loader/import/symlink and the role of copies.
Executable definitions live in policy/contract or a validator's canonical data; maintained
instructions keep discovery links, IDs, reasons, workflows and human responsibilities. Coverage
of norms and delivery of instructions are separate checks. Do not delete process instructions
after implementing a format checker or independently copy enums into instructions and code.

## Preflight and mirrors

Inspect all planned destinations, including canonical files, mirrors, archives, config and index.
User authority and a tool's actual write permissions are different. A denied destination does
not justify silently changing the chosen canonical location. Preserve symlinks; merge at their
maintained source. The configure helper refuses a symlink rather than replacing it.

For existing managed blocks inspect the requested delta and `matches: false`. Preserve accepted
rubric guidance during a script-only update; merge approved changes manually rather than dropping
instructions or replacing the whole file. A preserved but different block is not a completed upgrade.

Mirrors need ownership, source/target mapping and a read-only drift check. Check every target before
sync; manual changes or unknown files stop destructive overwrite. Remove only registered unchanged
copies under the project's accepted cleanup rules. Protect canonical paths and symlink boundaries.
Sync/generation is an explicit mutating action, never part of lint. Do not simply exclude mirrors
from every check; they have correspondence obligations even when excluded as navigation targets.

If a write sequence partially completes, record completed/uncertain/remaining paths and verify
their hashes before continuing. A preflight is not a filesystem transaction or guarantee of tool
permission; preserve unknown leftovers instead of overwriting them on retry.

## Moves and links

Find existing automation by behavior (relink, move, rename, rebase, relative links), not just the
expected filename. Establish each tool's real coverage. A utility that updates incoming Markdown
links does not necessarily move files, rebase outgoing links or update YAML/configuration.

Check the complete applicable relocation map:

1. Incoming references to the old path.
2. Outgoing relative links after changing depth, plus anchors, labels, images, reference links and
   URL encoding supported by the parser.
3. Paths in metadata, loaders, config and literal instructions.
4. Live historical indexes/README that need derivative editions while original bytes remain saved.
5. HTTP(S) links containing old repository paths and the explicitly reachable external scope.
6. Mirror targets, ownership manifests and removal/redirect plans.

Handle fenced examples and immutable originals according to their roles, not a global replacement.
Unknown external consumers remain a limitation. A successful internal link pass cannot prove all
external sites were updated. Preserve expected IDs, code literals and stable anchors.

## Reachability model

Choose existing subject indexes and entrypoints rather than a synthetic list of every document.
Distinguish roots, transit nodes and required targets. Independently callable skills can be chosen
as explicit roots; their resources should link from SKILL. Mirrors are not automatically roots.
Temporary/archive groups need an actual adoption decision, not a graph-based inference of purpose.

In the tested 0.4.x model a directory link resolves an existing README.md; it does not automatically
discover REGISTRY.md. Thus `AGENTS → docs/README → REGISTRY → document` needs real links at every
step. An instruction saying "look for a registry" creates no graph edge. Global exclusions remove
nodes; a rule target exclusion can retain traversal through the document. Test deletion of a link,
a disconnected group, an excluded transit node and README/REGISTRY separately. See the
[navigation example](rule-library.md#navigation) and [integration](integration.md#markdown-navigation-policies).
