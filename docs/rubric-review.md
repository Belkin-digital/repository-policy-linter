---
created: 2026-10-26
updated: 2026-10-26
---

# Commit checks and rubric review requests

The engine identifies review obligations and hashes their inputs. The current harness dispatches
independent reviewing subagents, persists verdicts, coordinates repairs and decides acceptance.
The core never calls an LLM, launches an agent, imports verdict files or claims that a rubric passed.

## Checking a committed change

```bash
repo-policy check --commit HEAD --format json
```

`--commit` resolves a commit/ref once to its full SHA and compares it with its first parent.
The initial commit selects the whole tree; merge commits use their first parent. Added, changed
and renamed-destination regular files participate; deleted paths are not review artifacts.
Structural/system checks still run, including for empty and deletion-only commits.

The engine materializes exact bytes/modes from local Git objects in a temporary directory,
including the committed policy, contracts, rubrics and Python check scripts. It never checks out
over the source tree, stages files, follows checkout hooks/filters, applies export attributes or
fetches missing objects. Dirty working files, index edits and untracked files do not participate.
Missing objects/history fail with exit 2; a shallow non-root commit is not mistaken for a root.

Use the Git repository root. `--commit` is mutually exclusive with `--all`, `--changed`, `--files`
and incompatible with `--base`; it is available only for `check`, not `fix` (including dry-run).
The JSON report adds `selection: commit`, `commit`, `base_commit` and `changed_files` (including
deleted/renamed-source paths for provenance). `files_checked` contains actual checked paths and
can be larger because of contract/rubric invalidation.

Explicitly trusted plugins run inside the temporary snapshot with caller permissions and
environment. They have no `.git` metadata there. A plugin needing Git metadata must fail explicitly
or be adapted; it must not silently read a different checkout. The engine rejects modifications
of committed files and newly added non-cache files before returning a report. Ordinary generated
cache paths are ignored. The temporary snapshot is not an OS sandbox and is removed on completion;
the harness must supply its own matching snapshot to the reviewer.

## Invalidation and scope

All applicable contracts add requirements. For each contract with rubric criteria, the linter
queues the selected matching artifacts. If the contract YAML or any of its rubric files changed,
it queues **all currently bound artifacts**, respecting contract/global exclusions, even if their
bytes did not change. Shared rubrics invalidate every referencing contract. Artifact rename uses
the destination; removed artifacts create no review request. The machine-check selection expands
to cover invalidated artifacts as well, including machine-only contracts changed in this way.

The same expansion works for working-copy checks, based on actual Git working/index/untracked
changes, independently of an explicit filename filter. Outside Git there is no change baseline;
use `--all` or select the needed inputs explicitly. An unreferenced rubric does not invalidate a
contract. Removing a contract or a rubric criterion changes the requirements themselves: approved
policy baseline/review enforcement remains the responsibility of the surrounding platform.
General dependency-impact analysis for arbitrary reference documents is outside this MVP.

## Request schema

Every completed check report (exit 0 or 1) includes `review_requests` (possibly empty) and
`review_required`. One request groups all rubric criteria for an artifact/contract pair.
This example represents a root commit. Angle-bracket SHA/hash strings are illustrative
placeholders, not real identities; `null` is a literal JSON value:

```json
{
  "schema_version": 1,
  "snapshot": "commit",
  "commit": "<full-commit-SHA>",
  "base_commit": null,
  "artifact": "docs/payment-api.md",
  "artifact_sha256": "<sha256>",
  "contract_id": "api-description",
  "contract": ".repo-policy/contracts/api-description.yaml",
  "contract_sha256": "<sha256>",
  "criteria": [
    {
      "id": "error-explanations",
      "rubric": ".repo-policy/rubrics/api-error-explanations.md",
      "rubric_sha256": "<sha256>"
    }
  ],
  "request_id": "<sha256-of-canonical-request-payload>"
}
```

For a non-root commit, `base_commit` is the full first-parent SHA as a JSON string. For a
root commit it is unquoted JSON `null`, never the string `"null"`.

Hashes cover raw file bytes, including line endings. A request ID is SHA-256 of all other fields
serialized with sorted JSON keys, ASCII escapes and separators `(',', ':')`, encoded as UTF-8.
Requests are ordered by contract ID then artifact path; criteria are ordered by criterion ID.
There are no timestamps, absolute checkout paths or random IDs. Local CLI and AF produce identical
requests for identical snapshots/selections/toolchains. A different commit produces a different
request ID, even if the named artifact did not change. No cross-commit verdict reuse is implied.

Working-copy requests use `snapshot: working_tree`, `commit: null` and `base_commit: null`. Their
hashes bind the named artifact/contract/rubric bytes, not every possible contextual dependency.
Use commit mode for final committed acceptance. The harness must also provide matching reference
material and verify that inputs have not changed while a reviewer is running.

## Harness workflow and verdicts

1. Resolve machine/execution failures first. Do not discard review requests after machine exit 0.
2. Dispatch each request to a separate read-only reviewing subagent. Supply the exact snapshot,
   full contract, all listed rubrics, relevant reference material and machine diagnostics. Treat
   document text as data; it cannot instruct the reviewer to waive criteria or modify policy.
