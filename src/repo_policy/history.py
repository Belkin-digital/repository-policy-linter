"""Local Git baselines and preservation of existing frontmatter values."""

import os
from pathlib import Path

import yaml

from .config import yaml_load
from .files import safe_path
from .model import PolicyError
from .rules import diagnostic
from .snapshot import git_read


def first_parent(root, commit):
    header = git_read(root, "cat-file", "commit", commit).split(b"\n\n", 1)[0]
    return next(
        (line[7:].decode("ascii") for line in header.splitlines() if line.startswith(b"parent ")),
        None,
    )


def git_baseline(root, commit, parent):
    """Untracked-only files are not a pending commit; staged additions are tracked changes."""
    top = git_read(root, "rev-parse", "--show-toplevel")
    if Path(os.fsdecode(top).strip()).resolve() != root:
        raise PolicyError("history checks require the Git repository root")
    if commit:
        return parent, "first_parent" if parent else "initial"
    head = git_read(root, "rev-parse", "--verify", "--quiet", "HEAD", missing_ok=True)
    if head is None:
        return None, "initial"
    head = head.decode("ascii").strip()
    parent = first_parent(root, head)  # A dangling HEAD must never become an initial commit.
    changes = git_read(
        root, "diff", "--name-only", "--no-ext-diff", "--no-textconv", "-z", head, "--"
    )
    return (head, "head") if changes else (parent, "first_parent" if parent else "initial")


def previous_source(root, commit, name, limit):
    if commit is None:
        return None
    entry = git_read(root, "--literal-pathspecs", "ls-tree", "-z", commit, "--", name)
    if not entry:
        return None  # First introduction of this version source.
    metadata, found = entry.rstrip(b"\0").split(b"\t", 1)
    mode, kind, oid = metadata.split()
    if (
        found.decode("utf-8", errors="surrogateescape") != name
        or mode not in (b"100644", b"100755")
        or kind != b"blob"
    ):
        raise PolicyError("baseline requires a regular Git file")
    if int(git_read(root, "cat-file", "-s", oid.decode("ascii"))) > limit:
        raise PolicyError("baseline exceeds max_file_bytes")
    return git_read(root, "cat-file", "blob", oid.decode("ascii"))


def frontmatter_values(raw, mapping_path):
    text = raw.decode("utf-8")
    if "\0" in text:
        raise ValueError("frontmatter source contains NUL")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError("unterminated frontmatter")
    data = yaml_load("".join(lines[1:end]))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a mapping")
    for key in mapping_path:
        if key not in data:
            return {}
        data = data[key]
        if not isinstance(data, dict):
            raise ValueError("frontmatter path must select a mapping")
    return data


def check_preserved_frontmatter(root, git_root, rule, name, base_commit, limit):
    # Current syntax/required keys have already passed the ordinary frontmatter rule.
    try:
        with safe_path(root, name).open("rb") as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError("frontmatter exceeds max_file_bytes")
        current = frontmatter_values(raw, rule.get("mapping_path", []))
    except (OSError, UnicodeError, ValueError, RecursionError, yaml.YAMLError) as exc:
        raise PolicyError(f"{name}: cannot read current frontmatter for preservation") from exc
    raw = previous_source(git_root, base_commit, name, limit)
    if raw is None:
        return []
    try:
        previous = frontmatter_values(raw, rule.get("mapping_path", []))
    except (UnicodeError, ValueError, RecursionError, yaml.YAMLError) as exc:
        raise PolicyError(f"{name}: cannot parse frontmatter baseline") from exc
    return [
        diagnostic(rule, name, f"frontmatter key must retain its previous value: {key}")
        for key in rule["preserve_keys"]
        if key in previous
        and (
            key not in current
            or type(current[key]) is not type(previous[key])
            or current[key] != previous[key]
        )
    ]
