import fnmatch
import os
import subprocess
from pathlib import Path

from .config import relative
from .model import PolicyError

PRUNED = {".git", ".venv", "venv", "node_modules", "__pycache__", ".ruff_cache"}


def matches(path, patterns):
    """POSIX fnmatch; **/ also matches zero directory levels."""
    for pattern in patterns:
        if fnmatch.fnmatchcase(path, pattern):
            return True
        while pattern.startswith("**/"):
            pattern = pattern[3:]
            if fnmatch.fnmatchcase(path, pattern):
                return True
    return False


def safe_path(root, name):
    relative(name, "file")
    path = root / name
    current = root
    for part in Path(name).parts:
        current = current / part
        if current.is_symlink():
            raise PolicyError(f"symlink path is unsupported: {name}")
    if not path.resolve().is_relative_to(root):
        raise PolicyError(f"path outside repository: {name}")
    return path


def git(root, *args, optional=False):
    try:
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PolicyError("cannot execute Git") from exc
    if result.returncode:
        if optional:
            return None
        raise PolicyError("Git selection failed; check repository, history and base ref")
    return result.stdout


def is_git_root(root):
    out = git(root, "rev-parse", "--show-toplevel", optional=True)
    return out is not None and Path(os.fsdecode(out).strip()).resolve() == root


def _names(raw):
    return {os.fsdecode(name) for name in raw.split(b"\0") if name}


def select_files(root, config, mode="all", base=None, explicit=None):
    if explicit is not None:
        candidates = set(explicit)
        if mode != "commit":
            for name in candidates:
                safe_path(root, name)
    elif mode == "changed":
        if not is_git_root(root):
            raise PolicyError("--changed requires --root to be the Git repository root")
        if base:
            # Resolve user input separately: a ref can never become a Git option.
            resolved = git(root, "rev-parse", "--verify", "--end-of-options", base + "^{commit}")
            merge_base = git(root, "merge-base", "HEAD", resolved.decode().strip()).decode().strip()
            raw = git(root, "diff", "--name-only", "-z", "--diff-filter=ACMR", merge_base, "--")
        elif git(root, "rev-parse", "--verify", "HEAD", optional=True):
            raw = git(root, "diff", "--name-only", "-z", "--diff-filter=ACMR", "HEAD", "--")
        else:
            raw = git(root, "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR", "--")
            raw += git(root, "diff", "--name-only", "-z", "--diff-filter=ACMR", "--")
        candidates = _names(raw) | _names(
            git(root, "ls-files", "-z", "--others", "--exclude-standard")
        )
    elif is_git_root(root):
        candidates = _names(
            git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
        )
    else:
        candidates = set()
        for directory, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(
                d for d in dirs if d not in PRUNED and not (Path(directory) / d).is_symlink()
            )
            candidates.update((Path(directory) / f).relative_to(root).as_posix() for f in files)
    selected, skipped = [], []
    for name in sorted(candidates):
        if set(Path(name).parts) & PRUNED or matches(name, config.get("exclude", [])):
            continue
        try:
            path = safe_path(root, name)
        except PolicyError:
            skipped.append({"file": name, "reason": "symlink"})
            continue
        if path.is_file():
            selected.append(name)
    return selected, skipped
