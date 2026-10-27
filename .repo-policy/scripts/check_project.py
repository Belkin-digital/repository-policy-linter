"""Read-only checks of this project's declared release, architecture and integration facts."""

import ast
import json
import re
import shlex
import sys
import tomllib
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from repo_policy.config import yaml_load
from repo_policy.files import safe_path
from repo_policy.history import frontmatter_values

LIMIT = 1_048_576
NETWORK_IMPORTS = {
    "socket",
    "http.client",
    "http.server",
    "urllib.request",
    "ftplib",
    "smtplib",
    "poplib",
    "imaplib",
    "xmlrpc.client",
    "xmlrpc.server",
    "telnetlib",
    "requests",
    "httpx",
    "aiohttp",
    "openai",
    "anthropic",
    "sentry_sdk",
    "posthog",
    "segment",
    "opentelemetry",
}
HOOKS = {
    "repo-policy": ["uv", "run", "--frozen", "repo-policy", "check", "--all", "--allow-plugins"],
    "python-format": ["uv", "run", "--frozen", "ruff", "format", "--check"],
}
CI_COMMANDS = {
    "uv run --frozen python -m unittest discover -s tests -v",
    "uv run --frozen ruff check .",
    "uv run --frozen ruff format --check .",
    "uv run --frozen repo-policy check --all --allow-plugins",
    "uv run --frozen pre-commit validate-config",
    "uv run --frozen pre-commit run --all-files",
    "uv run --frozen uv build",
    "uv run --frozen python scripts/smoke_wheel.py",
}


