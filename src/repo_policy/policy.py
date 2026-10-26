"""Local policy bundles, deterministic contract selection and built-in integrity checks."""

import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml

from .config import LIMIT, keys, patterns, read_config, relative, strings, validate, yaml_load
from .files import matches, safe_path, select_files
from .model import Diagnostic, PolicyError
from .rules import applies

DIRECTORIES = {"checks", "contracts", "readme", "rubrics", "scripts", "examples"}
IDENTIFIER = re.compile(r"[a-z][a-z0-9-]{0,63}")


def structure_error(message):
    raise PolicyError("system-policy-structure: " + message)


def identifier(value):
    if (
        not isinstance(value, str)
        or not IDENTIFIER.fullmatch(value)
        or value == "engine"
        or value.startswith("system-")
    ):
        raise PolicyError("system-unique-ids: invalid or reserved ID")
    return value


def unique(values, context):
    if len(values) != len(set(values)):
        raise PolicyError(f"system-unique-ids: duplicate {context}")


def canonical(value):
    relative(value, "policy resource")
    if value != PurePosixPath(value).as_posix():
        structure_error("resource paths must be canonical and repository-relative")


def resource(root, name, directory, section, suffix):
    canonical(name)
    path = PurePosixPath(name)
    if path.parent != PurePosixPath(directory) / section or path.suffix != suffix:
        structure_error(f"expected a {suffix} file directly inside {directory}/{section}")
    target = safe_path(root, name)
    if not target.is_file():
        structure_error(f"missing policy resource: {name}")
    return target


def check_directory(root, manifest, registries, contracts):
    """Inspect even ignored/unselected files; filters never disable system checks."""
    directory = PurePosixPath(manifest).parent
    path = safe_path(root, directory.as_posix())
    expected = set(registries) | set(contracts)
    found = set()
    count = 0

    def walk_error(error):
        structure_error("cannot enumerate the policy directory")

    for current, dirs, files in os.walk(path, followlinks=False, onerror=walk_error):
        for name in sorted(dirs + files):
            candidate = Path(current) / name
            relative_name = candidate.relative_to(root).as_posix()
            safe_path(root, relative_name)
            parts = candidate.relative_to(path).parts
            count += 1
            if count > 4096:
                structure_error("policy directory exceeds 4096 entries")
            if name in {"__pycache__", ".DS_Store"}:
                continue
            if len(parts) == 1:
                if name in DIRECTORIES and candidate.is_dir():
                    continue
                if (
                    name in {PurePosixPath(manifest).name, "requirements.txt"}
                    and candidate.is_file()
                ):
                    continue
                structure_error(f"unexpected policy entry: {relative_name}")
            section = parts[0]
            if section in {"checks", "contracts", "readme", "rubrics"}:
                extension = ".yaml" if section in {"checks", "contracts"} else ".md"
                if len(parts) != 2 or not candidate.is_file() or candidate.suffix != extension:
                    structure_error(f"invalid {section} resource: {relative_name}")
                identifier(candidate.stem)
                if section in {"checks", "contracts"}:
                    found.add(relative_name)
            elif section == "scripts" and candidate.is_file() and candidate.suffix != ".py":
                structure_error(f"scripts must contain Python source files: {relative_name}")
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
    if found != expected:
        structure_error(
            "undeclared or missing registry/contract: " + ", ".join(sorted(found ^ expected))
        )


@dataclass
class Policy:
    config: dict
    definitions: dict
    contracts: dict
    scopes: dict
    directory: str

    def in_scope(self, check, name):
        scopes = self.scopes[check]
        return scopes is None or any(contract_matches(c, name) for c in scopes)

    def applies(self, check, name):
        return applies(name, check) and self.in_scope(check["id"], name)


def contract_matches(contract, name):
    return matches(name, contract["files"]) and not matches(name, contract.get("exclude", []))


