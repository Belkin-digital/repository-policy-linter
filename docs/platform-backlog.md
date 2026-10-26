# Platform concept: repository policy as a portable control

Owner request, 2026-10-26: use the linter locally with Claude/Codex, retain all rules when moving
to Agent Factory, and allow AF to check local agents' repository updates by a hook before migration.
The same versioned `.repo-policy.yaml`, engine, exclusions, exceptions, plugin configuration and
tool locks are the shared policy artifact. Platform enforcement configuration may choose an approved
policy revision; it must not silently translate or fork the rules.

```text
local Claude / Codex → commit / push / PR
  → authenticated repository update event
  → AF authorized repo + exact head SHA + trusted policy/tool pins
  → isolated deterministic Runner check
  → JSON diagnostics + SHA-bound check/status
  → observe and compare → optional required gate → platform-hosted agents
```

The checker is independent of which agent authored the commit. It works for a human commit too;
attribution must come from real event/Run provenance rather than guessed from commit messages.
Observation lets teams test the platform control while the actual editor/agent remains local.

## Backlog (not implemented by this repository)

| Item | Deliverable | Acceptance |
| --- | --- | --- |
| PLAT-01 | Deterministic Runner policy job, no LLM needed | Uses same package/config; identical normalized report for same files/tool locks; all/changed selection and error codes preserved |
| PLAT-02 | Trusted push/PR event intake | Signature and delivery replay checks; repo Resource/tenant mapping, permission-limited principal; exact SHA cannot be substituted by branch movement |
| PLAT-03 | Immutable job identity and dedup | Key includes provider delivery id plus repo id, head/base SHA, policy digest, engine/toolchain digest and selection; retry idempotent; concurrent newer heads cannot receive stale success |
| PLAT-04 | Reviewed policy baseline | Gate uses protected approved policy/tool pins; candidate policy checked separately; removing/changing rules in PR cannot bypass gate; migration retains rule meaning |
| PLAT-05 | Untrusted checkout containment | Ephemeral read-only checkout, no credentials/network, pinned reviewed plugins only, resource/time/output limits; fork payload cannot run arbitrary commands in privileged Runner |
| PLAT-06 | SHA-bound reports and status | Diagnostics linked to repo/head SHA, engine/config/tool versions and hashes; minimal App permissions for checks/status; no content upload beyond configured authorized reports |
| PLAT-07 | Observation and parity harness | Nonblocking status; compare local/AF reports on same immutable snapshot; classify mismatches (dirty tree, policy/tool drift, Git history, file selection, environment); retain reproducible evidence |
| PLAT-08 | Explicit rollout and enforcement | Per-repo/branch enrollment; initial baseline; documented switch to required checks; failure vs execution error visible; rollback to observation without rule loss |
| PLAT-09 | Native platform tool (only if needed) | Live AF schema verified; supported protocol service with scoped repo/SHA inputs; Core lifecycle, resources, policy and audit; no arbitrary command or filesystem path inputs |

## Required tests before enforcement

- Same clean SHA + policy + toolchain + file selection: local CLI and AF job have identical ordered
  file/line/rule/severity/message outputs. Dirty local-tree reports are not treated as committed evidence.
- Duplicate delivery, retry after crash, out-of-order head updates, deleted/force-pushed branch and
  unavailable merge base: no false green, no stale required status.
- Untrusted fork changes policy, plugin argv/config or CI: it cannot disable its trusted gate, receive
  secrets or use plugin network access. Candidate-policy diagnostics remain distinguishable.
- Missing tool, invalid config, timeout or infrastructure failure is execution failure, not clean.
- Changed/all parity includes required-path deletions, renamed/untracked handling and shallow history.
- Publication failure/retry cannot change the check's SHA; same completed result is reused safely.
- Turning off enforcement changes status policy only; rules/config and local agent workflow stay intact.

Proposed mapping to AF: Channel/SCM event intake → Core authorization/scheduling → Runner deterministic
job → existing result/artifact indexing → GitHub App check publisher. Do not equate the current SCM
pre-receive authorization hook with this new content-validation workflow. Provider-specific wire/API
details, ownership and delivery milestones require platform implementation work.
