#!/usr/bin/env python3
"""Conservative, standalone scaffolding; engine stays an external dependency."""

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

START = "<!-- repo-policy:begin -->"
END = "<!-- repo-policy:end -->"
SECTION = """<!-- repo-policy:begin -->
## Repository policy

Install the exact tool dependency from `.repo-policy/requirements.txt` in an isolated
environment. Run `repo-policy check --all` before completion and `repo-policy check --changed`
while editing. [.repo-policy/policy.yaml](.repo-policy/policy.yaml) is the policy entrypoint.
Before editing artifacts, read `repo_policy_contracts` in the scope's README/AGENTS frontmatter.
Resolve ID to `.repo-policy/contracts/<id>.yaml` and optional `.repo-policy/readme/<id>.md`,
or run `repo-policy explain <id>`. Contract selectors remain authoritative.
For each new rule ask whether the linter can enforce it reasonably, reliably and simply.
If yes, implement it through the shared policy/engine with appropriate existing tools.
Always ask the user before implementing new rubric checks, changing their criteria or expanding
coverage/triggers; explain scope, frequency and review cost. Run existing rubric checks only within
their approved scope. Preserve known creation metadata; establish missing dates from evidence.
Installing the tool does not migrate all instructions or authorize rewriting historical artifacts.
Keep raw originals, native schemas and accepted results; inspect applicability before changing data.
Review configured external commands before passing `--allow-plugins`.
Exit 0 covers machine checks. Existing `review_requests` remain pending until their approved
harness review is complete; script-only setup does not create or authorize new rubric checks.
Use the installed setup skill's references/reviews.md for the complete approved handoff protocol.
<!-- repo-policy:end -->
"""
RUBRIC_HANDOFF = """
For a commit, run `repo-policy check --commit <SHA> --format json`. Exit 0 covers machine checks.
The current harness must dispatch every `review_requests` entry to a separate read-only subagent
with the matching snapshot, full contract and listed rubrics. Verify input hashes and save each
request/verdict at `<run-directory>/repo-policy/reviews/<request_id>.json`, outside tracked files.
Require per-criterion evidence and `pass`, `needs_changes` or `blocked`; the main agent fixes
issues, reruns checks and requests fresh reviews. Reuse no mismatched request IDs. After three
unsuccessful iterations, report remaining criteria; unavailable reviewers leave acceptance blocked.
Contract/rubric changes can require reviewing unchanged artifacts too. Acceptance requires both
machine success and current passing verdicts for every request; the linter never grades rubrics.
"""


class SetupError(ValueError):
    """An apply failure with an honest record of completed and uncertain writes."""

    def __init__(self, report):
        self.report = report
        super().__init__("scaffolding incomplete; inspect the write report before retrying")


def section(rubric_handoff=False):
    if rubric_handoff:
        return SECTION.replace(END, RUBRIC_HANDOFF + END)
    return SECTION


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def requirement(value):
    package = r"repository-policy-linter(?:\[markdown\])?"
    if re.fullmatch(package + r"==[0-9]+\.[0-9]+\.[0-9]+", value):
        return value
    match = re.fullmatch(package + r" @ (\S+)#sha256=([0-9a-f]{64})", value)
    if not match:
        raise ValueError("engine must be an exact version or a wheel URL with #sha256=...")
    url = urlsplit(match[1])
    if (
        url.scheme not in ("https", "file")
        or url.username
        or url.password
        or not url.path.endswith(".whl")
    ):
        raise ValueError("engine must use a credential-free https:// or file:// wheel URL")
    return value


def inside(root, name):
    path = root / name
    for current in [path, *path.parents]:
        if current == root:
            break
        if current.is_symlink():
            raise ValueError(f"refusing symlink: {name}")
    if not path.resolve().is_relative_to(root):
        raise ValueError("path escapes repository")
    return path


def preflight_write(path, original):
    if original is not None:
        if not path.is_file() or not os.access(path, os.W_OK):
            raise PermissionError("existing instruction file is not writable")
        return
    if path.exists():
        raise FileExistsError("planned new file already exists")
    parent = path.parent
    while not parent.exists():
        parent = parent.parent
    if not parent.is_dir() or not os.access(parent, os.W_OK | os.X_OK):
        raise PermissionError("parent directory is not writable")


def write_file(path, content, original):
    path.parent.mkdir(parents=True, exist_ok=True)
    if original is None:
        with path.open("xb") as stream:
            stream.write(content)
    else:
        # Append only. Preserve the original bytes/mode, and detect edits since planning.
        with path.open("r+b") as stream:
            if stream.read() != original:
                raise ValueError("instructions changed since planning")
            stream.write(content[len(original) :])


