---
created: 2026-10-26
updated: 2026-10-26
---

# Agent Factory: inspected integration and compatibility plan

Inspected on **2026-10-26**, from local AF-PM and backend source, not guessed from a generic
SKILL.md convention. This is an integration assessment, not a deployed-platform acceptance claim.
Both working trees have existing uncommitted documentation/code changes, so HEAD alone is not
the source snapshot; selected working-file hashes are in [af-source-evidence.json](af-source-evidence.json).

## Sources actually read

AF-PM root: `/Users/aleksejbelkin/Git/Agent Factory Workspace/AF-PM`;
HEAD `dcf8af48e06ee411be6b4312119e299c758eab04`.

- `AGENTS.md`, `README.md`, `REPOS.md`, `SSOT/agent-dev-conventions.md`,
  `plan/SoW/README.md` and `plan/SoW/SoW_AF_001_platform-concept.md`: PM/code boundary,
  configurable runtime wrapper, portable workfolders, identity, local/hosted/hybrid operation.
- `design/architecture/contracts/DES_AF_052_declarative-skills-integration-executor.md`,
  sections Decision, Domain contract, Minimal skill manifest and Runtime tool:
  immutable SkillVersion, `instructions_markdown`, protocol manifest, exact AgentVersion pin,
  workspace/personal Resource grants and Core Policy/Approval/Audit.
- `design/architecture/containers/AF-C02-runner/DES_AF_C02-M01_runtime-adapters.md`,
  runtime contract and Result manifest: workdir, adapter interfaces, Run outputs and artifact indexing.
- `design/architecture/containers/AF-C02-runner/DES_AF_C02-M02_workdir-context-repo-execution.md`:
  primary repo under `/session/work/repos/`, modes/access, target split context and current
  combined `context/bundle.json` implementation deviation.
- `design/architecture/containers/AF-C06-mcp-gateway/DES_AF_C06-M02_scm-gateway-git-proxy-gh.md`:
  inspected Git/SCM policy and pre-receive sections; an SCM push authorization hook is a
  different boundary from an asynchronous repository-policy status check.

Backend root: `/Users/aleksejbelkin/Git/Agent Factory Workspace/agent-factory-backend`;
HEAD `6e302aa43cfe88a1eb3ae26c352de46547fcbbe1`.

- `src/agent_factory_backend/schemas/skill.py`: actual `SkillProtocol` enum in this snapshot
  is **http/caldav/platform**; `SkillManifest` forbids unknown fields. The PM contract also
  describes MCP extensions, but this enum is narrower. No supported `shell`/`python` install
  protocol was found here; do not fabricate one.
- `src/agent_factory_backend/runner/execution/run_preparation.py`: `_skill_description()`
  builds operation/recipe descriptions and includes `instructions_markdown` (currently clipped
  to 4000 characters). Native Skill assignment is not equivalent to recursively mounting a
  filesystem skill folder with helper scripts/assets.

## Implemented adapter

`repo-policy-af` is a **Runner-side CLI bridge**. The engine is installed in the Runner image/tool
environment as a pinned dependency. The same `.repo-policy/` bundle, engine and plugin toolchain
stay in use. It checks the explicitly selected checkout and emits the same diagnostic JSON as
`repo-policy check`; tests assert report equality. It does not require an LLM subscription.

```bash
repo-policy-af --root /session/work/repos/selected \
  --session-root /session --output-dir /session/runs/RUN_ID/policy-output --all
```

Output directory must be new, inside the mounted session root and outside the repo. A host-mounted
session root can be specified explicitly; the bridge translates the output path to `/session/...`.
It writes `report.json` and `outputs.fragment.json`, returns the engine status, preserves symlink
boundaries and refuses existing output files. For configuration failures it still writes an error
report when a valid output directory is available.

The policy bundle includes explicitly registered check modules, artifact contracts, same-ID
explanations, navigation indexes and repository-specific Python scripts. Bundle pins must cover
these resources, not only the manifest. The same automatic system checks and additive contract
results run locally and through this bridge; rubric review remains external.

`repo-policy-af --commit <SHA>` uses the same immutable local-object snapshot and emits identical
hashed `review_requests` as the local CLI. The caller-owned harness dispatches reviewers and
persists verdicts in its run artifacts; the bridge performs no dispatch, grading or verdict import.
Machine success can coexist with `review_required: true`. See the
[review handoff](rubric-review.md) before treating a run as accepted.

The fragment follows the inspected output fields: `session_path`, `semantic_role: report`,
`content_type`, `checksum_sha256`, `publish: false`, and `schema_version: '1.0'`. It is **not** a
full runtime result manifest: the owning Runner supplies authoritative workspace/session/run ids,
overall status and its own output selection. No file is uploaded and no Core object is created.

## Rollout

1. Choose one authorized target repo and use the setup skill locally. Pin engine/plugins and
   policy; establish baseline. No mass installation.
2. Bake the same wheel and tool locks into an isolated AF execution environment. Mount the exact
   checkout and run the bridge in check-only mode. Missing tools/history fail explicitly.
3. Merge output metadata through the existing Runner result-indexing path after its policy check.
   Verify real source/runtime paths against the deployed version; do not assume target `/session`
   layout is already present everywhere.
4. Run push/PR observation while users still work in local Claude/Codex; compare results on identical
   content/SHA and policy pins. See [platform backlog](platform-backlog.md).
5. If platform-native tool invocation is needed later, expose a narrow deterministic check service
   through a **supported** protocol, using the deployed Core OpenAPI and lifecycle. It must take a
   permitted repo Resource + SHA + approved policy/tool pins, not an arbitrary host path, shell command
   or provider URL. Create/validate/publish/assign via Core only after explicit scope selection.

## Open integration gates / TODO

- Which deployed Runner image/revision and actual session path mapping should host the tool?
- Is there an existing generic deterministic validation job slot, or should Runner get one?
- Which immutable internal wheel/artifact registry and plugin lock format will be used?
- What exact deployed webhook intake, signature validation, GitHub App scopes and check-status API
  should be reused? Existing documentation is not proof of production readiness for these hooks.
- Which repositories/branches and trusted policy base are in the first observation cohort? Who may
  approve a policy/toolchain change and switch an observation check to required?
- How will Runner merge the fragment and store JSON diagnostics without unintended publication?
- Are native instruction-only skills supported by the deployed lifecycle? An empty HTTP operations
  list is not evidence that executable setup scripts will be distributed or invoked.
- If an HTTP/MCP tool is chosen, read the **live** OpenAPI/schema and use immutable SkillVersion,
  Resource grants, AgentVersion assignment and existing Policy/Approval/Audit. No guessed manifest,
  endpoint, Resource id or activation is included in this release.

Only the CLI bridge and local parity tests are implemented here. Webhook orchestration, GitHub
check publication, platform image changes and native AF registration remain platform backlog work.
