"""Deterministic handoff requests; grading and verdict persistence belong to the harness."""

import hashlib
import json
import os

from .files import git, is_git_root, safe_path
from .policy import contract_matches
from .snapshot import file_hash


def working_changes(root, base=None):
    if not is_git_root(root):
        return set()
    if base:
        ref = git(root, "rev-parse", "--verify", "--end-of-options", base + "^{commit}")
        baseline = git(root, "merge-base", "HEAD", ref.decode().strip()).decode().strip()
    else:
        baseline = "HEAD" if git(root, "rev-parse", "--verify", "HEAD", optional=True) else None
    if baseline:
        raw = git(
            root,
            "diff",
            "--name-only",
            "--no-renames",
            "--no-ext-diff",
            "--no-textconv",
            "-z",
            baseline,
            "--",
        )
    else:
        raw = git(root, "ls-files", "-z", "--cached")
    raw += git(root, "ls-files", "-z", "--others", "--exclude-standard")
    return {os.fsdecode(n) for n in raw.split(b"\0") if n}


def review_scope(policy, names, all_names, changed):
    selected, targets, expanded = set(names), {}, set(names)
    for cid, contract in sorted(policy.contracts.items()):
        contract_path = f"{policy.directory}/contracts/{cid}.yaml"
        rubric_changed = any(
            c.get("rubric") in changed for c in contract["criteria"] if "rubric" in c
        )
        invalidated = contract_path in changed or rubric_changed
        applicable = {n for n in set(all_names) | selected if contract_matches(contract, n)}
        if invalidated:
            expanded.update(applicable)
        if any("rubric" in c for c in contract["criteria"]):
            targets[cid] = sorted(applicable if invalidated else applicable & selected)
    return sorted(expanded), targets


def review_requests(root, policy, targets, *, commit=None, parent=None):
    requests, hashes = [], {}

    def digest(name):
        if name not in hashes:
            hashes[name] = file_hash(safe_path(root, name))
        return hashes[name]

    for cid, artifacts in sorted(targets.items()):
        contract = policy.contracts[cid]
        contract_path = f"{policy.directory}/contracts/{cid}.yaml"
        criteria = [
            {"id": c["id"], "rubric": c["rubric"], "rubric_sha256": digest(c["rubric"])}
            for c in sorted(contract["criteria"], key=lambda c: c["id"])
            if "rubric" in c
        ]
        for artifact in artifacts:
            request = {
                "schema_version": 1,
                "snapshot": "commit" if commit else "working_tree",
                "commit": commit,
                "base_commit": parent,
                "artifact": artifact,
                "artifact_sha256": digest(artifact),
                "contract_id": cid,
                "contract": contract_path,
                "contract_sha256": digest(contract_path),
                "criteria": criteria,
            }
            content = json.dumps(request, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
            request["request_id"] = hashlib.sha256(content.encode()).hexdigest()
            requests.append(request)
    return requests
