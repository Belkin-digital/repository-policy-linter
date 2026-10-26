import json
import os
import re
import stat
import tempfile

import yaml

from .config import yaml_load
from .files import matches, safe_path
from .model import Diagnostic, PolicyError


def applies(name, rule):
    return matches(name, rule.get("files", ["**/*"])) and not matches(name, rule.get("exclude", []))


def diagnostic(rule, name, message, line=1, column=1, fixable=False):
    return Diagnostic(
        name,
        line,
        column,
        rule["id"],
        rule.get("severity", "error"),
        rule.get("message", message),
        fixable,
    )


def _json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def parse_data(text, name):
    if name.endswith(".json"):
        return json.loads(
            text,
            object_pairs_hook=_json_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")),
        )
    if name.endswith((".yaml", ".yml")):
        return yaml_load(text)
    raise ValueError("structured rule requires .json, .yaml or .yml")


def check_text(rule, name, text):
    kind = rule["kind"]
    if kind in ("forbidden-text", "required-text"):
        found = list(re.finditer(rule["pattern"], text, re.MULTILINE))
        if kind == "required-text":
            return [] if found else [diagnostic(rule, name, "required text is absent")]
        return [
            diagnostic(
                rule,
                name,
                "forbidden text matched",
                text.count("\n", 0, m.start()) + 1,
                m.start() - text.rfind("\n", 0, m.start()),
            )
            for m in found
        ]
    if kind == "final-newline":
        if text and not text.endswith("\n"):
            return [
                diagnostic(
                    rule,
                    name,
                    "missing final newline",
                    text.count("\n") + 1,
                    fixable=rule.get("safe_fix", False),
                )
            ]
        return []
    if kind in ("syntax", "required-keys", "frontmatter"):
        offset = 0
        try:
            if kind == "frontmatter":
                lines = text.splitlines(keepends=True)
                if not lines or lines[0].strip() != "---":
                    return [diagnostic(rule, name, "missing YAML frontmatter")]
                end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
                if end is None:
                    return [diagnostic(rule, name, "unterminated YAML frontmatter")]
                offset = 1
                data = yaml_load("".join(lines[1:end]))
            else:
                data = parse_data(text, name)
        except (ValueError, yaml.YAMLError, RecursionError) as exc:
            mark = getattr(exc, "problem_mark", None)
            line = (mark.line + 1 if mark else getattr(exc, "lineno", 1)) + offset
            column = mark.column + 1 if mark else getattr(exc, "colno", 1)
            # Parser exceptions can quote source content; never include them in reports.
            return [
                diagnostic(
                    rule,
                    name,
                    "invalid structured data (syntax, duplicate key or unsupported YAML alias)",
                    line,
                    column,
                )
            ]
        if kind == "frontmatter" and rule.get("mapping_path"):
            walked = []
            for key in rule["mapping_path"]:
                walked.append(key)
                if not isinstance(data, dict) or key not in data:
                    return [
                        diagnostic(rule, name, "missing frontmatter mapping: " + ".".join(walked))
                    ]
                data = data[key]
            if not isinstance(data, dict):
                return [
                    diagnostic(
                        rule,
                        name,
                        "expected frontmatter mapping: " + ".".join(rule["mapping_path"]),
                    )
                ]
        if kind != "syntax":
            missing = [
                k for k in rule.get("keys", []) if not isinstance(data, dict) or k not in data
            ]
            if not isinstance(data, dict) or missing:
                return [diagnostic(rule, name, "missing mapping keys: " + ", ".join(missing))]
    return []


def append_newline(root, name, original):
    path = safe_path(root, name)
    before = path.stat()
    if before.st_nlink != 1:
        raise PolicyError(f"refusing to fix hardlinked file: {name}")
    if path.read_bytes() != original:
        raise PolicyError(f"file changed while checking: {name}")
    newline = b"\r\n" if b"\r\n" in original else b"\n"
    fd, temporary = tempfile.mkstemp(prefix=".repo-policy-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(original + newline)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, stat.S_IMODE(before.st_mode))
        safe_path(root, name)
        now = path.stat()
        if (now.st_ino, now.st_mtime_ns, now.st_size) != (
            before.st_ino,
            before.st_mtime_ns,
            before.st_size,
        ):
            raise PolicyError(f"file changed during fix: {name}")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
