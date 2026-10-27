"""Repository-wide version gates using only local Git objects and bounded source bytes."""

import os
import re
from itertools import islice
from pathlib import Path

from .files import safe_path
from .model import PolicyError
from .rules import diagnostic
from .snapshot import git_read

SEMVER = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)


def semver(value):
    if not isinstance(value, str) or not (match := SEMVER.fullmatch(value)):
        raise ValueError("expected SemVer MAJOR.MINOR.PATCH with optional prerelease/build")
    major, minor, patch, prerelease = match.groups()
    identifiers = []
    for part in prerelease.split(".") if prerelease else []:
        numeric = part.isascii() and part.isdigit()
        if numeric and len(part) > 1 and part.startswith("0"):
            raise ValueError("numeric prerelease identifiers must not have leading zeros")
        identifiers.append((0, int(part)) if numeric else (1, part))
    return int(major), int(minor), int(patch), not prerelease, tuple(identifiers)


def extract_version(rule, raw):
    text = raw.decode("utf-8")
    if "\0" in text:
        raise ValueError("version source must be UTF-8 without NUL")
    matches = list(islice(re.finditer(rule["pattern"], text, re.MULTILINE), 2))
    if len(matches) != 1:
        raise ValueError("version pattern must match exactly once")
    value = matches[0].group("version")
    return value, semver(value)


def first_parent(root, commit):
    header = git_read(root, "cat-file", "commit", commit).split(b"\n\n", 1)[0]
    return next(
        (line[7:].decode("ascii") for line in header.splitlines() if line.startswith(b"parent ")),
        None,
    )


def version_baseline(root, commit, parent):
    """Untracked-only files are not a pending commit; staged additions are tracked changes."""
    top = git_read(root, "rev-parse", "--show-toplevel")
    if Path(os.fsdecode(top).strip()).resolve() != root:
        raise PolicyError("version-increment requires the Git repository root")
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
        raise PolicyError("version baseline requires a regular Git file")
    if int(git_read(root, "cat-file", "-s", oid.decode("ascii"))) > limit:
        raise PolicyError("version baseline exceeds max_file_bytes")
    return git_read(root, "cat-file", "blob", oid.decode("ascii"))


def check_version(root, git_root, rule, baseline, limit):
    base_commit, source = baseline
    summary = {
        "rule": rule["id"],
        "kind": "version-increment",
        "path": rule["path"],
        "baseline": source,
        "base_commit": base_commit,
        "previous_version": None,
        "current_version": None,
    }
    try:
        with safe_path(root, rule["path"]).open("rb") as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError("version source exceeds max_file_bytes")
        current, value = extract_version(rule, raw)
    except (OSError, UnicodeError, ValueError, PolicyError):
        return [diagnostic(rule, rule["path"], "missing or invalid bounded SemVer source")], summary
    summary["current_version"] = current
    raw = previous_source(git_root, base_commit, rule["path"], limit)
    if raw is None:
        return [], summary
    try:
        previous, old_value = extract_version(rule, raw)
    except (UnicodeError, ValueError) as exc:
        raise PolicyError(f"{rule['id']}: cannot parse the version baseline") from exc
    summary["previous_version"] = previous
    if value <= old_value:
        return [
            diagnostic(
                rule,
                rule["path"],
                f"version must increase: {current} is not greater than {previous}",
            )
        ], summary
    return [], summary