def normalized(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def check(root):
    root = Path(root).resolve()
    issues, cache = [], {}

    def issue(name, code, message, line=1):
        issues.append({"file": name, "line": line, "code": code, "message": message})

    def read(name):
        if name not in cache:
            try:
                with safe_path(root, name).open("rb") as stream:
                    raw = stream.read(LIMIT + 1)
                if len(raw) > LIMIT or b"\0" in raw:
                    raise ValueError()
                cache[name] = raw.decode("utf-8")
            except Exception:
                issue(name, "project-source", "required source must be safe, bounded UTF-8")
                cache[name] = None
        return cache[name]

    def parse(name, parser):
        text = read(name)
        if text is None:
            return None
        try:
            return parser(text)
        except Exception:
            issue(name, "project-syntax", "cannot parse required project metadata/source")
            return None

    def mapping(value):
        return value if isinstance(value, dict) else {}

    metadata = mapping(parse("pyproject.toml", tomllib.loads))
    project = mapping(metadata.get("project"))
    version = project.get("version")
    if not isinstance(version, str) or not version:
        issue("pyproject.toml", "release-version-sync", "project.version must be nonempty text")
        version = None
    dependencies = project.get("dependencies", [])
    try:
        if not isinstance(dependencies, list):
            raise ValueError()
        required = [Requirement(value) for value in dependencies]
        if (
            len(required) != 1
            or normalized(required[0].name) != "pyyaml"
            or required[0].marker is not None
        ):
            raise ValueError()
    except (InvalidRequirement, TypeError, ValueError):
        issue(
            "pyproject.toml",
            "runtime-dependencies",
            "the only core runtime dependency must be PyYAML",
        )
    try:
        if SpecifierSet(project.get("requires-python", "")) != SpecifierSet(">=3.11"):
            raise ValueError()
    except (InvalidSpecifier, TypeError, ValueError):
        issue("pyproject.toml", "python-target", "requires-python must declare Python >=3.11")
    ruff = mapping(mapping(metadata.get("tool")).get("ruff"))
    if ruff.get("target-version") != "py311":
        issue("pyproject.toml", "python-target", "Ruff must target py311")

    all_dependencies = list(dependencies) if isinstance(dependencies, list) else []
    for group in (
        mapping(project.get("optional-dependencies")),
        mapping(metadata.get("dependency-groups")),
    ):
        for values in group.values():
            if isinstance(values, list):
                all_dependencies.extend(value for value in values if isinstance(value, str))
    for value in all_dependencies:
        try:
            if normalized(Requirement(value).name) == normalized(project.get("name", "")):
                issue(
                    "pyproject.toml",
                    "no-self-dependency",
                    "the source project must not depend on its own distribution",
                )
        except (InvalidRequirement, TypeError):
            issue("pyproject.toml", "runtime-dependencies", "invalid dependency declaration")

    locked = mapping(parse("uv.lock", tomllib.loads)).get("package", [])
    entries = (
        [p for p in locked if isinstance(p, dict) and p.get("name") == project.get("name")]
        if isinstance(locked, list)
        else []
    )
    if (
        len(entries) != 1
        or entries[0].get("version") != version
        or entries[0].get("source") != {"editable": "."}
    ):
        issue(
            "uv.lock",
            "release-version-sync",
            "the editable project entry must match project.version",
        )
    for value in all_dependencies:
        try:
            requirement = Requirement(value)
        except (InvalidRequirement, TypeError):
            continue  # Reported above; do not expose source text in parser errors.
        if requirement.marker is not None or requirement.url:
            continue
        compatible = False
        for package in locked if isinstance(locked, list) else []:
            if not isinstance(package, dict) or not isinstance(package.get("name"), str):
                continue
            if normalized(package["name"]) != normalized(requirement.name):
                continue
            try:
                compatible |= requirement.specifier.contains(
                    Version(package["version"]), prereleases=True
                )
            except (InvalidVersion, KeyError, TypeError):
                continue
        if not compatible:
            issue(
                "uv.lock",
                "dependency-lock-sync",
                f"no compatible locked version for {requirement.name}",
            )
    runtime = parse("src/repo_policy/__init__.py", ast.parse)
    if runtime is not None:
        values = [
            node.value.value if isinstance(node.value, ast.Constant) else None
            for node in runtime.body
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            and any(
                isinstance(target, ast.Name) and target.id == "__version__"
                for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
            )
        ]
        if values != [version] or version is None:
            issue(
                "src/repo_policy/__init__.py",
                "release-version-sync",
                "one literal __version__ must match project.version",
            )
    changelog = read("CHANGELOG.md")
    if changelog is not None:
        headings = list(re.finditer(r"^##\s+(\S+)[^\n]*$", changelog, re.MULTILINE))
        if not headings or headings[0][1] != version:
            issue(
                "CHANGELOG.md",
                "changelog-version",
                "the first version section must match project.version",
            )
        elif not changelog[
            headings[0].end() : headings[1].start() if len(headings) > 1 else None
        ].strip():
            issue(
                "CHANGELOG.md", "changelog-version", "the current version section must not be empty"
            )

    for name in (
        "README.md",
        "docs/releasing.md",
        "skills/repo-policy-setup/references/integration.md",
    ):
        text = read(name)
        if text is None:
            continue
        patterns = (
            r"repository_policy_linter-([0-9]+\.[0-9]+\.[0-9]+)-py3-none-any\.whl",
            r"repository-policy-linter(?:\[markdown\])?==([0-9]+\.[0-9]+\.[0-9]+)",
            r"^(?:\*\*Status:\*\* working version |Version )([0-9]+\.[0-9]+\.[0-9]+)",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.MULTILINE):
                if match[1] != version:
                    issue(
                        name,
                        "installation-version",
                        "current installation examples must match project.version",
                        text.count("\n", 0, match.start()) + 1,
                    )

    bootstrap = "skills/repo-policy-setup/scripts/configure.py"
    read(bootstrap)  # This helper must be runnable before the engine is installed.
    skill_name = "skills/repo-policy-setup/SKILL.md"
    skill = mapping(parse(skill_name, lambda text: frontmatter_values(text.encode(), [])))
    if (
        any(
            not isinstance(skill.get(key), str) or not skill[key].strip()
            for key in ("name", "description")
        )
        or not isinstance(skill.get("metadata"), dict)
        or "created" in skill
        or "updated" in skill
    ):
        issue(
            skill_name,
            "native-skill-metadata",
            "skill name/description must be text and dates must live under metadata",
        )
    for directory, core in (("src/repo_policy", True), ("skills/repo-policy-setup", False)):
        for path in sorted((root / directory).rglob("*.py")):
            name = path.relative_to(root).as_posix()
            tree = parse(name, ast.parse)
            if tree is None:
                continue
            for node in ast.walk(tree):
                modules = (
                    [(a.name, [a.name]) for a in node.names]
                    if isinstance(node, ast.Import)
                    else (
                        [
                            (
                                node.module or "",
                                [node.module or ""]
                                + [f"{node.module}.{a.name}" for a in node.names],
                            )
                        ]
                        if isinstance(node, ast.ImportFrom) and not node.level
                        else []
                    )
                )
                for module, spellings in modules:
                    top = module.split(".")[0]
                    if core and any(
                        name == banned or name.startswith(banned + ".")
                        for name in spellings
                        for banned in NETWORK_IMPORTS
                    ):
                        issue(
                            name,
                            "core-network-import",
                            "network, LLM and telemetry client imports are prohibited in the core",
                            node.lineno,
                        )
                    elif core and top not in sys.stdlib_module_names | {
                        "yaml",
                        "markdown_it",
                        "repo_policy",
                    }:
                        issue(
                            name,
                            "core-runtime-import",
                            "core import is outside stdlib and declared runtime modules",
                            node.lineno,
                        )
                    elif not core and name == bootstrap and top not in sys.stdlib_module_names:
                        issue(
                            name,
                            "skill-engine-independence",
                            "the bootstrap configurator must use only the Python standard library",
                            node.lineno,
                        )
        if not core:
            for path in sorted((root / directory).rglob("repo_policy")):
                if path.is_dir():
                    issue(
                        "skills/repo-policy-setup/SKILL.md",
                        "skill-engine-independence",
                        "do not vendor a repo_policy package inside the skill",
                    )

    hooks = mapping(parse(".pre-commit-config.yaml", yaml_load)).get("repos", [])
    found = {}
    if isinstance(hooks, list):
        for repo in hooks:
            if isinstance(repo, dict) and repo.get("repo") == "local":
                local_hooks = repo.get("hooks", [])
                for hook in local_hooks if isinstance(local_hooks, list) else []:
                    if (
                        isinstance(hook, dict)
                        and isinstance(hook.get("id"), str)
                        and hook["id"] in HOOKS
                    ):
                        found.setdefault(hook["id"], []).append(hook)
    for identifier, command in HOOKS.items():
        candidates = found.get(identifier, [])
        valid = len(candidates) == 1
        hook = candidates[0] if valid else {}
        try:
            valid = valid and shlex.split(hook.get("entry", "")) == command
        except (ValueError, TypeError):
            valid = False
        valid = valid and hook.get("language") == "system" and hook.get("require_serial") is True
        if identifier == "repo-policy":
            valid = valid and hook.get("pass_filenames") is False and hook.get("always_run") is True
        else:
            valid = valid and hook.get("pass_filenames") is True
        if not valid:
            issue(
                ".pre-commit-config.yaml",
                "check-only-hooks",
                f"{identifier} must use the locked check-only command and required hook flags",
            )

    workflow = mapping(parse(".github/workflows/ci.yml", yaml_load))
    candidates = []
    for job in mapping(workflow.get("jobs")).values():
        steps = mapping(job).get("steps", [])
        steps = steps if isinstance(steps, list) else []
        commands = {
            s["run"].strip() for s in steps if isinstance(s, dict) and isinstance(s.get("run"), str)
        }
        if CI_COMMANDS <= commands and any(
            re.fullmatch(r"uv sync --frozen(?: --python .+)?", c) for c in commands
        ):
            candidates.append(steps)
    if not candidates:
        issue(
            ".github/workflows/ci.yml",
            "locked-ci",
            "CI must run frozen sync, tests, lint/format, policy, pre-commit, build and wheel smoke checks",
        )
    depths = [
        mapping(s.get("with")).get("fetch-depth", 1)
        for steps in candidates
        for s in steps
        if isinstance(s, dict)
        and str(s.get("uses", "")).split("@")[0] == "actions/checkout"
        and not mapping(s.get("with")).get("path")
    ]
    if not any(type(d) is int and (d == 0 or d >= 2) for d in depths):
        issue(
            ".github/workflows/ci.yml",
            "git-baseline-history",
            "CI checkout must retain the first parent (fetch-depth 0 or >=2)",
        )
    return issues


if __name__ == "__main__":
    diagnostics = check(Path.cwd())
    print(json.dumps(diagnostics))
    raise SystemExit(1 if diagnostics else 0)
