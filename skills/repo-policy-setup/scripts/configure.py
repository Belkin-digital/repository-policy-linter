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

Install the exact tool dependency from `.repo-policy-requirements.txt` in an isolated
environment. Run `repo-policy check --all` before completion and `repo-policy check --changed`
while editing. `.repo-policy.yaml` is the policy source for local agents and platform runners.
Review configured external commands before passing `--allow-plugins`.
<!-- repo-policy:end -->
"""


def requirement(value):
    if re.fullmatch(r"repository-policy-linter==[0-9]+\.[0-9]+\.[0-9]+", value):
        return value
    match = re.fullmatch(r"repository-policy-linter @ (\S+)#sha256=([0-9a-f]{64})", value)
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
    asset = Path(__file__).resolve().parents[1] / "assets/repo-policy.yaml"
    proposed = {
        ".repo-policy.yaml": asset.read_text(),
        ".repo-policy-requirements.txt": engine + "\n",
    }
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