def load_policy(root, config_name):
    canonical(config_name)
    manifest_path = safe_path(root, config_name)
    directory = manifest_path.parent.relative_to(root).as_posix()
    if directory == ".":
        structure_error("the manifest must be inside a policy directory")
    manifest = read_config(manifest_path)
    keys(
        manifest,
        {
            "version",
            "exclude",
            "exceptions",
            "rules",
            "plugins",
            "max_file_bytes",
            "registries",
            "contracts",
            "checks",
        },
        "policy",
    )
    registries = manifest.get("registries", [])
    contract_files = manifest.get("contracts", [])
    global_checks = manifest.get("checks", [])
    for name, values in (
        ("registries", registries),
        ("contracts", contract_files),
        ("checks", global_checks),
    ):
        strings(values, name)
        unique(values, name)
    check_directory(root, config_name, registries, contract_files)
    config = {k: v for k, v in manifest.items() if k not in {"registries", "contracts", "checks"}}
    rules = list(config.get("rules", [])) if isinstance(config.get("rules", []), list) else None
    plugins = (
        list(config.get("plugins", [])) if isinstance(config.get("plugins", []), list) else None
    )
    if rules is None or plugins is None:
        structure_error("rules and plugins must be lists")
    inline = [r.get("id") for r in rules + plugins if isinstance(r, dict)]
    for name in registries:
        registry = read_config(resource(root, name, directory, "checks", ".yaml"))
        keys(registry, {"version", "rules", "plugins"}, name)
        validate(registry)
        rules.extend(registry.get("rules", []))
        plugins.extend(registry.get("plugins", []))
    config.update(rules=rules, plugins=plugins)
    validate(config)  # One global namespace across all registry rules/plugins.
    definitions = {r["id"]: r for r in rules + plugins}
    unknown = set(global_checks) - definitions.keys()
    if unknown:
        structure_error("unknown global check IDs: " + ", ".join(sorted(unknown)))
    scopes = {name: None for name in inline + global_checks}
    contracts = {}
    ids = set(definitions)
    for name in contract_files:
        contract = read_config(resource(root, name, directory, "contracts", ".yaml"))
        keys(
            contract,
            {"contract_version", "id", "files", "exclude", "entrypoints", "criteria"},
            name,
        )
        cid = identifier(contract.get("id"))
        if cid in ids:
            raise PolicyError(f"system-unique-ids: duplicate check/contract ID: {cid}")
        ids.add(cid)
        if PurePosixPath(name).stem != cid:
            structure_error("contract filename must equal its ID: " + name)
        if type(contract.get("contract_version")) is not int or contract["contract_version"] != 1:
            structure_error("contract_version must be 1")
        patterns(contract.get("files"), cid + ".files")
        if not contract["files"]:
            structure_error("contract.files must not be empty")
        patterns(contract.get("exclude", []), cid + ".exclude")
        entrypoints = contract.get("entrypoints")
        strings(entrypoints, cid + ".entrypoints", nonempty=True)
        unique(entrypoints, cid + ".entrypoints")
        for entry in entrypoints:
            canonical(entry)
            if PurePosixPath(entry).name not in {"README.md", "AGENTS.md"}:
                structure_error("contract entrypoints must be README.md or AGENTS.md")
            safe_path(root, entry)
        criteria = contract.get("criteria")
        if not isinstance(criteria, list) or not criteria:
            structure_error("contract.criteria must be a nonempty list")
        criterion_ids = []
        for criterion in criteria:
            keys(criterion, {"id", "rule", "rubric"}, cid + ".criteria")
            criterion_ids.append(identifier(criterion.get("id")))
            if ("rule" in criterion) == ("rubric" in criterion):
                structure_error("a criterion must reference exactly one rule or rubric")
            if "rule" in criterion:
                ref = criterion["rule"]
                if not isinstance(ref, str) or ref not in definitions:
                    structure_error(f"{cid}: unknown check ID")
                if ref not in scopes:
                    scopes[ref] = []
                if scopes[ref] is not None:
                    scopes[ref].append(contract)
            else:
                resource(root, criterion["rubric"], directory, "rubrics", ".md")
        unique(criterion_ids, cid + " criterion IDs")
        contracts[cid] = contract
    readme = safe_path(root, directory + "/readme")
    if readme.is_dir():
        for path in readme.iterdir():
            if path.suffix == ".md" and path.stem not in contracts:
                structure_error("explanation has no declared contract: " + path.name)
    config["rules"] = [r for r in rules if r["id"] in scopes]
    config["plugins"] = [p for p in plugins if p["id"] in scopes]
    return Policy(config, definitions, contracts, scopes, directory)


