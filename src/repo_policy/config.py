import re
from pathlib import PurePosixPath

import yaml

from .model import PolicyError

LIMIT = 1_048_576
CONFIG_NAME = ".repo-policy/policy.yaml"
POLICY_VERSION = 2
SYSTEM_CHECKS = {
    "system-policy-structure": "Validate the policy directory and all declared local resources.",
    "system-unique-ids": "Require unique check/contract IDs and criterion IDs within a contract.",
    "system-contract-navigation": "Validate contract IDs in declared README/AGENTS entrypoints.",
    "system-contract-review": "Generate hashed rubric review requests for the current harness.",
}
KINDS = {
    "required-path": "Require a literal file or directory, in every selection mode.",
    "version-increment": "Require a higher SemVer than HEAD or the checked commit's first parent.",
    "forbidden-path": "Reject matching selected paths.",
    "forbidden-text": "Reject a regular expression in UTF-8 text (multiline mode).",
    "required-text": "Require a regular expression in each matched UTF-8 file.",
    "final-newline": "Require a final newline; opt-in fix appends one without trimming content.",
    "max-bytes": "Limit selected file size without parsing its contents.",
    "syntax": "Parse JSON or YAML using their existing parsers; reject duplicate keys.",
    "required-keys": "Require top-level mapping keys in JSON or YAML.",
    "frontmatter": "Require YAML frontmatter and selected keys in Markdown/specifications.",
    "markdown-reachable": "Require Markdown files to be reachable from explicit local entrypoints.",
}
DEFAULT_CONFIG = """version: 2
registries: ['.repo-policy/checks/common.yaml']
checks: [readme, data-syntax, text-newline]
contracts: []
exclude:
  - dist/**
  - build/**
  - .venv-policy/**
"""
DEFAULT_REGISTRY = """version: 2
rules:
  - id: readme
    kind: required-path
    path: README.md
    type: file
  - id: data-syntax
    kind: syntax
    files: ['**/*.json', '**/*.yaml', '**/*.yml']
  - id: text-newline
    kind: final-newline
    files: ['**/*.py', '**/*.md', '**/*.yaml', '**/*.yml', '**/*.json', '**/*.txt']
    safe_fix: true
plugins: []
"""


class UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            if key in result:
                raise ValueError("duplicate YAML key")
            result[key] = loader.construct_object(value_node, deep=deep)
        except TypeError as exc:
            raise ValueError("YAML mapping keys must be scalar") from exc
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def yaml_load(text):
    # Reject aliases: no cycles, alias expansion surprises, or merge-key ambiguity.
    for event in yaml.parse(text, Loader=yaml.SafeLoader):
        if isinstance(event, yaml.AliasEvent):
            raise ValueError("YAML aliases are unsupported")
    return yaml.load(text, Loader=UniqueLoader)


def keys(data, allowed, context):
    if not isinstance(data, dict) or any(not isinstance(k, str) for k in data):
        raise PolicyError(f"{context}: expected a mapping with string keys")
    unknown = set(data) - set(allowed)
    if unknown:
        raise PolicyError(f"{context}: unknown fields: {', '.join(sorted(unknown))}")


def strings(value, context, nonempty=False):
    if not isinstance(value, list) or any(not isinstance(v, str) or not v for v in value):
        raise PolicyError(f"{context}: expected a list of nonempty strings")
    if nonempty and not value:
        raise PolicyError(f"{context}: list must not be empty")


