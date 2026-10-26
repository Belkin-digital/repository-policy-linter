from pathlib import Path

from . import __version__
from .config import LIMIT, load_config
from .files import matches, safe_path, select_files
from .model import PolicyError
from .plugins import run_plugin
from .rules import append_newline, applies, check_text, diagnostic


def run(
    root,
    *,
    config_name=".repo-policy.yaml",
    mode="all",
    base=None,
    files=None,
    fix=False,
    allow_plugins=False,
    fail_on="error",
):
    root = Path(root).resolve()
    if not root.is_dir():
        raise PolicyError("repository root is not a directory")
    config = load_config(safe_path(root, config_name))
    names, skipped = select_files(root, config, mode, base, files)
    rules = config.get("rules", [])
    diagnostics, fixed = [], []

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
    for name in names:
        path = safe_path(root, name)
        active = [
            r
            for r in rules
            if r["kind"] != "required-path" and applies(name, r) and not excepted(r, name)
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
        chosen = [name for name in names if not excepted(plugin, name)]
        if any(applies(name, plugin) for name in chosen):
            if not allow_plugins:
                raise PolicyError(
                    f"{plugin['id']}: external command requires --allow-plugins after review"
                )
            diagnostics.extend(run_plugin(plugin, root, chosen))
    diagnostics.sort()
    rank = {"info": 0, "warning": 1, "error": 2}
    failed = any(rank[d.severity] >= rank[fail_on] for d in diagnostics)
    return {
        "schema_version": 1,
        "engine_version": __version__,
        "config_version": config["version"],
        "selection": "files" if files else mode,
        "files_checked": names,
        "diagnostics": [d.json() for d in diagnostics],
        "fixed": fixed,
        "skipped": skipped,
        "exit_code": 1 if failed else 0,
    }
