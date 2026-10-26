import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from repo_policy import __version__
from repo_policy.af import main as af_main
from repo_policy.cli import main
from repo_policy.engine import run
from repo_policy.model import PolicyError

PROJECT = Path(__file__).resolve().parents[1]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, PROJECT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


configure = load_script("configure", "skills/repo-policy-setup/scripts/configure.py").configure
install = load_script("installer", "scripts/install_skill.py").install


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / "repo"
        self.root.mkdir()

    def put(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
        return path

    def config(self, rules=(), **extra):
        return self.put(
            ".repo-policy/policy.yaml",
            yaml.safe_dump({"version": 2, "rules": list(rules), **extra}),
        )

    def rule(self, kind, **options):
        return {"id": "test-rule", "kind": kind, "files": ["**/*.txt"], **options}

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args], check=True, capture_output=True
        ).stdout

    def init_git(self):
        self.git("init", "-b", "main")
        self.git("config", "core.autocrlf", "false")
        self.git("config", "user.email", "tests@example.invalid")
        self.git("config", "user.name", "Test")

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-m", "fixture")

    def cli(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            code = main(args)
        return code, output.getvalue()

    def test_diagnostics_have_locations_and_stable_order(self):
        self.config([self.rule("forbidden-text", pattern="BAD")])
        self.put("z.txt", "first\n BAD BAD\n")
        self.put("a.txt", "BAD\n")
        report = run(self.root)
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(
            [(d["file"], d["line"], d["column"]) for d in report["diagnostics"]],
            [("a.txt", 1, 1), ("z.txt", 2, 2), ("z.txt", 2, 6)],
        )
        self.assertEqual(report, run(self.root))

    def test_warning_threshold(self):
        self.config([self.rule("required-text", pattern="copyright", severity="warning")])
        self.put("a.txt", "hello\n")
        self.assertEqual(run(self.root)["exit_code"], 0)
        self.assertEqual(run(self.root, fail_on="warning")["exit_code"], 1)

    def test_exclusions_and_reasoned_exceptions(self):
        self.config(
            [self.rule("forbidden-path")],
            exclude=["skip/**"],
            exceptions=[{"rule": "test-rule", "files": ["allowed.txt"], "reason": "fixture"}],
        )
        self.put("skip/a.txt", "x")
        self.put("allowed.txt", "x")
        self.put("bad.txt", "x")
        self.assertEqual([d["file"] for d in run(self.root)["diagnostics"]], ["bad.txt"])

    def test_required_directory_even_with_empty_selection(self):
        self.config(
            [{"id": "directory", "kind": "required-path", "path": "specs", "type": "directory"}]
        )
        self.init_git()
        self.commit()
        self.assertEqual(run(self.root, mode="changed")["exit_code"], 1)
        (self.root / "specs").mkdir()
        self.assertEqual(run(self.root, mode="changed")["exit_code"], 0)

    def test_changed_includes_staged_unstaged_untracked_not_ignored(self):
        self.init_git()
        self.config([self.rule("forbidden-text", pattern="BAD")])
        self.put(".gitignore", "ignored.txt\n")
        self.put("steady.txt", "BAD\n")
        self.put("modified.txt", "ok\n")
        self.put("deleted.txt", "BAD\n")
        self.commit()
        self.put("modified.txt", "BAD\n")
        self.put("staged.txt", "BAD\n")
        self.git("add", "staged.txt")
        self.put("untracked space.txt", "BAD\n")
        self.put("ignored.txt", "BAD\n")
        (self.root / "deleted.txt").unlink()
        report = run(self.root, mode="changed")
        self.assertEqual(
            report["files_checked"], ["modified.txt", "staged.txt", "untracked space.txt"]
        )

    def test_merge_base_and_rename(self):
        self.init_git()
        self.config([self.rule("final-newline")])
        self.put("a.txt", "ok\n")
        self.commit()
        self.git("checkout", "-b", "feature")
        self.git("mv", "a.txt", "renamed.txt")
        self.commit()
        self.assertEqual(
            run(self.root, mode="changed", base="main")["files_checked"], ["renamed.txt"]
        )
        with self.assertRaises(PolicyError):
            run(self.root, mode="changed", base="--output=oops")

    def test_unborn_changed_and_changed_requires_git_root(self):
        self.config([])
        with self.assertRaises(PolicyError):
            run(self.root, mode="changed")
        self.init_git()
        self.put("a.txt", "x")
        self.git("add", "a.txt")
        self.assertIn("a.txt", run(self.root, mode="changed")["files_checked"])

    def test_explicit_files_and_option_like_names(self):
        self.config([self.rule("forbidden-text", pattern="BAD")])
        self.put("--danger.txt", "BAD\n")
        self.put("untouched.txt", "BAD\n")
        self.assertEqual(run(self.root, files=["--danger.txt"])["files_checked"], ["--danger.txt"])

    @unittest.skipUnless(os.name == "posix", "POSIX mode-bit contract")
    def test_fix_preserves_markdown_spaces_crlf_permissions_and_is_idempotent(self):
        self.config([self.rule("final-newline", safe_fix=True, files=["**/*.md"])])
        path = self.put("a.md", b"first  \r\nsecond  ")
        path.chmod(0o640)
        first = run(self.root, fix=True)
        self.assertEqual(first["fixed"], ["a.md"])
        self.assertEqual(path.read_bytes(), b"first  \r\nsecond  \r\n")
        self.assertEqual(path.stat().st_mode & 0o777, 0o640)
        self.assertEqual(run(self.root, fix=True)["fixed"], [])

    def test_fix_requires_rule_opt_in_and_dry_run_does_not_write(self):
        self.config([self.rule("final-newline")])
        path = self.put("a.txt", "x")
        self.assertEqual(run(self.root, fix=True)["exit_code"], 1)
        self.config([self.rule("final-newline", safe_fix=True)])
        code, report = self.cli(["fix", "--root", str(self.root), "--dry-run", "--format", "json"])
        self.assertEqual(code, 1)
        self.assertTrue(json.loads(report)["diagnostics"][0]["fixable"])
        self.assertEqual(path.read_bytes(), b"x")

    @unittest.skipUnless(os.name == "posix", "symlink privileges vary on Windows")
    def test_symlinks_and_path_traversal(self):
        self.config([self.rule("final-newline", safe_fix=True)])
        outside = Path(self.temporary.name) / "outside.txt"
        outside.write_text("secret")
        (self.root / "link.txt").symlink_to(outside)
        report = run(self.root, fix=True)
        self.assertEqual(report["skipped"], [{"file": "link.txt", "reason": "symlink"}])
        self.assertEqual(outside.read_text(), "secret")
        for name in ("../outside.txt", str(outside), "link.txt"):
            with self.subTest(name=name), self.assertRaises(PolicyError):
                run(self.root, files=[name], fix=True)

    @unittest.skipUnless(os.name == "posix", "symlink privileges vary on Windows")
    def test_config_symlink_rejected(self):
        outside = Path(self.temporary.name) / "config"
        outside.write_text("version: 2\n")
        (self.root / ".repo-policy").mkdir()
        (self.root / ".repo-policy/policy.yaml").symlink_to(outside)
        with self.assertRaises(PolicyError):
            run(self.root)

    def test_hardlinked_fix_rejected(self):
        self.config([self.rule("final-newline", safe_fix=True)])
        path = self.put("a.txt", "x")
        os.link(path, self.root / "b.txt")
        with self.assertRaises(PolicyError):
            run(self.root, fix=True)
        self.assertEqual(path.read_text(), "x")

    def test_binary_and_oversized_text_fail_closed(self):
        self.config([self.rule("final-newline")], max_file_bytes=10)
        path = self.put("a.txt", b"\x00binary")
        with self.assertRaises(PolicyError):
            run(self.root)
        path.write_text("a" * 11)
        with self.assertRaises(PolicyError):
            run(self.root)

    def test_binary_file_size_rule_does_not_decode(self):
        self.config([self.rule("max-bytes", bytes=3, files=["**/*.bin"])])
        self.put("a.bin", b"\x00\xffabcd")
        self.assertEqual(run(self.root)["exit_code"], 1)

    def test_json_yaml_syntax_duplicates_aliases_and_no_source_excerpt(self):
        self.config(
            [self.rule("syntax", files=["*.json", "*.yaml"], exclude=[".repo-policy/policy.yaml"])]
        )
        for name, content in [
            ("a.json", '{"x":1,"x":2}'),
            ("a.yaml", "x: 1\nx: 2\n"),
            ("b.json", '{"secret-value":'),
            ("b.yaml", "x: &a [*a]\n"),
        ]:
            self.put(name, content)
        report = run(self.root)
        self.assertEqual(len(report["diagnostics"]), 4)
        self.assertNotIn("secret-value", json.dumps(report))

    def test_frontmatter_and_required_mapping_keys(self):
        self.config(
            [
                self.rule("frontmatter", files=["*.md"], keys=["id", "status"]),
                {"id": "keys", "kind": "required-keys", "files": ["*.json"], "keys": ["openapi"]},
            ]
        )
        self.put("spec.md", "---\nid: REQ-1\n---\ntext\n")
        self.put("api.json", '{"openapi":"3.1.0"}\n')
        report = run(self.root)
        self.assertEqual(len(report["diagnostics"]), 1)
        self.assertIn("status", report["diagnostics"][0]["message"])

    def test_frontmatter_nested_mapping_requires_both_date_keys(self):
        self.config(
            [
                self.rule(
                    "frontmatter",
                    files=["*.md"],
                    mapping_path=["metadata"],
                    keys=["created", "updated"],
                )
            ]
        )
        path = self.put(
            "SKILL.md",
            "---\nname: example\nmetadata:\n  created: 2026-10-26\n  updated: 2026-10-26\n---\nBody\n",
        )
        self.assertEqual(run(self.root)["exit_code"], 0)
        path.write_text(
            "---\ncreated: 2026-10-26\nupdated: 2026-10-26\nmetadata:\n  created: 2026-10-26\n---\nBody\n"
        )
        report = run(self.root)
        self.assertEqual(report["exit_code"], 1)
        self.assertIn("updated", report["diagnostics"][0]["message"])
        for value in ("null", "wrong-type", "[]"):
            path.write_text(f"---\nmetadata: {value}\n---\nBody\n")
            self.assertEqual(run(self.root)["exit_code"], 1)
        path.write_text("---\nname: example\n---\nBody\n")
        self.assertIn("missing frontmatter mapping", run(self.root)["diagnostics"][0]["message"])

    def test_frontmatter_mapping_path_preserves_literal_key_contract(self):
        self.config([self.rule("frontmatter", files=["*.md"], keys=["metadata.created"])])
        path = self.put("doc.md", "---\nmetadata:\n  created: 2026-10-26\n---\nBody\n")
        self.assertEqual(run(self.root)["exit_code"], 1)
        path.write_text("---\nmetadata.created: 2026-10-26\n---\nBody\n")
        self.assertEqual(run(self.root)["exit_code"], 0)
        self.config(
            [
                self.rule(
                    "frontmatter",
                    files=["*.md"],
                    mapping_path=["a", "b"],
                    keys=["created", "updated"],
                )
            ]
        )
        path.write_text(
            "---\na:\n  b:\n    created: 2026-10-26\n    updated: 2026-10-26\n---\nBody\n"
        )
        self.assertEqual(run(self.root)["exit_code"], 0)

    def test_frontmatter_nested_policy_has_identical_af_report(self):
        self.config(
            [
                self.rule(
                    "frontmatter",
                    files=["*.md"],
                    mapping_path=["metadata"],
                    keys=["created", "updated"],
                )
            ]
        )
        self.put("SKILL.md", "---\nmetadata:\n  created: '2026-10-26'\n---\nBody\n")
        expected = run(self.root)
        self.assertEqual(expected["exit_code"], 1)
        session = Path(self.temporary.name)
        output = session / "runs/dates/output"
        with contextlib.redirect_stdout(io.StringIO()):
            code = af_main(
                [
                    "--root",
                    str(self.root),
                    "--session-root",
                    str(session),
                    "--output-dir",
                    str(output),
                ]
            )
        self.assertEqual(code, 1)
        self.assertEqual(json.loads((output / "report.json").read_text()), expected)

    def test_invalid_configs_exit_two(self):
        invalid = [
            "version: 99\n",
            "version: 2\nversion: 2\n",
            "version: 2\nunknown: true\n",
            "version: 2\nrules: true\n",
            "version: 2\nrules: [{id: x, kind: typo}]\n",
            "version: 2\nrules: [{id: x, kind: forbidden-text, pattern: '['}]\n",
            "version: 2\nrules: [{id: x, kind: final-newline, safe_fix: 'yes'}]\n",
            "version: 2\nrules: [{id: x, kind: required-path, path: ../x}]\n",
            "version: 2\nrules: [{id: x, kind: syntax}, {id: x, kind: syntax}]\n",
            "version: 2\nexceptions: [{rule: absent, files: ['*'], reason: why}]\n",
            "version: 2\nrules: [{id: x, kind: []}]\n",
            "version: 2\nexceptions: [{rule: [], files: ['*'], reason: why}]\n",
            "version: 2\nrules: [{id: x, kind: frontmatter, mapping_path: metadata}]\n",
            "version: 2\nrules: [{id: x, kind: frontmatter, mapping_path: [null]}]\n",
        ]
        for content in invalid:
            with self.subTest(config=content):
                self.put(".repo-policy/policy.yaml", content)
                code, output = self.cli(["check", "--root", str(self.root), "--format", "json"])
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(output)["exit_code"], 2)

    def test_large_config_and_unsafe_yaml_are_rejected(self):
        for content in (
            "version: 2\n#" + "x" * 1_048_576,
            "!!python/object/apply:os.system ['echo unsafe']\n",
        ):
            self.put(".repo-policy/policy.yaml", content)
            with self.assertRaises(PolicyError):
                run(self.root)

    def test_cli_usage_base_and_missing_plugin_are_execution_errors(self):
        self.config([])
        self.assertEqual(self.cli(["check", "--root", str(self.root), "--base", "main"])[0], 2)
        self.config(
            [],
            plugins=[
                {
                    "id": "missing-tool",
                    "command": ["unavailable-policy-tool-001", "{files}"],
                    "format": "json",
                    "files": ["*.txt"],
                }
            ],
        )
        self.put("a.txt", "text")
        self.assertEqual(self.cli(["check", "--root", str(self.root), "--allow-plugins"])[0], 2)

    def test_valid_structured_files_pass_and_yaml_error_location_is_preserved(self):
        self.config(
            [
                self.rule("syntax", files=["*.json"]),
                {"id": "meta", "kind": "frontmatter", "files": ["*.md"], "keys": ["id"]},
            ]
        )
        self.put("a.json", '{"name":"value","nested":[1,true,null]}\n')
        path = self.put("a.md", "---\nid: example\n---\ntext\n")
        self.assertEqual(run(self.root)["exit_code"], 0)
        path.write_text("---\nid: [broken\n---\n")
        self.assertGreaterEqual(run(self.root)["diagnostics"][0]["line"], 2)

    def test_distribution_version_matches_runtime(self):
        metadata = tomllib.loads((PROJECT / "pyproject.toml").read_text())
        self.assertEqual(metadata["project"]["version"], __version__)

    def test_init_never_overwrites_and_explain(self):
        code, _ = self.cli(["init", "--root", str(self.root)])
        self.assertEqual(code, 0)
        before = (self.root / ".repo-policy/policy.yaml").read_bytes()
        self.assertEqual(self.cli(["init", "--root", str(self.root)])[0], 2)
        self.assertEqual((self.root / ".repo-policy/policy.yaml").read_bytes(), before)
        self.assertEqual(self.cli(["explain", "readme", "--root", str(self.root)])[0], 0)
        self.assertEqual(self.cli(["explain", "syntax"])[0], 0)

    def plugin(self, body, **options):
        script = self.put("plugin.py", body)
        plugin = {
            "id": "external",
            "command": [sys.executable, str(script), "{files}"],
            "format": "json",
            "files": ["*.txt"],
            **options,
        }
        self.config([], plugins=[plugin])
        self.put("a.txt", "x\n")
        return plugin

    def test_plugins_require_explicit_execution_authorization(self):
        self.plugin("from pathlib import Path\nPath('executed').write_text('bad')\nprint('[]')\n")
        with self.assertRaises(PolicyError):
            run(self.root)
        self.assertFalse((self.root / "executed").exists())

    def test_bare_python_plugin_uses_interpreter_from_path(self):
        plugin = self.plugin(
            "import sys\nprint('[]')\nsys.exit(0 if sys.prefix == sys.argv[1] else 2)\n"
        )
        plugin["command"] = [Path(sys.executable).name, plugin["command"][1], sys.prefix, "{files}"]
        self.config([], plugins=[plugin])
        path = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
        with patch.dict(os.environ, {"PATH": path}):
            report = run(self.root, allow_plugins=True)
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["diagnostics"], [])

    def test_json_plugin_no_shell_interpolation(self):
        self.plugin(
            "import json,sys\nprint(json.dumps([{'file':sys.argv[1], 'line':2, 'message':'issue'}]))\nsys.exit(1)\n"
        )
        name = "$(touch injected);.txt"
        (self.root / "a.txt").rename(self.root / name)
        report = run(self.root, allow_plugins=True)
        self.assertEqual(report["diagnostics"][0]["file"], name)
        self.assertFalse((self.root / "injected").exists())

    def test_ruff_and_regex_adapters(self):
        self.plugin(
            "import json\nprint(json.dumps([{'filename':'a.txt','location':{'row':3,'column':2},'code':'F401','message':'unused'}]))\n",
            format="ruff",
        )
        self.assertIn("F401", run(self.root, allow_plugins=True)["diagnostics"][0]["message"])
        self.plugin(
            "print('a.txt:3:unused')\n",
            format="regex",
            pattern=r"(?P<file>.+):(?P<line>\d+):(?P<message>.+)",
        )
        self.assertEqual(run(self.root, allow_plugins=True)["diagnostics"][0]["line"], 3)

    def test_plugin_errors_never_pass_cleanly(self):
        bodies = [
            "print('invalid json')",
            "print('[]'); raise SystemExit(2)",
            "print('[]'); raise SystemExit(1)",
            'print(\'[{"file":"../outside","line":1,"message":"bad"}]\')',
            'print(\'[{"file":"not-selected","line":1,"message":"bad"}]\')',
        ]
        for body in bodies:
            self.plugin(body)
            with self.subTest(body=body), self.assertRaises(PolicyError):
                run(self.root, allow_plugins=True)

    def test_plugin_timeout_and_output_limit(self):
        self.plugin("import time\ntime.sleep(10)\n", timeout=1)
        with self.assertRaisesRegex(PolicyError, "timed out"):
            run(self.root, allow_plugins=True)
        self.plugin("print('x' * 4194305)")
        with self.assertRaisesRegex(PolicyError, "4 MiB"):
            run(self.root, allow_plugins=True)

    def test_cli_and_af_produce_identical_policy_report(self):
        self.config([self.rule("forbidden-text", pattern="BAD")])
        self.put("a.txt", "BAD\n")
        expected = run(self.root)
        session = Path(self.temporary.name)
        output = session / "runs/test/output"
        with contextlib.redirect_stdout(io.StringIO()):
            code = af_main(
                [
                    "--root",
                    str(self.root),
                    "--session-root",
                    str(session),
                    "--output-dir",
                    str(output),
                ]
            )
        self.assertEqual(code, 1)
        self.assertEqual(json.loads((output / "report.json").read_text()), expected)
        fragment = json.loads((output / "outputs.fragment.json").read_text())
        self.assertEqual(
            fragment["outputs"][0]["session_path"], "/session/runs/test/output/report.json"
        )
        self.assertFalse(fragment["outputs"][0]["publish"])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                af_main(
                    [
                        "--root",
                        str(self.root),
                        "--session-root",
                        str(session),
                        "--output-dir",
                        str(output),
                    ]
                ),
                2,
            )

    def test_af_reports_configuration_failure_and_protects_repo(self):
        session = Path(self.temporary.name)
        output = session / "runs/failure"
        with contextlib.redirect_stdout(io.StringIO()):
            code = af_main(
                [
                    "--root",
                    str(self.root),
                    "--session-root",
                    str(session),
                    "--output-dir",
                    str(output),
                ]
            )
            blocked = af_main(
                [
                    "--root",
                    str(self.root),
                    "--session-root",
                    str(session),
                    "--output-dir",
                    str(self.root / "out"),
                ]
            )
        self.assertEqual(code, 2)
        self.assertEqual(blocked, 2)
        self.assertEqual(json.loads((output / "report.json").read_text())["exit_code"], 2)

    def test_setup_is_idempotent_preserves_existing_config_and_requires_apply(self):
        self.init_git()
        engine = "repository-policy-linter==" + __version__
        configure(self.root, engine)
        self.assertFalse((self.root / ".repo-policy/policy.yaml").exists())
        self.put("AGENTS.md", "Existing instructions.\n")
        configure(self.root, engine, True, "AGENTS.md")
        first = {
            p.relative_to(self.root).as_posix(): p.read_bytes()
            for p in self.root.rglob("*")
            if p.is_file() and ".git" not in p.parts
        }
        configure(self.root, engine, True, "AGENTS.md")
        self.assertEqual(
            first,
            {
                p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob("*")
                if p.is_file() and ".git" not in p.parts
            },
        )
        self.put(".repo-policy/policy.yaml", "version: 2\n# custom policy\nrules: []\n")
        configure(self.root, engine, True)
        self.assertIn("custom policy", (self.root / ".repo-policy/policy.yaml").read_text())

    def test_setup_preserves_custom_bundle_without_injecting_undeclared_registry(self):
        self.init_git()
        policy = self.put(".repo-policy/policy.yaml", "version: 2\nrules: []\n")
        before = policy.read_bytes()
        configure(self.root, "repository-policy-linter==" + __version__, True)
        self.assertEqual(policy.read_bytes(), before)
        self.assertFalse((self.root / ".repo-policy/checks/common.yaml").exists())
        self.assertEqual(run(self.root)["exit_code"], 0)

    def test_setup_refuses_incomplete_policy_directory_before_writing(self):
        self.init_git()
        custom = self.put(".repo-policy/readme/notes.md", "User content\n")
        with self.assertRaisesRegex(ValueError, "no manifest"):
            configure(self.root, "repository-policy-linter==" + __version__, True)
        self.assertEqual(custom.read_text(), "User content\n")
        self.assertFalse((self.root / ".repo-policy/policy.yaml").exists())

    def test_setup_accepts_markdown_extra_and_preserves_existing_base_pin(self):
        self.init_git()
        base = "repository-policy-linter==" + __version__
        extra = "repository-policy-linter[markdown]==" + __version__
        configure(self.root, extra, True)
        requirements = self.root / ".repo-policy/requirements.txt"
        self.assertEqual(requirements.read_text(), extra + "\n")
        first = requirements.read_bytes()
        configure(self.root, extra, True)
        self.assertEqual(requirements.read_bytes(), first)
        requirements.write_text(base + "\n")
        result = configure(self.root, extra, True)
        self.assertEqual(requirements.read_text(), base + "\n")
        self.assertFalse(
            next(
                a
                for a in result["actions"]
                if a["file"] == requirements.relative_to(self.root).as_posix()
            )["matches"]
        )
        wheel = (
            "repository-policy-linter[markdown] @ https://example.invalid/engine.whl#sha256="
            + "a" * 64
        )
        requirements.unlink()
        configure(self.root, wheel, True)
        self.assertEqual(requirements.read_text(), wheel + "\n")
        with self.assertRaises(ValueError):
            configure(self.root, "repository-policy-linter[unknown]==" + __version__)

    @unittest.skipUnless(os.name == "posix", "symlink privileges vary on Windows")
    def test_setup_preserves_symlink_instructions_and_rejects_unpinned_source(self):
        self.init_git()
        self.put("AGENTS.md", "existing")
        (self.root / "CLAUDE.md").symlink_to("AGENTS.md")
        with self.assertRaises(ValueError):
            configure(self.root, "repository-policy-linter==0.1.0", True, "CLAUDE.md")
        self.assertFalse((self.root / ".repo-policy/policy.yaml").exists())
        for bad in [
            "repository-policy-linter",
            "--index-url http://evil",
            "repo==1\nanything",
            "repository-policy-linter @ https://example.org/x.whl",
        ]:
            with self.subTest(engine=bad), self.assertRaises(ValueError):
                configure(self.root, bad, True)

    def test_skill_installer_is_idempotent_and_preserves_differences(self):
        source = PROJECT / "skills/repo-policy-setup"
        destination = Path(self.temporary.name).resolve() / "skills/repo-policy-setup"
        install(source, destination)
        self.assertIn("identical", install(source, destination))
        (destination / "SKILL.md").write_text("user edits")
        with self.assertRaises(ValueError):
            install(source, destination)
        self.assertEqual((destination / "SKILL.md").read_text(), "user edits")


if __name__ == "__main__":
    unittest.main()
