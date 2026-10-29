---
created: 2026-10-29
updated: 2026-10-29
---

# Data preservation and adoption

Read before changing a generator, repairing existing documents, registering originals or adding
history-dependent requirements. Apply the selected repository's own rules; the engine's newline
fix capability does not authorize edits to protected input.

## Preserve the current state

Capture a scoped before snapshot of affected tracked/untracked bytes, hashes, modes, symlinks
and index state. Preserve dirty user work separately from the installer's delta. Use the existing
archive/Git mechanism where it preserves the actual inputs; uncommitted versions need their own
snapshot. Do not commit someone else's whole working tree to obtain a baseline.

Keep private backups and run outputs ignored with appropriate access. Publish maintained tests
and generalized explanations, not client documents or raw evidence. Before/after proof is scoped
to its named baseline and package of work, not an assertion that no file ever changed.

## Choose adoption per rule and artifact class

| Mode | Define before applying it |
| --- | --- |
| Immediate conformity | Existing obligation, exact findings, reliable fixes and authority |
| New/changed editions | Activation boundary, new paths, content changes, missing/invalid dates, moves |
| Immutable historical edition | Exact original bytes, provenance and how to create a derivative |
| Narrow exception | Rule/path/finding, reason, decision source and expiry/review condition |
| Archive | Inactive status, preserved original and redirects/updated live references |

Do not choose a mode merely because there are many findings. A date is not a content fingerprint;
a fingerprint does not establish a creation date. Define metadata-only versus substantive edits
and rename behavior explicitly. A new path with an old or absent date must not silently qualify
as accepted history. A project may choose a date-only model, but record that model's limitations.
Never advance an adoption/integrity baseline during ordinary validation.

Unknown dates/statuses require distinct decisions: recover from evidence, preserve an explicitly
allowed unknown value or obtain the actual owner's choice. Midnight, commit time or a filename
is not sufficient authorship evidence. `preserve_keys` only preserves existing typed values at
the same path; it does not prove dates, rename lineage or whether `updated` must change.

For exact legacy debt, bind entries to rule/file/code and a stable finding/content fingerprint,
reason, necessary count and before/after hashes. New findings must not inherit an old waiver;
detect stale entries or expire them according to the accepted model. The checker does not add to
its own allowlist. A ledger records a known state, not the authority to accept it. Avoid a blanket
directory ignore or lowering an entire schema's severity to conceal new violations.

## Generators and historical results

Before enabling drift as a gate, run the reviewed generator without writes and classify every
difference: true drift, generator defect, manual information or an unresolved norm. Verify that
check-mode detects drift with its documented return code and preserves bytes/modes/index.

Demonstrate round-trip preservation on representative accepted inputs, including manual columns,
unknown values, formatting, BOM/CRLF and invalid data where relevant. Reuse one parser/model for
generation and checking. Fix a lossy generator before mass writes. Do not replace an unknown
duration/date with an inferred value because a generator can calculate it. An explicit supplemental
source can retain known legacy facts, bound to source bytes and a reason; stale bindings require
review, not automatic rehashing.

Historical test results must not be rebuilt from today's changed scenarios and called repaired.
Separate internal arithmetic, original integrity and reproducibility from the original inputs
(generator revision, source revisions, selection, parameters and environment). Missing historical
inputs limit reproducibility; they do not prove the old result was wrong. Changes to test scope,
verdicts or counters are distinct decisions from editorial changes.

## Originals and explicit edits

Registering a new original, moving the same object and creating a derivative are different
operations. Preserve identity/provenance and earlier records; do not update a changed original's
hash to make it pass. Excluding raw/archive from new prose schemas does not remove integrity
obligations. Do not add authored frontmatter to native external inputs or rewrite released bytes.

When a newline repair on protected data is explicitly allowed, operate on bytes and verify
`after == before + b'\n'`, with modes and unrelated data unchanged. Do not decode/re-encode,
normalize all line endings, refresh dates or reformat under the safe-fix label.

Classify diagnostics before edits: checker/selector bug, representation defect, real artifact
violation, missing evidence or a substantive choice. Correct false positives at the checker and
retain a counterexample. For a substantive choice, use the concrete decision record in
[acceptance](acceptance.md#decisions-and-current-state); continue independent work within scope.