def read_text(root, name):
    with safe_path(root, name).open("rb") as stream:
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise PolicyError(f"{name}: policy navigation input exceeds 1 MiB")
    try:
        if b"\0" in raw:
            raise UnicodeError()
        return raw.decode("utf-8")
    except UnicodeError as exc:
        raise PolicyError(f"{name}: policy navigation requires UTF-8 text without NUL") from exc


def navigation_diagnostics(root, policy):
    """Metadata is an explicit ID index, requiring no optional Markdown parser."""
    expected = {}
    for cid, contract in policy.contracts.items():
        for entry in contract["entrypoints"]:
            expected.setdefault(entry, set()).add(cid)
    names, _ = select_files(root, {"exclude": []}, mode="all")
    candidates = (
        set(expected)
        | ({"AGENTS.md"} if policy.contracts else set())
        | {
            n
            for n in names
            if PurePosixPath(n).name in {"README.md", "AGENTS.md"}
            and not n.startswith(policy.directory + "/examples/")
        }
    )
    diagnostics = []

    def issue(name, message):
        diagnostics.append(Diagnostic(name, 1, 1, "system-contract-navigation", "error", message))

    for name in sorted(candidates):
        path = safe_path(root, name)
        if not path.is_file():
            issue(name, "contract navigation entrypoint is missing")
            continue
        text = read_text(root, name)
        lines = text.splitlines(keepends=True)
        required = name in expected or (name == "AGENTS.md" and policy.contracts)
        if not required and "repo_policy_contracts" not in text and "repo_policy_root" not in text:
            continue
        data = {}
        if lines and lines[0].strip() == "---":
            end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
            try:
                if end is None:
                    raise ValueError()
                data = yaml_load("".join(lines[1:end]))
                if not isinstance(data, dict):
                    raise ValueError()
            except (ValueError, RecursionError, yaml.YAMLError):
                issue(name, "invalid contract navigation frontmatter")
                continue
        declared = data.get("repo_policy_contracts", [])
        if not isinstance(declared, list) or any(not isinstance(i, str) for i in declared):
            issue(name, "repo_policy_contracts must be a list of contract IDs")
            continue
        if len(declared) != len(set(declared)):
            issue(name, "duplicate contract IDs in repo_policy_contracts")
        unknown = set(declared) - policy.contracts.keys()
        if unknown:
            issue(name, "unknown contract IDs: " + ", ".join(sorted(unknown)))
        missing = expected.get(name, set()) - set(declared)
        if missing:
            issue(name, "missing contract IDs: " + ", ".join(sorted(missing)))
        if (
            name == "AGENTS.md"
            and policy.contracts
            and data.get("repo_policy_root") != policy.directory
        ):
            issue(name, "AGENTS.md must declare repo_policy_root: " + policy.directory)
    return diagnostics


def contract_results(policy, names, diagnostics, all_names, review_targets):
    results = []
    for cid, contract in sorted(policy.contracts.items()):
        # Explicit --files can intentionally select an ignored file absent from Git's all set.
        targets = [n for n in sorted(set(all_names) | set(names)) if contract_matches(contract, n)]
        selected = [n for n in targets if n in names]
        criteria = []
        for criterion in contract["criteria"]:
            if "rubric" in criterion:
                status = "needs_review" if review_targets.get(cid) else "not_evaluated"
            else:
                check = policy.definitions[criterion["rule"]]
                structural = check.get("kind") in {"required-path", "markdown-reachable"}
                problems = [
                    d
                    for d in diagnostics
                    if d.rule == check["id"]
                    and (
                        check.get("kind") == "required-path"
                        or d.file in check.get("roots", [])
                        or contract_matches(contract, d.file)
                    )
                ]
                applicable = [n for n in targets if applies(n, check)]
                checked = [n for n in applicable if n in names]
                if problems:
                    status = "failed"
                elif structural or (applicable and len(checked) == len(applicable)):
                    status = "satisfied"
                elif checked:
                    status = "partial"
                else:
                    status = "not_evaluated"
            criteria.append({**criterion, "status": status})
        states = {c["status"] for c in criteria}
        status = next(
            (s for s in ("failed", "needs_review", "not_evaluated", "partial") if s in states),
            "satisfied",
        )
        results.append(
            {
                "id": cid,
                "files": targets,
                "files_checked": selected,
                "status": status,
                "criteria": criteria,
            }
        )
    return results
