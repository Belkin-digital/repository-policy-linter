---
created: 2026-10-26
updated: 2026-10-26
---

# Review guide: implementation accuracy

Applies to the `implementation-accuracy` criterion of the
[rubric-review-guide contract](../contracts/rubric-review-guide.yaml), described in its
[explanation](../readme/rubric-review-guide.md).

Evaluate the guide against the supplied snapshot's CLI, engine, request construction,
snapshot handling and relevant tests. Cite concrete guide locations and corroborating
source/test locations; do not assume that machine success establishes factual accuracy.

Pass when all of the following hold:

- Selection, invalidation and deletion/rename behavior match the implementation for commit
  and working-tree modes. Limits of the selected baseline and reference dependencies are clear.
- Report fields, JSON types, request identity and hashing are described consistently with
  the implementation. Examples distinguish literal values from explanatory placeholders,
  including nullable fields; they must not teach an incorrect schema or reuse rule.
- Exit codes, pending review states and the harness acceptance gate are accurately separated.
  Readers can tell what a subsequent engine run reports after an external verdict is saved.
- Descriptions of plugin permissions, snapshot isolation, missing Git data and reviewer
  access do not promise protection or enforcement that the implementation does not provide.

Fail for a material contradiction, an example that implies an invalid public field type,
or an ambiguity that could cause incorrect acceptance or input selection. State the exact
claim and the correction needed. Stylistic preferences alone are not failures. If necessary
reference material is unavailable, return `blocked` and identify it instead of guessing.
