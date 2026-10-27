import importlib.util
import json
import shutil
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

import yaml

from repo_policy.engine import run

PROJECT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "project_checks", PROJECT / ".repo-policy/scripts/check_project.py"
)
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class ProjectCheckTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "repo"
        self.root.mkdir()
        for name in (
            "pyproject.toml",
            "uv.lock",
            "README.md",
            "CHANGELOG.md",
            "docs/releasing.md",
            ".pre-commit-config.yaml",
            ".github/workflows/ci.yml",
        ):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PROJECT / name, target)
        for directory in ("src/repo_policy", "skills/repo-policy-setup"):
            shutil.copytree(
                PROJECT / directory,
                self.root / directory,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        self.version = tomllib.loads((self.root / "pyproject.toml").read_text())["project"][
            "version"
        ]

    def put(self, name, text):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def codes(self):
        return {d["code"] for d in CHECKER.check(self.root)}

    def yaml_edit(self, name, change):
        data = yaml.safe_load((self.root / name).read_text())
        change(data)
        self.put(name, yaml.safe_dump(data, sort_keys=False))

    def test_valid_project_has_no_diagnostics(self):
        self.assertEqual(CHECKER.check(self.root), [])

    def test_version_mirrors_and_current_examples_must_match(self):
        self.put("src/repo_policy/__init__.py", '__version__ = "9.9.9"\n')
        lock = (self.root / "uv.lock").read_text()
        lock = lock.replace(
            f'name = "repository-policy-linter"\nversion = "{self.version}"',
            'name = "repository-policy-linter"\nversion = "9.9.9"',
        )
        self.put("uv.lock", lock)
        self.put("README.md", "Install repository_policy_linter-9.9.9-py3-none-any.whl\n")
        issues = CHECKER.check(self.root)
        self.assertIn("release-version-sync", {d["code"] for d in issues})
        self.assertIn("installation-version", {d["code"] for d in issues})
        self.assertEqual(
            {d["file"] for d in issues}, {"uv.lock", "src/repo_policy/__init__.py", "README.md"}
        )

    def test_changelog_needs_current_nonempty_section(self):
        self.put("CHANGELOG.md", "# Changelog\n\n## 9.9.9\n\n- Other version\n")
        self.assertIn("changelog-version", self.codes())
        self.put("CHANGELOG.md", f"# Changelog\n\n## {self.version}\n\n## 0.0.1\n\n- Old\n")
        self.assertIn("changelog-version", self.codes())

    def test_core_dependency_and_python_target_contract(self):
        text = (self.root / "pyproject.toml").read_text()
        text = text.replace('"PyYAML>=6.0.3,<7"', '"PyYAML>=6.0.3,<7", "requests==2.0.0"')
        text = text.replace('requires-python = ">=3.11"', 'requires-python = ">=3.10"')
        self.put("pyproject.toml", text)
        self.assertTrue({"runtime-dependencies", "python-target"} <= self.codes())

    def test_optional_self_dependency_is_also_forbidden(self):
        text = (
            (self.root / "pyproject.toml")
            .read_text()
            .replace(
                "[project.optional-dependencies]",
                '[project.optional-dependencies]\nself-copy = ["repository-policy-linter==9.9.9"]',
            )
        )
        self.put("pyproject.toml", text)
        self.assertIn("no-self-dependency", self.codes())

    def test_changed_tool_pin_requires_compatible_lock_entry(self):
        text = (self.root / "pyproject.toml").read_text().replace('"ruff==0.14.2"', '"ruff==9.9.9"')
        self.put("pyproject.toml", text)
        self.assertIn("dependency-lock-sync", self.codes())

    def test_network_import_aliases_are_rejected_but_comments_and_url_parsing_are_allowed(self):
        name = "src/repo_policy/example.py"
        self.put(
            name,
            '"""import requests is only prose."""\nfrom urllib.parse import urlsplit\n# import socket\n',
        )
        self.assertEqual(CHECKER.check(self.root), [])
        self.put(name, "import httpx as client\nfrom urllib import request as fetch\n")
        issues = CHECKER.check(self.root)
        self.assertEqual(
            [d["code"] for d in issues], ["core-network-import", "core-network-import"]
        )
        self.assertEqual([d["line"] for d in issues], [1, 2])

    def test_undeclared_import_is_reported(self):
        self.put("src/repo_policy/example.py", "import unlisted_vendor_sdk\n")
        self.assertIn("core-runtime-import", self.codes())

    def test_skill_cannot_import_or_vendor_engine(self):
        self.put(
            "skills/repo-policy-setup/scripts/configure.py", "from repo_policy import engine\n"
        )
        self.put("skills/repo-policy-setup/src/repo_policy/__init__.py", "# Copied engine\n")
        self.assertEqual(
            sum(d["code"] == "skill-engine-independence" for d in CHECKER.check(self.root)), 2
        )

    def test_post_install_helper_may_use_external_engine_without_vendoring_it(self):
        self.put(
            "skills/repo-policy-setup/scripts/post_install.py", "from repo_policy import cli\n"
        )
        self.assertEqual(CHECKER.check(self.root), [])

    def test_native_skill_dates_cannot_duplicate_top_level_fields(self):
        name = "skills/repo-policy-setup/SKILL.md"
        text = (
            (self.root / name)
            .read_text()
            .replace("\nmetadata:", "\ncreated: '2026-10-26'\nmetadata:", 1)
        )
        self.put(name, text)
        self.assertIn("native-skill-metadata", self.codes())

    def test_native_skill_name_and_description_need_text_values(self):
        name = "skills/repo-policy-setup/SKILL.md"
        text = (self.root / name).read_text().replace("name: repo-policy-setup", "name: 42", 1)
        self.put(name, text)
        self.assertIn("native-skill-metadata", self.codes())

    def test_hook_flags_and_check_only_commands_are_enforced(self):
        self.yaml_edit(
            ".pre-commit-config.yaml",
            lambda data: data["repos"][0]["hooks"][0].update(always_run=False),
        )
        self.assertIn("check-only-hooks", self.codes())
        shutil.copy2(PROJECT / ".pre-commit-config.yaml", self.root / ".pre-commit-config.yaml")
        self.yaml_edit(
            ".pre-commit-config.yaml",
            lambda data: data["repos"][0]["hooks"][1].update(entry="uv run --frozen ruff format"),
        )
        self.assertIn("check-only-hooks", self.codes())

    def test_hook_whitespace_does_not_change_meaning(self):
        self.yaml_edit(
            ".pre-commit-config.yaml",
            lambda data: data["repos"][0]["hooks"][0].update(
                entry="uv   run --frozen repo-policy check --all --allow-plugins"
            ),
        )
        self.assertEqual(CHECKER.check(self.root), [])

    def test_ci_requires_tests_locked_commands_and_history(self):
        name = ".github/workflows/ci.yml"
        self.yaml_edit(
            name, lambda data: data["jobs"]["test"]["steps"][0]["with"].update({"fetch-depth": 1})
        )
        self.assertIn("git-baseline-history", self.codes())
        shutil.copy2(PROJECT / name, self.root / name)
        self.yaml_edit(
            name,
            lambda data: data["jobs"]["test"]["steps"].remove(
                next(
                    s
                    for s in data["jobs"]["test"]["steps"]
                    if s.get("run") == "uv run --frozen python -m unittest discover -s tests -v"
                )
            ),
        )
        self.assertIn("locked-ci", self.codes())

    def test_ci_job_rename_and_full_history_remain_valid(self):
        def edit(data):
            data["jobs"]["renamed"] = data["jobs"].pop("test")
            data["jobs"]["renamed"]["steps"][0]["with"]["fetch-depth"] = 0

        self.yaml_edit(".github/workflows/ci.yml", edit)
        self.assertEqual(CHECKER.check(self.root), [])

    def test_missing_or_malformed_metadata_is_diagnostic_without_source_excerpt(self):
        (self.root / "uv.lock").unlink()
        self.put("pyproject.toml", "secret = [PRIVATE_SOURCE_MARKER\n")
        issues = CHECKER.check(self.root)
        self.assertIn("project-syntax", {d["code"] for d in issues})
        self.assertIn("project-source", {d["code"] for d in issues})
        self.assertNotIn("PRIVATE_SOURCE_MARKER", json.dumps(issues))

    def test_registered_checker_catches_unselected_metadata(self):
        script = ".repo-policy/scripts/check_project.py"
        self.put(script, (PROJECT / script).read_text())
        self.put(
            ".repo-policy/policy.yaml",
            yaml.safe_dump(
                {
                    "version": 2,
                    "plugins": [
                        {
                            "id": "project",
                            "scope": "repository",
                            "format": "json",
                            "files": ["**/*"],
                            "command": [sys.executable, script, "{files}"],
                        }
                    ],
                }
            ),
        )
        self.put("src/repo_policy/__init__.py", '__version__ = "9.9.9"\n')
        report = run(self.root, files=[], allow_plugins=True)
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["files_checked"], [])
        self.assertIn("src/repo_policy/__init__.py", [d["file"] for d in report["diagnostics"]])
