from pathlib import Path

from . import __version__
from .config import CONFIG_NAME, LIMIT
from .files import matches, safe_path, select_files
from .markdown_graph import check_reachability
from .model import PolicyError
from .plugins import run_plugin
from .policy import contract_results, load_policy, navigation_diagnostics
from .reviews import review_requests, review_scope, working_changes
from .rules import append_newline, applies, check_text, diagnostic
from .snapshot import commit_snapshot


def run(
    root,
    *,
    config_name=CONFIG_NAME,
    mode="all",
    base=None,
    files=None,
    fix=False,
    allow_plugins=False,
    fail_on="error",
    commit=None,
):
    root = Path(root).resolve()
    if not root.is_dir():
        raise PolicyError("repository root is not a directory")
    if mode not in {"all", "changed"}:
        raise PolicyError("unknown file selection mode")
    if base and mode != "changed":
        raise PolicyError("--base requires --changed")
    if commit is not None:
        if mode != "all" or files is not None or base or fix:
            raise PolicyError(
                "--commit is check-only and cannot be combined with another selection"
            )
        with commit_snapshot(root, commit) as snapshot:
            report = _run(
                snapshot.root,
                config_name=config_name,
                mode="commit",
                files=sorted(snapshot.changed),
                fix=False,
                allow_plugins=allow_plugins,
                fail_on=fail_on,
                commit=snapshot.commit,
                parent=snapshot.parent,
                changed_paths=snapshot.changed,
            )
            snapshot.verify()
            return report
    return _run(
        root,
        config_name=config_name,
        mode=mode,
        base=base,
        files=files,
        fix=fix,
        allow_plugins=allow_plugins,
        fail_on=fail_on,
    )


def _run(
    root,
    *,
    config_name,
    mode,
    base=None,
    files=None,
    fix=False,
    allow_plugins=False,
    fail_on="error",
    commit=None,
    parent=None,
    changed_paths=None,
):
    policy = load_policy(root, config_name)
    config = policy.config
    names, skipped = select_files(root, config, mode, base, files)
    all_names, review_targets = None, {}
    if policy.contracts:
        all_names, _ = select_files(root, config, mode="all")
        changes = working_changes(root, base=base) if changed_paths is None else changed_paths
        changes = changes | set(names)
        names, review_targets = review_scope(policy, names, all_names, changes)
    rules = config.get("rules", [])
    diagnostics, fixed = navigation_diagnostics(root, policy), []
    repository_checks = []

    def excepted(rule, name):
        return any(
            e["rule"] == rule["id"] and matches(name, e["files"])
            for e in config.get("exceptions", [])
        )

    for rule in rules:
        if rule["kind"] != "required-path" or excepted(rule, rule["path"]):
            continue
        name = rule["path"]
        try:
            path = safe_path(root, name)
            exists = path.is_dir() if rule.get("type") == "directory" else path.is_file()
        except PolicyError:
            exists = False
        if not exists:
            diagnostics.append(diagnostic(rule, name, "required path is missing or is a symlink"))
    graph_rules = [rule for rule in rules if rule["kind"] == "markdown-reachable"]
    if graph_rules:
        # Link deletion can orphan unchanged documents; graph rules always read all docs.
        if all_names is None:
            all_names, _ = select_files(root, config, mode="all")
        for rule in graph_rules:

            def graph_excepted(rule, name):
                return excepted(rule, name) or not policy.in_scope(rule["id"], name)

            found, summary = check_reachability(
                root, rule, all_names, config.get("max_file_bytes", LIMIT), graph_excepted
            )
            diagnostics.extend(found)
            repository_checks.append(summary)
    for name in names:
        path = safe_path(root, name)
        active = [
            r
            for r in rules
            if r["kind"] not in ("required-path", "markdown-reachable")
            and policy.applies(r, name)
            and not excepted(r, name)
        ]
        text_rules = []
        for rule in active:
            if rule["kind"] == "forbidden-path":
                diagnostics.append(diagnostic(rule, name, "forbidden path"))
            elif rule["kind"] == "max-bytes":
                if path.stat().st_size > rule["bytes"]:
                    diagnostics.append(
                        diagnostic(rule, name, f"file exceeds {rule['bytes']} bytes")
                    )
            else:
                text_rules.append(rule)
        if not text_rules:
            continue
        with path.open("rb") as stream:
            raw = stream.read(config.get("max_file_bytes", LIMIT) + 1)
        if len(raw) > config.get("max_file_bytes", LIMIT):
            raise PolicyError(
                f"{name}: exceeds max_file_bytes; exclude it or raise the explicit limit"
            )
        try:
            if b"\0" in raw:
                raise UnicodeError()
            text = raw.decode("utf-8")
        except UnicodeError:
            # A configured text rule must never silently pass an uncheckable file.
            raise PolicyError(
                f"{name}: configured text rule requires UTF-8 text without NUL"
            ) from None
        found = [d for rule in text_rules for d in check_text(rule, name, text)]
        if fix and any(d.fixable for d in found):
            append_newline(root, name, raw)
            fixed.append(name)
            text += "\r\n" if b"\r\n" in raw else "\n"
            found = [d for rule in text_rules for d in check_text(rule, name, text)]
        diagnostics.extend(found)
    for plugin in config.get("plugins", []):
        chosen = [
            name
            for name in names
            if not excepted(plugin, name) and policy.in_scope(plugin["id"], name)
        ]
        if any(applies(name, plugin) for name in chosen):
            if not allow_plugins:
                raise PolicyError(
                    f"{plugin['id']}: external command requires --allow-plugins after review"
                )
            diagnostics.extend(run_plugin(plugin, root, chosen))
    contracts = []
    requests = review_requests(root, policy, review_targets, commit=commit, parent=parent)
    if policy.contracts:
        contracts = contract_results(policy, names, diagnostics, all_names, review_targets)
    diagnostics.sort()
    rank = {"info": 0, "warning": 1, "error": 2}
    failed = any(rank[d.severity] >= rank[fail_on] for d in diagnostics) or any(
        c["status"] == "failed" for c in contracts
    )
    report = {
        "schema_version": 1,
        "engine_version": __version__,
        "config_version": config["version"],
        "selection": "commit" if commit else ("files" if files is not None else mode),
        "files_checked": names,
        "diagnostics": [d.json() for d in diagnostics],
        "fixed": fixed,
        "skipped": skipped,
        "exit_code": 1 if failed else 0,
        "review_requests": requests,
        "review_required": bool(requests),
    }
    if commit:
        report.update(commit=commit, base_commit=parent, changed_files=sorted(changed_paths))
    if repository_checks:
        report["repository_checks"] = repository_checks
    if contracts:
        report["contracts"] = contracts
    return report