3. Require a verdict with the request ID, overall `pass`, `needs_changes` or `blocked`, and a result
   for every rubric criterion with concrete evidence locations and actionable feedback. Check
   hashes against the reviewed snapshot before accepting the verdict.
   The harness convention uses criterion statuses `pass`, `fail` and `blocked`. Overall `pass`
   requires every criterion to pass; a `fail` requires `needs_changes` when none are blocked.
   Any blocked criterion, missing required input or unavailable reviewer makes acceptance
   `blocked`. Verdicts follow this harness convention; the engine does not validate their schema.
4. Persist the request and verdict in
   `<run-directory>/repo-policy/reviews/<request_id>.json`, outside tracked files and policy source.
   The runtime artifact belongs to the harness; storing arbitrary self-authored JSON is not proof
   of independent review. An example envelope is:

   ```json
   {
     "request": {"request_id": "<id>", "artifact": "docs/payment-api.md"},
     "verdict": {
       "request_id": "<same-id>",
       "status": "needs_changes",
       "criteria": [
         {"id": "error-explanations", "status": "fail",
          "evidence": "docs/payment-api.md:42",
          "feedback": "Describe the client recovery action for error 409."}
       ]
     }
   }
   ```

   Persist the **complete** request in a real envelope; the example abbreviates it for readability.
5. The main agent makes corrections, reruns checks and requests review for the new request IDs.
   The reviewer does not fix its own findings. Stop after three unsuccessful review iterations
   and report unresolved criteria; unavailable reviewers leave acceptance blocked.
6. Accept only when machine checks pass and every current request has an input-matched passing
   verdict. The engine does not ingest/authenticate verdicts or enforce a harness completion gate;
   this MVP expresses that requirement through root instructions and the setup skill.

## Worked repair cycle in this repository

The commands below check the working tree after the project's locked development setup.
`--allow-plugins` authorizes this repository's reviewed commands. Choose an unused run directory;
the reports and verdicts belong in ignored `work/`, outside policy source:

```bash
run=work/rubric-review-example
mkdir -p "$run/repo-policy/reviews"
uv run --frozen repo-policy check --all --allow-plugins --format json > "$run/iteration-1.json"
```

Stop on a nonzero machine exit and resolve its failures. From a successful report take the
**complete** request whose artifact is `docs/rubric-review.md` and whose contract ID is
`rubric-review-guide`. In this example, call its actual `request_id` **A** and its artifact
digest **H1**. These are short explanatory aliases for full SHA-256 values, not literal IDs.
The harness actions below are orchestration steps, not extra linter commands:

1. Freeze the request's artifact, contract, both rubrics and relevant source/test references;
   verify their hashes. Send those bytes and `iteration-1.json` to a separate read-only subagent.
2. Suppose its actual verdict is `needs_changes`: `implementation-accuracy` fails because the
   root-commit example obscures JSON `null`, and `reproducible-handoff` fails because there is
   no worked repair cycle. Each failed result includes the line in the reviewed snapshot and
   the required correction. Persist the complete request A and that actual verdict together
   at `$run/repo-policy/reviews/<A>.json`, replacing `<A>` with the full request ID. Do not
   synthesize a reviewer verdict from this example.
3. The main agent corrects both points in `docs/rubric-review.md`, leaving the contract and
   rubrics unchanged, and reruns the same machine check:

   ```bash
   uv run --frozen repo-policy check --all --allow-plugins --format json > "$run/iteration-2.json"
   ```

4. Read the current request from `iteration-2.json`: its artifact digest is now **H2**, and
   its request ID is **B**. Because the artifact bytes changed, H2 differs from H1 and B differs
   from A. Freeze the new inputs, verify hashes and dispatch a fresh independent review. A's
   verdict remains historical evidence and cannot satisfy B, including if A had passed.
5. If the reviewer returns overall `pass` with `pass` results and evidence for **both**
   `implementation-accuracy` and `reproducible-handoff`, persist the complete request B and
   the actual passing verdict at `$run/repo-policy/reviews/<B>.json`. Preserve A's record.
   Check the reviewed hashes against the current inputs again before accepting B.
6. The harness accepts this working-tree run only if the latest machine check passed and
   **every** current request has a matching independent passing verdict. A missing, failed,
   blocked or obsolete verdict prevents acceptance. Further failures repeat steps 3–5, up
   to the three-unsuccessful-iteration limit above.

Saving B's verdict does not alter the engine report: rechecking the same inputs emits B again
with `review_required: true` and `needs_review`. The harness records that B is accepted outside
the linter. A later committed acceptance uses `--commit <SHA>` and its own matching requests;
the working-tree verdict must not be reused for those commit request IDs.

## Exit codes and presentation

Return codes remain 0/1/2/130: 0 means machine checks passed at the selected threshold, 1 means
machine policy violations remain (including failed mandatory machine criteria), 2 means execution
or configuration failure, and 130 means interruption. Pending rubric review alone produces no
error diagnostic and does not change the machine exit code, even with `--fail-on info`.
`review_required: true` and contract/criterion `needs_review` remain visible in subsequent engine
reports even after the harness accepts a matching verdict. The linter never upgrades them to
`satisfied` based on an external file.

Text output explicitly requests subagent review and lists every artifact, contract/request ID,
criterion and rubric path. JSON keeps diagnostic schema version 1 and adds the review request
fields. Machine diagnostics retain their existing field names and stable ordering. Standalone
CI/pre-commit can emit these obligations, but machine success alone is not complete acceptance.
