---
created: 2026-10-29
updated: 2026-10-29
---

# Acceptance, decisions and handoff

Verify the affected implementation and repository-mandated checks within the user's constraints.
Skipped tests/network/CI/review are `not-run` with a reason, not `passed` or `not-applicable`.
Do not replay a full migration after a narrow documentation update. After relevant checks pass,
repeat or broaden them only for new changes, failures or unresolved concerns.

## Meaningful verification

Use maintained tests with disposable repositories and fictional data for changed helpers/adapters.
Choose positive, negative and nearby valid cases according to the changed behavior:

| Area | Cases and evidence |
| --- | --- |
| Scaffold/update | Preview has no writes; second apply is unchanged; existing mismatches remain visible |
| Preservation | Dirty/untracked bytes, CRLF/BOM, modes, symlinks, index; blocked/partial write destinations |
| Schema/selector | Bad YAML types/duplicates/unclosed header; removed or changed type; appendix/template/fence/native skill |
| Cross-file check | Empty selection, deletion-only, removed target still referenced by unchanged sources |
| Generator | Round-trip, meaningful drift return, no check-mode writes, manual/unknown fields |
| History | Correct baseline, exact commit without .git, rename/delete/type/mode, insufficient history |
| External evidence | Applicable and absent trigger; missing, stale or incomplete input |
| Integration | Correct pinned runtime/tool PATH, parser extra, timeout/error propagation and real target CI |

Isolate hooks/signing/autocrlf and relevant inherited Git defaults in test fixtures. Use bytes for
identity; exercise platform-sensitive cases when claiming support. A successful macOS run does not
prove Windows support. Tests of wording alone do not demonstrate the installer's decisions.

Use the maintained launcher and record actual commands, version, config/tool hashes, selection,
revision/baseline and exit codes. Full `--all`, working-tree `--changed` and exact `--commit SHA`
cover different states. Do not stage/commit unrelated user work just to obtain a snapshot.
pre-commit may stash unstaged changes; direct CLI is not a staged-only validator. Run history
cases only with supported capabilities; missing required history is an error, not an empty baseline.

When installation/runtime delivery changed and verification is authorized, obtain the declared
artifact/source in a new environment without an old editable engine or dependency on the author's
clone. Verify digest, lock/build-tool provenance and imports from the noneditable installed wheel;
run a small init/check smoke. Repeat helper setup when the helper changed. A local file/cache only
proves that local route. A remote distribution's availability, cold installation and target CI are
separate observations. Do not silently replace an unavailable release with `main`.

For behavioral skill evaluation, use realistic disposable scenarios and inspect resulting diffs
and receipts when delegation is authorized. Helper tests alone do not prove an agent classified
every norm or handled every owner decision correctly. State which kind of validation occurred.

## Decisions and current state

Classify each finding before proposing edits: real violation, checker/selector defect, legitimate
artifact variant, presentation issue, missing evidence or disputed meaning. Correct a false
positive with a regression case; do not change good documents to fit a bad rule.

For a material proposal show its stable ID, full path/section, exact fragment, source norm,
plain-language rule and why it applies, before/after or diff, effects on identities/history/links/
verdicts/counters and independent choices. Changing test scope and carrying forward an old result
may require different decisions. Fix routine authorized typos without inventing an approval step.

Keep one current decision ledger: item ID, proposed diff/revision, actual owner decision source,
scope and `proposed / approved / applied / verified / superseded`. An installer-created
`approved: true` does not create authority. Apply an existing decision without asking again when
the delta and consequences match; show only genuinely new consequences when the proposal changes.
Update state after application/verification; keep history distinct so accepted work is not
mistaken for an unresolved old proposal. Save scoped originals before substantive authorized edits.

## One current receipt

Use the project's existing format. This compact template is an installation report, **not new
engine fields, exit codes, permission evidence or an extra policy file required in every repo**:

| Area | Status and concrete evidence |
| --- | --- |
| Scope | Selected root, task mode, allowed delta, Git/dirty baseline |
| Runtime | Engine version, source commit, artifact digest, availability and cold-install outcome |
| Toolchain | Python, extras/parsers/tools/build dependencies, lock and canonical launcher |
| Policy/coverage | Entry point, IDs, normative sources, realized M/D/X facts and remaining O duties |
| Adoption | Rule/class modes, originals, exact exceptions, decision sources and preserved baseline |
| Changes | Installer delta versus original dirty work, completed/uncertain writes, mirrors/links |
| Machine result | Full and incremental snapshot/selection, versions, commands, actual exit/diagnostics |
| Decisions | Applied/verified/current pending items with exact proposed changes |
| Hooks/CI | Actual mode, which step blocks/writes, run URL/SHA and verified environments |
| Rubric | Not configured, proposed, approved/pending or current hash-matched verdicts |
| Remainder | Checker bugs, artifact violations, unimplemented checks, missing evidence and decisions |

Use `passed / failed / not-run / not-applicable` with reasons. Preserve failed and historical
receipts; do not total diagnostics from different scopes or call a smaller selection progress.
Inventory/test counts do not measure complete semantic coverage. Local success is not target CI;
engine CI is not consumer CI; platform objects do not exist until actually created.

Installation-only completion does not claim all instructions migrated. Migration completion
requires accounting for each applicable norm and proving the implemented machine portion; a
deferred required X input remains a gap. Independent queues can finish while the actual overall
machine result stays failed/blocked. Distinguish changed documents, changed rules and corrected
checkers when explaining why diagnostics disappeared.

Use [the review protocol](reviews.md) for existing approved obligations. A machine success or
one accepted pilot does not accept every artifact. Do not add rubric to close an unimplemented
script queue, invent costs, run reviewers beyond scope or self-author a positive verdict.
Report actual costs when available and leave unavailable reviewers/inputs pending or blocked.
