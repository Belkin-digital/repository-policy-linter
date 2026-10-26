#!/usr/bin/env python3
"""Conservative, standalone scaffolding; engine stays an external dependency."""

import argparse
import json
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
Review configured external commands before passing `--allow-plugins`.
For a commit, run `repo-policy check --commit <SHA> --format json`. Exit 0 covers machine checks.
The current harness must dispatch every `review_requests` entry to a separate read-only subagent
with the matching snapshot, full contract and listed rubrics. Verify input hashes and save each
request/verdict at `<run-directory>/repo-policy/reviews/<request_id>.json`, outside tracked files.
Require per-criterion evidence and `pass`, `needs_changes` or `blocked`; the main agent fixes
issues, reruns checks and requests fresh reviews. Reuse no mismatched request IDs. After three
unsuccessful iterations, report remaining criteria; unavailable reviewers leave acceptance blocked.
Contract/rubric changes can require reviewing unchanged artifacts too. Acceptance requires both
machine success and current passing verdicts for every request; the linter never grades rubrics.
<!-- repo-policy:end -->
"""


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


def configure(root, engine, apply=False, instructions=None):
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
        proposed[".repo-policy/policy.yaml"] = (assets / "policy.yaml").read_text()
    else:
        directory = inside(root, ".repo-policy")
        if directory.exists() and (not directory.is_dir() or any(directory.iterdir())):
            raise ValueError("existing policy directory has no manifest; reconcile manually")
        for asset in sorted(assets.rglob("*")):
            if asset.is_file():
                name = ".repo-policy/" + asset.relative_to(assets).as_posix()
                proposed[name] = asset.read_text()
    proposed[".repo-policy/requirements.txt"] = engine + "\n"
    actions, writes = [], []
    for name, content in proposed.items():
        path = inside(root, name)
        if path.exists():
            actions.append(
                {"file": name, "action": "preserve", "matches": path.read_text() == content}
            )
        else:
            actions.append({"file": name, "action": "create"})
            writes.append((path, content, True))
    if instructions:
        path = inside(root, instructions)
        existing = path.read_text() if path.exists() else ""
        if START in existing or END in existing:
            if (
                existing.count(START) != 1
                or existing.count(END) != 1
                or existing.index(START) > existing.index(END)
            ):
                raise ValueError("invalid managed instruction markers; reconcile manually")
            actions.append({"file": instructions, "action": "preserve"})
        else:
            writes.append((path, existing.rstrip("\n") + "\n\n" + SECTION, not path.exists()))
            actions.append({"file": instructions, "action": "append"})
    if apply:
        for path, content, create in writes:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x" if create else "w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
    return {
        "applied": apply,
        "actions": actions,
        "engine": engine,
        "portable_source": "file://" not in engine,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--engine", required=True)
    parser.add_argument("--instructions", choices=["AGENTS.md", "CLAUDE.md"])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        print(
            json.dumps(configure(args.root, args.engine, args.apply, args.instructions), indent=2)
        )
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"setup failed: {exc}\n")


if __name__ == "__main__":
    main()
