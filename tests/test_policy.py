import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from repo_policy.af import main as af_main
from repo_policy.cli import main
from repo_policy.engine import run
from repo_policy.model import PolicyError


class PolicyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "repo"
        self.root.mkdir()
        self.manifest()

    def put(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
        return path

    def data(self, name, value):
        return self.put(name, yaml.safe_dump(value, sort_keys=False))

    def manifest(self, **options):
        return self.data(".repo-policy/policy.yaml", {"version": 2, **options})

    def registry(self, name="docs", rules=None, **options):
        path = f".repo-policy/checks/{name}.yaml"
        self.data(
            path,
            {
                "version": 2,
                "rules": rules
                or [{"id": "title", "kind": "required-text", "pattern": "^# ", "files": ["*.md"]}],
                **options,
            },
        )
        return path

    def contract(self, cid="document", **options):
        path = f".repo-policy/contracts/{cid}.yaml"
        self.data(
            path,
            {
                "contract_version": 1,
                "id": cid,
                "files": ["docs/*"],
                "entrypoints": ["docs/README.md"],
                "criteria": [{"id": "heading", "rule": "title"}],
                **options,
            },
        )
        return path

    def bundle(self, **options):
        self.manifest(registries=[self.registry()], contracts=[self.contract()], **options)
        self.put("AGENTS.md", "---\nrepo_policy_root: .repo-policy\n---\n# Policy instructions\n")
        self.put("docs/README.md", "---\nrepo_policy_contracts: [document]\n---\n# Docs\n")
        self.put("docs/page.md", "# Page\n")

    def cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            code = main([*args, "--root", str(self.root)])
        return code, json.loads(output.getvalue())

    def test_contract_scope_and_unreferenced_checks_do_not_activate_globally(self):
        self.bundle()
        self.put("elsewhere.md", "No title\n")
        self.assertEqual(run(self.root)["exit_code"], 0)
        self.put("docs/page.md", "No title\n")
        report = run(self.root)
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual([d["file"] for d in report["diagnostics"]], ["docs/page.md"])
        self.assertEqual(report["contracts"][0]["status"], "failed")
        self.manifest(registries=[".repo-policy/checks/docs.yaml"])
        self.put(".repo-policy/contracts/document.yaml", "")
        (self.root / ".repo-policy/contracts/document.yaml").unlink()
        self.put("docs/README.md", "No contract index\n")
        self.assertEqual(run(self.root)["exit_code"], 0)

    def test_project_claude_pointer_accepts_lf_and_crlf(self):
        source = Path(__file__).resolve().parents[1] / ".repo-policy/checks/markdown.yaml"
        rules = yaml.safe_load(source.read_text())["rules"]
        rule = next(rule for rule in rules if rule["id"] == "claude-shared-instructions")
        registry = self.registry("claude", rules=[rule])
        self.manifest(registries=[registry], checks=[rule["id"]])
        for newline in (b"\n", b"\r\n"):
            with self.subTest(newline=newline):
                self.put("CLAUDE.md", b"# Instructions" + newline + b"@AGENTS.md" + newline)
                self.assertEqual(run(self.root)["exit_code"], 0)
                self.put("CLAUDE.md", b"@AGENTS.md.extra" + newline)
                report = run(self.root)
                self.assertEqual(report["exit_code"], 1)
                self.assertEqual([d["rule"] for d in report["diagnostics"]], [rule["id"]])

    def test_absent_when_preserves_path_only_selection_without_parsing_metadata(self):
        self.bundle()
        self.put("docs/page.md", "---\nbroken: [\n---\n# Still selected by path\n")
        report = run(self.root)
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["contracts"][0]["files"], ["docs/README.md", "docs/page.md"])

    def test_frontmatter_conditions_intersect_paths_exclusions_and_each_other(self):
        self.bundle()
        self.contract(
            when={"frontmatter": {"artifact_type": "requirement", "status": ["draft", "approved"]}},
            exclude=["docs/archive/*"],
        )
        for name, metadata in {
            "page": "artifact_type: requirement\nstatus: draft",
            "approved": "artifact_type: requirement\nstatus: approved",
            "note": "artifact_type: note\nstatus: draft",
            "closed": "artifact_type: requirement\nstatus: closed",
            "list": "artifact_type: [requirement]\nstatus: draft",
            "missing": "status: draft",
        }.items():
            self.put(f"docs/{name}.md", f"---\n{metadata}\n---\nNo heading\n")
        self.put("elsewhere.md", "---\nbroken: [\n")
        self.put("docs/archive/old.md", "---\nbroken: [\n")
        report = run(self.root)
        expected = ["docs/approved.md", "docs/page.md"]
        self.assertEqual([d["file"] for d in report["diagnostics"]], expected)
        self.assertEqual(report["contracts"][0]["files"], expected)
        self.assertEqual(report["contracts"][0]["files_checked"], expected)
        self.put("docs/README.md", "# Missing navigation\n")
        self.assertIn(
            "system-contract-navigation", [d["rule"] for d in run(self.root)["diagnostics"]]
        )

    def test_invalid_frontmatter_condition_schemas_fail_with_exit_two(self):
        self.bundle()
        for condition in (
            None,
            {},
            [],
            {"expression": "1 / 0"},
            {"frontmatter": {}},
            {"frontmatter": []},
            {"frontmatter": {"": "requirement"}},
            {"frontmatter": {True: "requirement"}},
            {"frontmatter": {"artifact_type": ""}},
            {"frontmatter": {"artifact_type": []}},
            {"frontmatter": {"artifact_type": ["requirement", 1]}},
            {"frontmatter": {"artifact_type": True}},
            {"frontmatter": {"metadata": {"artifact_type": "requirement"}}},
        ):
            with self.subTest(condition=condition):
                self.contract(when=condition)
                code, report = self.cli("check", "--all", "--format", "json")
                self.assertEqual(code, 2)
                self.assertEqual(report["exit_code"], 2)

    def test_missing_and_empty_frontmatter_do_not_match(self):
        self.bundle()
        self.contract(when={"frontmatter": {"artifact_type": "requirement"}})
        for content in (
            "# No header\n",
            "---\n---\n# Empty header\n",
            "---\n \n# Only a comment\n---\n# Page\n",
            "---\nartifact_type: 123\n---\n# Numeric value\n",
            "---\nartifact_type: Requirement\n---\n# Case matters\n",
        ):
            with self.subTest(content=content):
                self.put("docs/page.md", content)
                report = run(self.root)
                self.assertEqual(report["exit_code"], 0)
                self.assertEqual(report["contracts"][0]["files"], [])

    def test_invalid_candidate_frontmatter_is_not_silently_excluded(self):
        self.bundle()
        self.contract(when={"frontmatter": {"artifact_type": "requirement"}})
        for metadata in (
            b"---\nsecret: [PRIVATE-SOURCE-MARKER\n---\n",
            b"---\nartifact_type: requirement\nartifact_type: note\n---\n",
            b"---\nartifact_type: &type requirement\nother: *type\n---\n",
            b"---\n[requirement]\n---\n",
            b"---\nnull\n---\n",
            b"---\nartifact_type: requirement\n",
            b"---\ninvalid: \xff\n---\n",
            b"---\ninvalid: \0\n---\n",
        ):
            with self.subTest(metadata=metadata):
                self.put("docs/page.md", metadata)
                code, report = self.cli("check", "--files", "AGENTS.md", "--format", "json")
                self.assertEqual(code, 2)
                self.assertIn("contract frontmatter", report["error"])
                self.assertNotIn("PRIVATE-SOURCE-MARKER", report["error"])

    def test_conditional_frontmatter_reads_bounded_header_without_decoding_body(self):
        self.bundle(max_file_bytes=128)
        self.registry(
            rules=[{"id": "title", "kind": "max-bytes", "bytes": 4096, "files": ["docs/*"]}]
        )
        self.contract(when={"frontmatter": {"artifact_type": "requirement"}})
        for newline in (b"\n", b"\r\n"):
            with self.subTest(newline=newline):
                header = newline.join([b"---", b"artifact_type: requirement", b"---", b""])
                self.put("docs/page.md", header + b"\xff\0" * 1000)
                self.put("docs/untyped.md", b"\xff\0" * 1000)
                report = run(self.root)
                self.assertEqual(report["exit_code"], 0)
                self.assertEqual(report["contracts"][0]["files"], ["docs/page.md"])
        self.put("docs/page.md", b"---\nartifact_type: " + b"x" * 128 + b"\n---\n")
        with self.assertRaisesRegex(PolicyError, "frontmatter exceeds max_file_bytes"):
            run(self.root)
        self.bundle(max_file_bytes=1)
        self.contract(when={"frontmatter": {"artifact_type": "requirement"}})
        with self.assertRaisesRegex(PolicyError, "frontmatter exceeds max_file_bytes"):
            run(self.root)

    def test_conditional_plugin_scope_does_not_weaken_global_checks(self):
        self.bundle()
        plugin = {
            "id": "metadata-tool",
            "format": "json",
            "files": ["docs/*.md"],
            "command": [
                sys.executable,
                "-c",
                "import json,sys; print(json.dumps([{'file':n,'line':1,'message':'checked'} for n in sys.argv[1:]]))",
                "{files}",
            ],
        }
        registry = self.registry(plugins=[plugin])
        self.contract(
            when={"frontmatter": {"artifact_type": "requirement"}},
            criteria=[{"id": "external", "rule": "metadata-tool"}],
        )
        self.put("docs/page.md", "---\nartifact_type: requirement\n---\n# Page\n")
        self.put("docs/note.md", "---\nartifact_type: note\n---\n# Note\n")
        report = run(self.root, allow_plugins=True)
        self.assertEqual([d["file"] for d in report["diagnostics"]], ["docs/page.md"])
        self.manifest(
            registries=[registry],
            contracts=[".repo-policy/contracts/document.yaml"],
            checks=["metadata-tool"],
        )
        report = run(self.root, allow_plugins=True)
        self.assertEqual(
            [d["file"] for d in report["diagnostics"]],
            ["docs/README.md", "docs/note.md", "docs/page.md"],
        )

    def test_overlapping_contracts_add_requirements_and_global_checks_remain_active(self):
        self.bundle()
        extra = self.registry(
            "extra",
            rules=[{"id": "ending", "kind": "required-text", "pattern": "END", "files": ["*.md"]}],
        )
        specific = self.contract(
            "specific", files=["docs/page.md"], criteria=[{"id": "ending", "rule": "ending"}]
        )
        self.manifest(
            registries=[".repo-policy/checks/docs.yaml", extra],
            contracts=[".repo-policy/contracts/document.yaml", specific],
        )
        self.put(
            "docs/README.md", "---\nrepo_policy_contracts: [document, specific]\n---\n# Docs\n"
        )
        self.put("docs/page.md", "# Page\n")
        report = run(self.root)
        self.assertEqual([c["status"] for c in report["contracts"]], ["satisfied", "failed"])
        self.assertEqual([d["rule"] for d in report["diagnostics"]], ["ending"])
        self.put("docs/page.md", "# Page\nEND\n")
        self.assertEqual(run(self.root)["exit_code"], 0)
        self.manifest(
            registries=[".repo-policy/checks/docs.yaml", extra],
            checks=["title"],
            contracts=[".repo-policy/contracts/document.yaml", specific],
        )
        self.put("elsewhere.md", "No title\n")
        self.assertEqual(run(self.root)["diagnostics"][0]["file"], "elsewhere.md")

    def test_system_ids_are_reserved_and_errors_precede_fixes_and_plugins(self):
        self.manifest(rules=[{"id": "system-policy-structure", "kind": "final-newline"}])
        path = self.put("a.txt", b"unchanged")
        with self.assertRaisesRegex(PolicyError, "system-unique-ids"):
            run(self.root, files=["a.txt"], fix=True)
        self.assertEqual(path.read_bytes(), b"unchanged")

    def test_duplicate_ids_across_registries_and_entity_types_fail(self):
        one, two = self.registry(), self.registry("other")
        self.manifest(registries=[one, two], exclude=[".repo-policy/*"])
        with self.assertRaisesRegex(PolicyError, "system-unique-ids"):
            run(self.root, files=["outside.txt"])
        (self.root / two).unlink()
        contract = self.contract("title")
        self.manifest(registries=[one], contracts=[contract])
        with self.assertRaisesRegex(PolicyError, "system-unique-ids"):
            run(self.root)

    def test_criterion_ids_are_unique_within_a_contract(self):
        self.bundle()
        self.contract(criteria=[{"id": "same", "rule": "title"}, {"id": "same", "rule": "title"}])
        with self.assertRaisesRegex(PolicyError, "system-unique-ids"):
            run(self.root)

    def test_invalid_structure_cannot_be_excluded(self):
        self.manifest(exclude=[".repo-policy/*"])
        for name in (
            ".repo-policy/readme.md",
            ".repo-policy/checks/undeclared.yaml",
            ".repo-policy/checks/deep/registry.yaml",
            ".repo-policy/scripts/check.sh",
        ):
            with self.subTest(name=name):
                path = self.put(name, "unexpected\n")
                with self.assertRaisesRegex(PolicyError, "system-policy-structure"):
                    run(self.root)
                path.unlink()
                # The flat check registry must not retain an empty nested directory either.
                if path.parent.name == "deep":
                    path.parent.rmdir()

    def test_unknown_references_and_contract_filename_mismatch_fail(self):
        self.bundle()
        self.contract(criteria=[{"id": "absent", "rule": "does-not-exist"}])
        with self.assertRaisesRegex(PolicyError, "unknown check ID"):
            run(self.root)
        self.contract(id="different")
        with self.assertRaisesRegex(PolicyError, "filename must equal"):
            run(self.root)

    def test_missing_modules_and_orphan_explanations_fail(self):
        self.manifest(registries=[".repo-policy/checks/missing.yaml"])
        with self.assertRaisesRegex(PolicyError, "system-policy-structure"):
            run(self.root)
        self.manifest()
        self.put(".repo-policy/readme/orphan.md", "# Orphan\n")
        with self.assertRaisesRegex(PolicyError, "explanation has no declared contract"):
            run(self.root)

    def test_navigation_works_without_optional_parser_and_missing_ids_fail(self):
        self.bundle()
        with patch.dict("sys.modules", {"markdown_it": None}):
            self.assertEqual(run(self.root)["exit_code"], 0)
        self.put("docs/README.md", "# Missing index\n")
        report = run(self.root, files=["docs/page.md"])
        self.assertEqual(report["diagnostics"][0]["rule"], "system-contract-navigation")
        self.assertFalse(report["diagnostics"][0]["fixable"])
        self.assertEqual(report["exit_code"], 1)

    def test_navigation_errors_run_with_empty_changed_selection(self):
        self.bundle()
        self.put("docs/README.md", "# Missing index\n")
        subprocess.run(
            ["git", "init", "-b", "main", str(self.root)], check=True, capture_output=True
        )
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True, capture_output=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=tests@example.invalid",
                "-c",
                "core.hooksPath=/dev/null",
                "commit",
                "-m",
                "fixture",
            ],
            check=True,
            capture_output=True,
        )
        report = run(self.root, mode="changed")
        self.assertEqual(report["files_checked"], [])
        self.assertEqual(report["exit_code"], 1)

    def test_bad_navigation_ids_types_and_root_location_fail(self):
        self.bundle()
        for metadata in (
            "repo_policy_contracts: [absent]",
            "repo_policy_contracts: document",
            "repo_policy_contracts: [document, document]",
            "repo_policy_contracts: [",
        ):
            with self.subTest(metadata=metadata):
                self.put("docs/README.md", f"---\n{metadata}\n---\n# Docs\n")
                self.assertEqual(run(self.root)["exit_code"], 1)
        self.put("docs/README.md", "---\nrepo_policy_contracts: [document]\n---\n# Docs\n")
        self.put("AGENTS.md", "# Missing navigation scheme\n")
        self.assertIn("repo_policy_root", run(self.root)["diagnostics"][0]["message"])

    def test_dangling_navigation_is_detected_even_with_no_contracts(self):
        self.put("README.md", "---\nrepo_policy_contracts: [gone]\n---\n# Readme\n")
        self.assertEqual(run(self.root)["exit_code"], 1)

    def test_contract_navigation_is_not_an_activation_switch(self):
        self.bundle(exclude=["docs/README.md"])
        self.put("docs/README.md", "# Index removed\n")
        self.put("docs/page.md", "No title\n")
        report = run(self.root)
        self.assertEqual(
            {d["rule"] for d in report["diagnostics"]}, {"title", "system-contract-navigation"}
        )

    def test_rubric_is_required_resource_and_pending_review_is_delegated(self):
        self.bundle()
        rubric = ".repo-policy/rubrics/quality.md"
        self.contract(criteria=[{"id": "quality", "rubric": rubric}])
        with self.assertRaisesRegex(PolicyError, "missing policy resource"):
            run(self.root)
        self.put(rubric, "# Quality\nExplain each failure and recovery action.\n")
        report = run(self.root)
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["contracts"][0]["status"], "needs_review")
        self.assertTrue(report["review_required"])
        self.assertEqual(len(report["review_requests"]), 2)
        self.assertEqual(report["diagnostics"], [])

    def test_partial_and_empty_selections_do_not_claim_artifact_acceptance(self):
        self.bundle()
        report = run(self.root, files=["docs/page.md"])
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["contracts"][0]["status"], "partial")
        report = run(self.root, files=["AGENTS.md"])
        self.assertEqual(report["contracts"][0]["status"], "not_evaluated")

    def test_explicit_ignored_artifact_is_included_in_contract_evidence(self):
        self.bundle()
        self.contract(files=["ignored.md"])
        self.put(".gitignore", "ignored.md\n")
        self.put("ignored.md", "# Explicit artifact\n")
        subprocess.run(
            ["git", "init", "-b", "main", str(self.root)], check=True, capture_output=True
        )
        report = run(self.root, files=["ignored.md"])
        contract = report["contracts"][0]
        self.assertEqual(contract["files_checked"], ["ignored.md"])
        self.assertEqual(contract["status"], "satisfied")

    def test_explain_resolves_id_and_optional_description_without_running_checks(self):
        self.bundle()
        description = ".repo-policy/readme/document.md"
        self.put(description, "# Why\nОбъяснение\n")
        code, report = self.cli("explain", "document")
        self.assertEqual(code, 0)
        self.assertEqual(report["contract_path"], ".repo-policy/contracts/document.yaml")
        self.assertEqual(report["explanation_path"], description)
        self.assertIn("Объяснение", report["explanation"])
        (self.root / description).unlink()
        self.assertNotIn("explanation_path", self.cli("explain", "document")[1])
        self.assertEqual(self.cli("explain", "title")[0], 0)
        self.assertEqual(self.cli("explain", "system-unique-ids")[0], 0)

    def test_mandatory_criterion_failure_cannot_be_hidden_by_warning_threshold(self):
        self.bundle()
        self.registry(
            rules=[
                {
                    "id": "title",
                    "kind": "required-text",
                    "pattern": "^# ",
                    "files": ["*.md"],
                    "severity": "warning",
                }
            ]
        )
        self.put("docs/page.md", "No heading\n")
        report = run(self.root)
        self.assertEqual(report["diagnostics"][0]["severity"], "warning")
        self.assertEqual(report["contracts"][0]["status"], "failed")
        self.assertEqual(report["exit_code"], 1)

    def test_contract_id_named_like_builtin_kind_remains_resolvable(self):
        self.bundle()
        contract = self.contract("syntax")
        self.manifest(
            registries=[".repo-policy/checks/docs.yaml"],
            contracts=[".repo-policy/contracts/document.yaml", contract],
        )
        code, explanation = self.cli("explain", "syntax")
        self.assertEqual(code, 0)
        self.assertEqual(explanation["configuration"]["id"], "syntax")
        self.assertEqual(explanation["description"], "Artifact acceptance contract")
        self.assertIn("syntax", self.cli("explain", "--kind", "syntax")[1])

    def test_shared_graph_check_attributes_only_relevant_target_failures(self):
        self.bundle()
        self.registry(
            rules=[
                {
                    "id": "title",
                    "kind": "markdown-reachable",
                    "files": ["*.md"],
                    "roots": ["AGENTS.md"],
                }
            ]
        )
        other = self.contract("other", files=["other/*"], entrypoints=["AGENTS.md"])
        self.manifest(
            registries=[".repo-policy/checks/docs.yaml"],
            contracts=[".repo-policy/contracts/document.yaml", other],
        )
        self.put(
            "AGENTS.md",
            "---\nrepo_policy_root: .repo-policy\n"
            "repo_policy_contracts: [other]\n---\n"
            "[Docs](docs/README.md) [Page](docs/page.md)\n",
        )
        self.put("other/orphan.md", "# Disconnected\n")
        report = run(self.root)
        self.assertEqual([c["status"] for c in report["contracts"]], ["satisfied", "failed"])

    def test_python_check_is_stored_with_policy_and_requires_explicit_trust(self):
        self.bundle()
        script = ".repo-policy/scripts/check_text.py"
        self.put(
            script,
            "import json,sys\nprint(json.dumps([{'file':sys.argv[1],"
            "'line':1,'message':'issue'}]))\nsys.exit(1)\n",
        )
        self.registry(
            rules=[{"id": "title", "kind": "required-text", "pattern": "^# "}],
            plugins=[
                {
                    "id": "custom",
                    "command": [sys.executable, script, "{files}"],
                    "format": "json",
                    "files": ["*.md"],
                }
            ],
        )
        self.contract(criteria=[{"id": "custom", "rule": "custom"}])
        self.put("outside.md", "# Outside\n")
        with self.assertRaisesRegex(PolicyError, "--allow-plugins"):
            run(self.root)
        report = run(self.root, allow_plugins=True)
        self.assertEqual(report["diagnostics"][0]["file"], "docs/README.md")
        self.assertEqual(report["contracts"][0]["status"], "failed")

    @unittest.skipUnless(os.name == "posix", "symlink privileges vary on Windows")
    def test_symlink_resources_are_never_read_or_executed(self):
        outside = self.root.parent / "outside.py"
        outside.write_text("raise RuntimeError('must not execute')\n")
        scripts = self.root / ".repo-policy/scripts"
        scripts.mkdir()
        (scripts / "check.py").symlink_to(outside)
        with self.assertRaisesRegex(PolicyError, "symlink"):
            run(self.root, allow_plugins=True)

    def test_local_and_af_reports_have_identical_schema_diagnostics_and_contract_results(self):
        self.bundle()
        self.put("docs/page.md", "No title\n")
        output = self.root.parent / "output"
        with contextlib.redirect_stdout(io.StringIO()):
            code = af_main(
                [
                    "--root",
                    str(self.root),
                    "--session-root",
                    str(self.root.parent),
                    "--output-dir",
                    str(output),
                ]
            )
        report = run(self.root)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads((output / "report.json").read_text()), report)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(
            set(report["diagnostics"][0]),
            {"file", "line", "column", "rule", "severity", "message", "fixable"},
        )

    def test_old_root_config_is_not_discovered_or_supported(self):
        (self.root / ".repo-policy/policy.yaml").unlink()
        self.put(".repo-policy.yaml", "version: 1\nrules: []\n")
        with self.assertRaises(PolicyError):
            run(self.root)
        self.put(".repo-policy/policy.yaml", "version: 1\nrules: []\n")
        with self.assertRaisesRegex(PolicyError, "version must be 2"):
            run(self.root)


if __name__ == "__main__":
    unittest.main()
