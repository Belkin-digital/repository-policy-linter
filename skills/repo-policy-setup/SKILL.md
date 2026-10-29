---
name: repo-policy-setup
description: Install or update Repository Policy Linter in a chosen repository, or migrate its approved instructions into machine checks with controlled adoption of existing artifacts. Use for policy setup, rule migration and local/CI/AF integration; ordinary editing under an existing policy does not require this skill.
metadata:
  created: '2026-10-26'
  updated: '2026-10-29'
---

# Repository Policy Linter setup and instruction migration

Work in the repository selected by the user. Infer the requested outcome from the task and
existing decisions; do not require another approval for work already authorized:

- **Install/update:** resolve an external engine, configure the selected policy and integrate
  its runtime and commands. A complete instruction audit or document rewrite is additional work.
- **Migrate rules:** also inventory normative sources and artifact roles, implement the provable
  checks, adopt existing data deliberately and report every uncovered requirement.
- **Continue an installation:** reuse its current receipts and accepted decisions; inspect the
  changed scope instead of restarting the entire migration.

Engine installation, rule coverage, conformity of the artifact collection, instruction delivery,
CI success and rubric acceptance are separate results. A green starter policy proves only its
enabled checks. This skill is self-contained; the upstream root AGENTS is not a prerequisite.

## Read by stage

1. [Discovery and rule design](references/rule-design.md): establish scope, dirty-state baseline,
   artifact classes, normative sources, required inputs and engine capabilities. Installation-only
   needs the relevant setup conventions, not a full coverage catalog.
2. [Runtime and integration](references/integration.md): resolve a real distribution, preview
   [configure.py](scripts/configure.py), install the external dependency and merge integrations.
   Use [contracts](references/contracts.md) for actual schema, selectors and ID navigation.
3. [Acceptance and handoff](references/acceptance.md): select meaningful verification, preserve
   real exit codes, separate unresolved queues and leave one current receipt.

Read conditional guidance before the corresponding work:

- [Data preservation and adoption](references/data-preservation.md) before generator writes,
  historical backfill, baseline changes or edits to originals and published results.
- [Instruction migration and navigation](references/instruction-migration.md) when moving a
  canonical source, syncing mirrors or changing document reachability.
- [Language policies](references/language-policy.md) for lexical checks or editorial migration.
- [Rule library](references/rule-library.md) for optional candidates and tested examples.
  Select rules from the project's own conventions; examples are never enabled automatically.
- [Rubric handoff](references/reviews.md) only for already-approved review obligations or an
  explicitly authorized rubric stage. The helper's `--rubric-handoff` delivers full instructions
  for that stage; the flag does not authorize criteria, reviewers or new automatic triggers.

## Boundaries

For every new rule ask whether the linter can enforce it reasonably, reliably and simply.
Prefer built-ins, existing specialist tools and small repository adapters. State the narrow fact
proved and its limits; a word, hash, status or self-written `approved` field is not evidence of
meaning, ownership, permission or completed work. Keep process obligations in maintained
instructions when no reliable check exists.

Preserve unrelated edits, bytes, modes, symlinks, native schemas, historical results and local
configuration. Check-mode does not generate, fix, stage, refresh baselines or synchronize copies.
Inspect a diagnostic's applicability before changing dates, types, audience, facts or verdicts.
Use accepted decisions for the same proposed delta; ask only about a genuinely new decision.

Always obtain user approval before new rubric checks, changed criteria or expanded coverage,
triggers or recurring cost. Explain the scope, frequency and expected cost, or say it is unmeasured.
Uncovered semantic requirements do not automatically become rubric checks. Existing requests
remain pending until their approved harness workflow completes; machine exit 0 is insufficient.

Keep the engine an external dependency; never copy `src/repo_policy` into the target. A skill
update does not itself authorize an engine upgrade, another repository's publication, platform
objects or a new blocking gate. Respect explicit constraints on tests, network, writes and review.
Prepare a concrete diff/destination before asking for missing authority; continue independent work.

## Distribution and compatibility

Official [source](https://github.com/Belkin-digital/repository-policy-linter),
[skill folder](https://github.com/Belkin-digital/repository-policy-linter/tree/main/skills/repo-policy-setup)
and [PyPI project](https://pypi.org/project/repository-policy-linter/) identify this project.
Record engine version, source commit and available distribution separately. Verify a selected
version and its source URLs; a source version or link to `main` does not establish publication.

Use the selected distribution's documentation and CLI. Do not configure a capability from a
draft branch as if it were released. A `file://` wheel is a local pilot; a reproducible cold path
must obtain the declared distribution without the installer's existing clone or editable package.
The helper validates requirement syntax and scaffolds files; it performs no download, install,
hook registration, commit, push, CI or review. Reconcile every reported mismatch explicitly.
