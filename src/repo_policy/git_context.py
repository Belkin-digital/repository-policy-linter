"""Opt-in, caller-owned Git comparison context for trusted repository plugins."""

import hashlib
import json
import os
import re
import stat
import tempfile
from contextlib import ExitStack, contextmanager
from pathlib import Path

from .history import first_parent
from .model import PolicyError
from .snapshot import commit_snapshot, git_read

INPUT_LIMIT = 1_048_576


def names(raw):
    return {os.fsdecode(n) for n in raw.split(b"\0") if n}


def commit_info(root, sha):
    if sha is None:
        return None
    raw = git_read(root, "cat-file", "commit", sha).split(b"\n\n", 1)[0]
    return {
        "sha": sha,
        "tree": next(
            line[5:].decode("ascii") for line in raw.splitlines() if line.startswith(b"tree ")
        ),
        "parents": [
            line[7:].decode("ascii") for line in raw.splitlines() if line.startswith(b"parent ")
        ],
    }


def entries(root, paths, versioned, gitlinks=None):
    result = {}
    for name in sorted(paths):
        path = root / name
        if any(p.is_symlink() for p in path.parents if p != root and root in p.parents):
            raise PolicyError("Git context cannot traverse a symlink directory")
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        item = {"versioned": name in versioned}
        if stat.S_ISLNK(info.st_mode):
            raw = os.fsencode(os.readlink(path))
            item.update(
                kind="symlink", mode="120000", size=len(raw), sha256=hashlib.sha256(raw).hexdigest()
            )
        elif stat.S_ISREG(info.st_mode):
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            item.update(
                kind="file",
                mode="100755" if info.st_mode & stat.S_IXUSR else "100644",
                size=info.st_size,
                sha256=digest,
            )
        elif stat.S_ISDIR(info.st_mode):
            oid = (gitlinks or {}).get(name)
            if oid is None:
                raise PolicyError("untracked embedded repository is not a Git tree entry")
            item.update(kind="gitlink", mode="160000", size=0, sha256=None, git_oid=oid)
        else:
            raise PolicyError("unsupported file type in Git context")
        result[name] = item
    return result


def working_entries(root):
    indexed, gitlinks = set(), {}
    for raw in git_read(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not raw:
            continue
        metadata, name = raw.split(b"\t", 1)
        mode, oid, stage = metadata.split()
        if stage != b"0":
            raise PolicyError("Git context requires a resolved index")
        name = os.fsdecode(name)
        indexed.add(name)
        if mode == b"160000":
            gitlinks[name] = oid.decode("ascii")
    if git_read(root, "ls-files", "--unmerged", "-z"):
        raise PolicyError("Git context requires a resolved index")
    others = names(git_read(root, "ls-files", "--others", "--exclude-standard", "-z"))
    head = git_read(root, "rev-parse", "--verify", "--quiet", "HEAD", missing_ok=True)
    old = (
        names(git_read(root, "ls-tree", "-rz", "--name-only", head.decode().strip()))
        if head
        else set()
    )
    # rm --cached must remain a versioned deletion, even if disk bytes remain.
    return entries(root, (indexed | others) - (old - indexed), indexed, gitlinks)


def tree_links(root, ref):
    result = {}
    for raw in git_read(root, "ls-tree", "-rz", ref).split(b"\0"):
        if raw:
            metadata, name = raw.split(b"\t", 1)
            mode, _, oid = metadata.split()
            if mode == b"160000":
                result[os.fsdecode(name)] = oid.decode("ascii")
    return result


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate context-input key")
        result[key] = value
    return result


def caller_input(filename, git_root):
    if filename is None:
        return None, None
    path = Path(filename).absolute()
    if path.resolve().is_relative_to(git_root) or any(
        p.is_symlink() for p in (path, *path.parents)
    ):
        raise PolicyError("context-input must be a regular caller file outside the repository")
    if not path.is_file() or path.stat().st_size > INPUT_LIMIT:
        raise PolicyError("context-input is missing or exceeds 1 MiB")
    with path.open("rb") as stream:
        raw = stream.read(INPUT_LIMIT + 1)
    if len(raw) > INPUT_LIMIT:
        raise PolicyError("context-input exceeds 1 MiB")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=strict_object)
        if (
            not isinstance(value, dict)
            or (
                type(value.get("context_input_version")) is not int
                or value["context_input_version"] != 1
            )
            or set(value) - {"context_input_version", "git_queries", "extensions"}
        ):
            raise ValueError("unsupported context-input schema")
        if not isinstance(value.get("extensions", {}), dict):
            raise ValueError("context-input extensions must be a mapping")
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise PolicyError("invalid context-input JSON/schema") from exc
    return path, {"sha256": hashlib.sha256(raw).hexdigest(), "data": value}


