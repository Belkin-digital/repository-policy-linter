---
created: 2026-10-26
updated: 2026-10-26
---

# setup-skill

The [setup-skill contract](../contracts/setup-skill.yaml) binds native skill entrypoints to
the [skills registry](../checks/skills.yaml). `metadata` requires `name` and `description`;
`dates` requires `created` and `updated` inside `metadata`, preserving the native skill schema.

Read the [scope instructions](../../skills/AGENTS.md) before modifying the
[standalone setup skill](../../skills/repo-policy-setup/SKILL.md). The engine is distributed
separately; helper assets must work without a copy of its source. The repository's reviewed
[asset checker](../scripts/check_setup_assets.py) verifies starter-template parity as an
explicit external plugin, using the installed package rather than vendored engine code.
