---
created: 2026-10-26
updated: 2026-10-26
---

# Review guide: reproducible handoff

Applies to the `reproducible-handoff` criterion of the
[rubric-review-guide contract](../contracts/rubric-review-guide.yaml), described in its
[explanation](../readme/rubric-review-guide.md).

Evaluate whether a harness author can implement the documented workflow with the supplied
CLI and request schema. Use concrete guide locations as evidence. A worked example may use
illustrative IDs and hashes if they are labelled; it need not embed a harness implementation.

Pass when all of the following hold:

- The guide gives an operational sequence from machine check through independent review,
  persisted verdict, a failed review and repair, new input hashes/request identity, and
  final acceptance. At least one worked sequence connects the commands and saved records.
- Reviewer inputs and responsibilities are explicit: exact reviewed bytes, full contract,
  all requested rubric criteria, relevant references and diagnostics; no artifact edits or
  authority to waive policy. The harness verifies input identity before accepting a verdict.
- Verdict examples let an implementer distinguish the overall statuses from per-criterion
  results, record every requested criterion, and locate actionable evidence. Missing or
  unavailable review cannot be treated as passing.
- Storage examples make it clear that the real record contains the complete request and
  actual independent verdict, which identity it belongs to, and why a verdict for obsolete
  inputs cannot close a fresh request. The repair limit and blocked outcome are explicit.

Fail when an essential step or status convention is missing or ambiguous enough to require
the implementer to invent acceptance behavior. Explain the concrete consequence and a
minimal actionable correction. Do not require an engine-owned verdict store or automatic
agent dispatch: those are explicitly harness responsibilities in this MVP. Use `blocked`
only when evaluation cannot proceed because required review inputs are unavailable.
