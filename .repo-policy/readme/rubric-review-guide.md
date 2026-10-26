---
created: 2026-10-26
updated: 2026-10-26
---

# rubric-review-guide

The [contract](../contracts/rubric-review-guide.yaml) binds only the
[rubric review guide](../../docs/rubric-review.md). It exercises the project's own external
review handoff: machine success creates an obligation for an independent reviewing subagent.
The general [documentation contract](documentation.md) still checks Markdown dates.

The rubric criteria are:

- [Implementation accuracy](../rubrics/review-guide-accuracy.md): claims and examples agree
  with the engine, public report schema and execution boundaries.
- [Reproducible handoff](../rubrics/review-guide-handoff.md): a harness author can carry out
  review, persistence, repairs and final acceptance without guessing essential steps.

Resolve this contract with `uv run --frozen repo-policy explain rubric-review-guide`.
Navigation starts at the [docs index](../../docs/README.md). The selectors above remain
authoritative; listing this ID in the index does not bind every document in that directory.

The reviewer reads the exact artifact, contract and both rubric files named in the request,
plus the relevant engine source, tests and machine report from the same snapshot. It does
not edit those inputs. The harness verifies their hashes, records the complete request and
the actual independent verdict in ignored `work/<run>/repo-policy/reviews/<request_id>.json`,
and requests a fresh review after repairs. Verdict files are run evidence, not policy source;
the engine continues to emit the obligation even after a harness accepts a matching verdict.