def query_facts(root, supplied):
    queries = supplied["data"].get("git_queries", []) if supplied else []
    if not isinstance(queries, list) or len(queries) > 64:
        raise PolicyError("context-input git_queries must be a list of at most 64 queries")
    facts = []
    for query in queries:
        if not isinstance(query, dict):
            raise PolicyError("invalid Git query")
        kind = query.get("kind")
        keys = {"kind", "commit"} if kind == "commit" else {"kind", "ancestor", "descendant"}
        if (
            kind not in ("commit", "ancestor")
            or set(query) != keys
            or any(
                not isinstance(query[k], str)
                or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", query[k])
                for k in keys - {"kind"}
            )
        ):
            raise PolicyError("Git queries require exact local commit SHA(s)")
        if kind == "commit":
            facts.append({**query, "object": commit_info(root, query["commit"])})
        else:
            ancestor, descendant = (commit_info(root, query[k]) for k in ("ancestor", "descendant"))
            direct = (
                ancestor["sha"] == descendant["sha"] or ancestor["sha"] in descendant["parents"]
            )
            if (
                not direct
                and git_read(root, "rev-parse", "--is-shallow-repository").strip() == b"true"
            ):
                raise PolicyError("ancestry query requires complete local history")
            answer = (
                direct
                or git_read(
                    root,
                    "merge-base",
                    "--is-ancestor",
                    ancestor["sha"],
                    descendant["sha"],
                    missing_ok=True,
                )
                is not None
            )
            facts.append({**query, "is_ancestor": answer})
    return facts


@contextmanager
def git_context(root, *, git_root=None, commit=None, parent=None, base=None, context_input=None):
    git_root = git_root or root
    top = git_read(git_root, "rev-parse", "--show-toplevel")
    if Path(os.fsdecode(top).strip()).resolve() != git_root:
        raise PolicyError("Git context requires the repository root")
    head_raw = git_read(git_root, "rev-parse", "--verify", "--quiet", "HEAD", missing_ok=True)
    head = head_raw.decode().strip() if head_raw else None
    input_path, supplied = caller_input(context_input, git_root)
    facts = query_facts(git_root, supplied)
    with ExitStack() as stack:
        head_snapshot = None
        if commit:
            baseline, comparison = parent, "first_parent" if parent else "initial"
            paths = names(git_read(git_root, "ls-tree", "-rz", "--name-only", commit))
            after = entries(root, paths, paths, tree_links(git_root, commit))
        else:
            after = working_entries(root)
            if head:
                head_snapshot = stack.enter_context(
                    commit_snapshot(git_root, head, include_changes=False)
                )
                head_entries = entries(
                    head_snapshot.root,
                    head_snapshot.expected,
                    head_snapshot.expected,
                    tree_links(git_root, head),
                )
                pending = head_entries != after
                baseline = head if pending else first_parent(git_root, head)
                comparison = "head" if pending else "first_parent" if baseline else "initial"
            else:
                baseline, comparison = None, "initial"
        if base:
            resolved = (
                git_read(git_root, "rev-parse", "--verify", "--end-of-options", base + "^{commit}")
                .decode()
                .strip()
            )
            baseline = git_read(git_root, "merge-base", "HEAD", resolved).decode().strip()
            comparison = "merge_base"
        previous = (
            head_snapshot
            if head_snapshot and baseline == head
            else stack.enter_context(commit_snapshot(git_root, baseline, include_changes=False))
            if baseline
            else None
        )
        before = (
            entries(
                previous.root, previous.expected, previous.expected, tree_links(git_root, baseline)
            )
            if previous
            else {}
        )
        changes = []
        for name in sorted(before.keys() | after.keys()):
            old, new = before.get(name), after.get(name)
            if old != new:
                status = "added" if old is None else "deleted" if new is None else "modified"
                changes.append({"path": name, "status": status, "before": old, "after": new})
        payload = {
            "context_version": 1,
            "kind": "git",
            "current_root": str(root),
            "baseline_root": str(previous.root) if previous else None,
            "comparison": comparison,
            "current_kind": "commit" if commit else "worktree",
            "current_commit": commit_info(git_root, commit or head),
            "baseline_commit": commit_info(git_root, baseline),
            "before": before,
            "after": after,
            "changes": changes,
            "input": supplied,
            "git_facts": facts,
        }
        directory = Path(
            stack.enter_context(tempfile.TemporaryDirectory(prefix="repo-policy-context-"))
        )
        path = directory / "context.json"
        raw = (json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n").encode()
        path.write_bytes(raw)
        path.chmod(0o400)
        summary = {
            "rule": "system-git-context",
            "kind": "git-context",
            "comparison": comparison,
            "base_commit": baseline,
            "current_commit": commit or head,
            "changed_paths": len(changes),
            "input_sha256": supplied["sha256"] if supplied else None,
            "git_queries": len(facts),
        }
        yield path, summary
        if path.is_symlink() or path.read_bytes() != raw:
            raise PolicyError("a checker changed the Git context")
        if previous:
            previous.verify()
        current = (
            entries(root, paths, paths, tree_links(git_root, commit))
            if commit
            else working_entries(root)
        )
        if current != after:
            raise PolicyError("a checker or concurrent edit changed the Git context inputs")
        if not commit:
            now = git_read(git_root, "rev-parse", "--verify", "--quiet", "HEAD", missing_ok=True)
            if now != head_raw:
                raise PolicyError("Git HEAD changed during checking")
        if input_path and (
            input_path.is_symlink()
            or hashlib.sha256(input_path.read_bytes()).hexdigest() != supplied["sha256"]
        ):
            raise PolicyError("caller context-input changed during checking")