def relative(value, context, glob=False):
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise PolicyError(f"{context}: expected a relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value == ".":
        raise PolicyError(f"{context}: path must stay inside the repository")
    if not glob and any(c in value for c in "*?["):
        raise PolicyError(f"{context}: requires a literal path")


def patterns(value, context):
    strings(value, context)
    for pattern in value:
        relative(pattern, context, glob=True)


def number(value, context, maximum=LIMIT):
    if type(value) is not int or not 1 <= value <= maximum:
        raise PolicyError(f"{context}: expected integer 1..{maximum}")


def read_config(path):
    try:
        with path.open("rb") as stream:
            raw = stream.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise PolicyError("configuration exceeds 1 MiB")
        config = yaml_load(raw.decode("utf-8"))
    except (OSError, UnicodeError, ValueError, yaml.YAMLError, RecursionError) as exc:
        raise PolicyError(f"cannot parse config {path.name}: {type(exc).__name__}") from exc
    return config


def validate(config):
    keys(
        config, {"version", "exclude", "exceptions", "rules", "plugins", "max_file_bytes"}, "config"
    )
    if type(config.get("version")) is not int or config["version"] != POLICY_VERSION:
        raise PolicyError(f"config.version must be {POLICY_VERSION}")
    patterns(config.get("exclude", []), "exclude")
    number(config.get("max_file_bytes", LIMIT), "max_file_bytes", 100 * LIMIT)
    ids = set()
    rules = config.get("rules", [])
    plugins = config.get("plugins", [])
    if not isinstance(rules, list) or not isinstance(plugins, list):
        raise PolicyError("rules and plugins must be lists")
    for entry in rules + plugins:
        if not isinstance(entry, dict):
            raise PolicyError("each rule/plugin must be a mapping")
        identifier = entry.get("id")
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", identifier):
            raise PolicyError("rule/plugin ids must match [a-z][a-z0-9-]{0,63}")
        if identifier in ids or identifier == "engine" or identifier.startswith("system-"):
            raise PolicyError(f"system-unique-ids: duplicate or reserved id: {identifier}")
        ids.add(identifier)
        if entry.get("severity", "error") not in ("error", "warning", "info"):
            raise PolicyError(f"{identifier}: invalid severity")
        patterns(entry.get("files", ["**/*"]), f"{identifier}.files")
        patterns(entry.get("exclude", []), f"{identifier}.exclude")
    for rule in rules:
        kind = rule.get("kind")
        common = {"id", "kind", "files", "exclude", "severity", "message"}
        options = {
            "required-path": {"path", "type"},
            "version-increment": {"path", "pattern"},
            "forbidden-path": set(),
            "forbidden-text": {"pattern"},
            "required-text": {"pattern"},
            "final-newline": {"safe_fix"},
            "max-bytes": {"bytes"},
            "syntax": set(),
            "required-keys": {"keys"},
            "frontmatter": {"keys", "mapping_path", "preserve_keys"},
            "markdown-reachable": {"roots"},
        }
        if not isinstance(kind, str) or kind not in KINDS:
            raise PolicyError(f"{rule['id']}: unknown rule kind")
        keys(rule, common | options[kind], rule["id"])
        if "message" in rule and (not isinstance(rule["message"], str) or not rule["message"]):
            raise PolicyError("message must be nonempty text")
        if kind == "required-path":
            relative(rule.get("path"), "required-path.path")
            if rule.get("type", "file") not in ("file", "directory"):
                raise PolicyError("required-path.type must be file or directory")
        if kind == "version-increment":
            relative(rule.get("path"), "version-increment.path")
            if rule["path"] != PurePosixPath(rule["path"]).as_posix():
                raise PolicyError("version-increment.path must be canonical")
            if not isinstance(rule.get("pattern"), str):
                raise PolicyError("version-increment requires a string pattern")
            try:
                pattern = re.compile(rule["pattern"], re.MULTILINE)
            except (KeyError, TypeError, re.error) as exc:
                raise PolicyError("version-increment requires a valid pattern") from exc
            if "version" not in pattern.groupindex:
                raise PolicyError("version-increment.pattern requires a named version group")
        if kind in ("forbidden-text", "required-text"):
            if not isinstance(rule.get("pattern"), str):
                raise PolicyError("pattern must be a string")
            try:
                re.compile(rule["pattern"], re.MULTILINE)
            except re.error as exc:
                raise PolicyError("invalid rule pattern") from exc
        if kind == "final-newline" and type(rule.get("safe_fix", False)) is not bool:
            raise PolicyError("safe_fix must be boolean")
        if kind == "max-bytes":
            number(rule.get("bytes"), "max-bytes.bytes", 1024 * LIMIT)
        if kind in ("required-keys", "frontmatter"):
            strings(rule.get("keys", []), "keys")
        if kind == "frontmatter":
            strings(rule.get("mapping_path", []), "frontmatter.mapping_path")
            preserved = rule.get("preserve_keys", [])
            strings(preserved, "frontmatter.preserve_keys")
            if len(preserved) != len(set(preserved)):
                raise PolicyError("frontmatter.preserve_keys must be unique")
        if kind == "markdown-reachable":
            roots = rule.get("roots")
            strings(roots, "markdown-reachable.roots", nonempty=True)
            if len(roots) != len(set(roots)):
                raise PolicyError("markdown-reachable.roots must be unique")
            for root in roots:
                relative(root, "markdown-reachable.roots")
                if root != PurePosixPath(root).as_posix():
                    raise PolicyError("markdown-reachable roots must use canonical paths")
                if not root.lower().endswith((".md", ".markdown")):
                    raise PolicyError("markdown-reachable roots must be Markdown files")
    for plugin in plugins:
        keys(
            plugin,
            {
                "id",
                "command",
                "format",
                "files",
                "exclude",
                "severity",
                "timeout",
                "success_codes",
                "diagnostic_codes",
                "pattern",
                "scope",
            },
            plugin["id"],
        )
        strings(plugin.get("command"), "plugin.command", nonempty=True)
        if plugin.get("scope", "files") not in ("files", "repository"):
            raise PolicyError("plugin.scope must be files or repository")
        if plugin["command"].count("{files}") != 1:
            raise PolicyError("plugin.command must contain one standalone {files} argument")
        if plugin.get("format") not in ("json", "ruff", "regex"):
            raise PolicyError("plugin.format must be json, ruff or regex")
        number(plugin.get("timeout", 30), "plugin.timeout", 300)
        for name, default in (("success_codes", [0]), ("diagnostic_codes", [1])):
            codes = plugin.get(name, default)
            if (
                not isinstance(codes, list)
                or not codes
                or any(type(c) is not int or c < 0 for c in codes)
            ):
                raise PolicyError(f"plugin.{name}: expected nonnegative exit codes")
        if set(plugin.get("success_codes", [0])) & set(plugin.get("diagnostic_codes", [1])):
            raise PolicyError("plugin success and diagnostic codes must be disjoint")
        if plugin.get("format") == "regex":
            try:
                regex = re.compile(plugin.get("pattern", ""))
            except (re.error, TypeError) as exc:
                raise PolicyError("invalid plugin pattern") from exc
            if not {"file", "line", "message"} <= regex.groupindex.keys():
                raise PolicyError("plugin pattern requires named file, line, message groups")
    exceptions = config.get("exceptions", [])
    if not isinstance(exceptions, list):
        raise PolicyError("exceptions must be a list")
    for exception in exceptions:
        keys(exception, {"rule", "files", "reason"}, "exception")
        if not isinstance(exception.get("rule"), str) or exception["rule"] not in ids:
            raise PolicyError("exception references unknown rule/plugin id")
        patterns(exception.get("files"), "exception.files")
        if not isinstance(exception.get("reason"), str) or not exception["reason"].strip():
            raise PolicyError("exception requires a reason")
