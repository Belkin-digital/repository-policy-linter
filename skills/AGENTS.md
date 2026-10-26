---
created: 2026-10-26
updated: 2026-10-26
repo_policy_contracts: [setup-skill]
---

# Skill acceptance

Before editing native skill entrypoints, read the
[setup-skill contract](../.repo-policy/contracts/setup-skill.yaml) and its
[explanation](../.repo-policy/readme/setup-skill.md), or run `repo-policy explain setup-skill`.
Keep required dates under skill `metadata`. Preserve the setup skill's independence from
engine source and test its helper in disposable repositories. This contract is discovered
from selectors even when a navigation pointer is missing.

Continue to the [setup skill](repo-policy-setup/SKILL.md).