def configure(root, engine, apply=False, instructions=None, rubric_handoff=False):
    if rubric_handoff and not instructions:
        raise ValueError("--rubric-handoff requires --instructions")
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("target root does not exist")
    found = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    if Path(found.stdout.strip()).resolve() != root:
        raise ValueError("target must be a Git repository root")
    engine = requirement(engine)
    assets = Path(__file__).resolve().parents[1] / "assets/policy"
    proposed = {}
    manifest = inside(root, ".repo-policy/policy.yaml")
    if manifest.exists():
        # Adding an undeclared module to an existing bundle would break system validation.
        proposed[".repo-policy/policy.yaml"] = (assets / "policy.yaml").read_bytes()
    else:
        directory = inside(root, ".repo-policy")
        if directory.exists() and (not directory.is_dir() or any(directory.iterdir())):
            raise ValueError("existing policy directory has no manifest; reconcile manually")
        for asset in sorted(assets.rglob("*")):
            if asset.is_file():
                name = ".repo-policy/" + asset.relative_to(assets).as_posix()
                proposed[name] = asset.read_bytes()
    proposed[".repo-policy/requirements.txt"] = (engine + "\n").encode("utf-8")
    actions, writes = [], []
    for name, content in proposed.items():
        path = inside(root, name)
        if path.exists():
            existing = path.read_bytes()
            actions.append(
                {
                    "file": name,
                    "action": "preserve",
                    "matches": existing == content,
                    "current_sha256": digest(existing),
                    "requested_sha256": digest(content),
                }
            )
        else:
            actions.append({"file": name, "action": "create", "requested_sha256": digest(content)})
            writes.append((name, content, None))
    if instructions:
        path = inside(root, instructions)
        original = path.read_bytes() if path.exists() else None
        existing = original or b""
        try:
            existing.decode("utf-8")
        except UnicodeError as exc:
            raise ValueError("instruction file must be UTF-8; no files written") from exc
        first_lf = existing.find(b"\n")
        newline = b"\r\n" if first_lf > 0 and existing[first_lf - 1] == 13 else b"\n"
        content = section(rubric_handoff).encode("utf-8").replace(b"\n", newline)
        start, end = START.encode(), END.encode()
        if start in existing or end in existing:
            if (
                existing.count(start) != 1
                or existing.count(end) != 1
                or existing.index(start) > existing.index(end)
            ):
                raise ValueError("invalid managed instruction markers; reconcile manually")
            current = existing[existing.index(start) : existing.index(end) + len(end)]
            requested = content.rstrip(b"\r\n")
            actions.append(
                {
                    "file": instructions,
                    "action": "preserve",
                    "matches": current == requested,
                    "current_sha256": digest(current),
                    "requested_sha256": digest(requested),
                }
            )
        else:
            separator = b""
            if existing and not existing.endswith(newline * 2):
                separator = newline if existing.endswith(newline) else newline * 2
            content = existing + separator + content
            writes.append((instructions, content, original))
            actions.append(
                {"file": instructions, "action": "append", "requested_sha256": digest(content)}
            )
    blocked = []
    for name, _, original in writes:
        try:
            preflight_write(inside(root, name), original)
        except (OSError, ValueError) as exc:
            blocked.append({"file": name, "reason": type(exc).__name__})
    report = {
        "applied": False,
        "actions": actions,
        "engine": engine,
        "portable_source": "file://" not in engine,
        "source_kind": (
            "local_wheel"
            if "file://" in engine
            else "https_wheel"
            if " @ " in engine
            else "registry"
        ),
        "verification": {
            "availability": "not_verified",
            "cold_install": "not_run",
            "ci": "not_run",
        },
        "verification_note": "Requirement syntax only; no download, install or CI run is performed.",
        "reconciliation_required": [a["file"] for a in actions if a.get("matches") is False],
        "rubric_handoff": rubric_handoff,
        "write_preflight": {
            "status": "blocked" if blocked else "passed",
            "scope": "filesystem_access_only; not a transaction or tool-permission guarantee",
            "blocked": blocked,
        },
        "planned_writes": [name for name, _, _ in writes],
        "completed_writes": [],
    }
    if apply:
        if blocked:
            report["error"] = "write preflight failed; no files written"
            report["remaining_writes"] = report["planned_writes"]
            raise SetupError(report)
        for i, (name, content, original) in enumerate(writes):
            try:
                write_file(inside(root, name), content, original)
            except (OSError, ValueError) as exc:
                report["error"] = "write failed; inspect the affected file before retrying"
                report["uncertain_write"] = name
                report["error_type"] = type(exc).__name__
                report["remaining_writes"] = [name for name, _, _ in writes[i:]]
                raise SetupError(report) from exc
            report["completed_writes"].append(name)
        report["applied"] = True
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--engine", required=True)
    parser.add_argument("--instructions", choices=["AGENTS.md", "CLAUDE.md"])
    parser.add_argument(
        "--rubric-handoff",
        action="store_true",
        help="include full harness instructions for already-approved rubric contracts",
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                configure(
                    args.root, args.engine, args.apply, args.instructions, args.rubric_handoff
                ),
                indent=2,
            )
        )
    except SetupError as exc:
        print(json.dumps(exc.report, indent=2))
        parser.exit(2, f"setup failed: {exc}\n")
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"setup failed: {exc}\n")


if __name__ == "__main__":
    main()
