"""Materialize an immutable commit from local Git objects without checkout hooks or filters."""

import hashlib
import os
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .files import PRUNED, safe_path
from .model import PolicyError


def git_read(root, *args, input=None, stdout=subprocess.PIPE):
    env = dict(os.environ)
    for name in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_COMMON_DIR",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_NAMESPACE",
    ):
        env.pop(name, None)
    env.update(
        GIT_NO_LAZY_FETCH="1",
        GIT_NO_REPLACE_OBJECTS="1",
        GIT_TERMINAL_PROMPT="0",
        GIT_OPTIONAL_LOCKS="0",
    )
    command = ["git", "-C", str(root), "-c", "protocol.allow=never"]
    for protocol in ("http", "https", "ssh", "git", "file", "ext"):
        command.extend(["-c", f"protocol.{protocol}.allow=never"])
    try:
        result = subprocess.run(
            command + list(args),
            input=input,
            stdout=stdout,
            stderr=subprocess.PIPE,
            env=env,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PolicyError("cannot read local Git commit objects") from exc
    if result.returncode:
        raise PolicyError("cannot read commit or history; required Git objects must be local")
    return result.stdout


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@dataclass
class Snapshot:
    root: Path
    commit: str
    parent: str | None
    changed: set
    expected: dict

    def verify(self):
        for name, (mode, value) in self.expected.items():
            path = self.root / name
            if mode == b"120000":
                valid = path.is_symlink() and os.fsencode(os.readlink(path)) == value
            elif mode == b"160000":
                valid = path.is_dir() and not path.is_symlink()
            else:
                valid = not path.is_symlink() and path.is_file() and file_hash(path) == value
                if os.name == "posix" and valid:
                    valid = bool(path.stat().st_mode & stat.S_IXUSR) == (mode == b"100755")
            if not valid:
                raise PolicyError("a checker changed the committed snapshot")
        for directory, dirs, files in os.walk(self.root, followlinks=False):
            dirs[:] = [d for d in dirs if d not in PRUNED]
            for name in files + [d for d in dirs if (Path(directory) / d).is_symlink()]:
                relative = (Path(directory) / name).relative_to(self.root).as_posix()
                if relative not in self.expected:
                    raise PolicyError("a checker added files to the committed snapshot")


@contextmanager
def commit_snapshot(root, ref):
    if not isinstance(ref, str) or not ref:
        raise PolicyError("--commit requires a commit or ref")
    top = git_read(root, "rev-parse", "--show-toplevel")
    if Path(os.fsdecode(top).strip()).resolve() != root:
        raise PolicyError("--commit requires the Git repository root")
    sha = (
        git_read(root, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}")
        .decode()
        .strip()
    )
    # Read the commit object itself: shallow history must not turn a non-root into a root.
    header = git_read(root, "cat-file", "commit", sha).split(b"\n\n", 1)[0]
    parents = [
        line[7:].decode("ascii") for line in header.splitlines() if line.startswith(b"parent ")
    ]
    parent = parents[0] if parents else None
    tree = git_read(root, "ls-tree", "-rz", "--full-tree", sha)
    entries = []
    for raw in tree.split(b"\0"):
        if raw:
            metadata, name = raw.split(b"\t", 1)
            mode, kind, oid = metadata.split()
            entries.append((mode, kind, oid, os.fsdecode(name)))
    if parent:
        changed = git_read(
            root,
            "diff-tree",
            "--no-commit-id",
            "-r",
            "--name-only",
            "-z",
            "--no-renames",
            "--no-ext-diff",
            "--no-textconv",
            parent,
            sha,
            "--",
        )
        changed = {os.fsdecode(n) for n in changed.split(b"\0") if n}
    else:
        changed = {name for _, _, _, name in entries}
    with tempfile.TemporaryDirectory(prefix="repo-policy-commit-") as temporary:
        snapshot_root = Path(temporary).resolve()
        expected = {}
        blobs = [entry for entry in entries if entry[0] != b"160000"]
        with tempfile.TemporaryFile() as stream:
            git_read(
                root,
                "cat-file",
                "--batch",
                input=b"".join(e[2] + b"\n" for e in blobs),
                stdout=stream,
            )
            stream.seek(0)
            for mode, kind, oid, name in entries:
                if any(part.lower() == ".git" for part in Path(name).parts):
                    raise PolicyError("commit contains a reserved .git path")
                path = safe_path(snapshot_root, name)
                path.parent.mkdir(parents=True, exist_ok=True)
                if mode == b"160000":
                    path.mkdir()
                    expected[name] = (mode, None)
                    continue
                if mode not in {b"100644", b"100755", b"120000"} or kind != b"blob":
                    raise PolicyError("unsupported Git tree entry")
                response = stream.readline(256).split()
                if (
                    len(response) != 3
                    or response[0] != oid
                    or response[1] != b"blob"
                    or not response[2].isdigit()
                ):
                    raise PolicyError("required Git blob is unavailable locally")
                remaining = int(response[2])
                digest = hashlib.sha256()
                if mode == b"120000":
                    if remaining > 16384:
                        raise PolicyError("Git symlink target exceeds filesystem limits")
                    target = stream.read(remaining)
                    path.symlink_to(os.fsdecode(target))
                    expected[name] = (mode, target)
                else:
                    with path.open("xb") as output:
                        while remaining:
                            chunk = stream.read(min(remaining, 1024 * 1024))
                            if not chunk:
                                raise PolicyError("incomplete Git blob")
                            output.write(chunk)
                            digest.update(chunk)
                            remaining -= len(chunk)
                    path.chmod(0o755 if mode == b"100755" else 0o644)
                    expected[name] = (mode, digest.hexdigest())
                if stream.read(1) != b"\n":
                    raise PolicyError("invalid Git blob delimiter")
        snapshot = Snapshot(snapshot_root, sha, parent, changed, expected)
        yield snapshot
