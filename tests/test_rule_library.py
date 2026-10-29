import json
import shutil
import unittest

import yaml
from skill_fixtures import SKILL, SkillFixture, load_helper

from repo_policy import __version__
from repo_policy.engine import run
from repo_policy.model import PolicyError

EXAMPLES = SKILL / "assets/examples"


class RuleLibraryTests(SkillFixture):
    def registry(self, name):
        content = (EXAMPLES / name).read_text()
        config = yaml.safe_load(content)
        self.put(".repo-policy/checks/example.yaml", content)
        self.put(
            ".repo-policy/policy.yaml",
            yaml.safe_dump(
                {
                    "version": 2,
                    "registries": [".repo-policy/checks/example.yaml"],
                    "checks": [rule["id"] for rule in config["rules"]],
                }
            ),
        )

    def test_library_is_not_activated_by_the_default_scaffold(self):
        self.put("README.md", "Pilot\n")
        self.put("docs/no-dates.md", "No invented metadata\n")
        self.put("specs/no-type.md", "No new schema\n")
        helper = load_helper()
        helper.configure(self.root, "repository-policy-linter==" + __version__, True)
        report = run(self.root)
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["review_requests"], [])
        self.assertEqual(
            sorted(p.name for p in (self.root / ".repo-policy/checks").iterdir()), ["common.yaml"]
        )

    def test_foundation_checks_empty_selection_and_duplicate_data_without_fixes(self):
        self.registry("foundation.yaml")
        self.put("README.md", "Pilot\n")
        raw = self.put("docs/raw/original.md", b"\xff\xfe")
        authored = self.put("docs/guide.md", b"Guide without LF")
        result = run(self.root, fix=True)
        self.assertEqual(result["exit_code"], 0)  # A warning still stays visible.
        self.assertTrue(any(d["rule"] == "example-authored-newline" for d in result["diagnostics"]))
        self.assertEqual(authored.read_bytes(), b"Guide without LF")
        self.assertEqual(raw.read_bytes(), b"\xff\xfe")
        self.put("data.yaml", "item: 1\nitem: 2\n")
        self.assertEqual(run(self.root)["exit_code"], 1)
        (self.root / "README.md").unlink()
        result = run(self.root, files=[])
        self.assertEqual(result["exit_code"], 1)
        self.assertTrue(any(d["rule"] == "example-readme" for d in result["diagnostics"]))

    def test_date_profile_preserves_values_and_keeps_native_metadata_and_originals_separate(self):
        self.registry("documentation.yaml")
        self.put("README.md", "Pilot\n")
        document = self.put(
            "docs/guide.md", "---\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\nBody\n"
        )
        native = self.put(
            ".agents/skills/native/SKILL.md",
            "---\nname: native\ndescription: Example\nmetadata:\n  created: '2026-01-01'\n  updated: '2026-01-01'\n---\nNative\n",
        )
        original = self.put("docs/raw/original.md", b"Unchanged external original")
        self.commit()
        self.assertEqual(run(self.root)["exit_code"], 0)
        document.write_text(
            document.read_text().replace("created: 2026-01-01", "created: 2026-01-02")
        )
        result = run(self.root)
        self.assertEqual(result["exit_code"], 1)
        self.assertTrue(any("previous value" in d["message"] for d in result["diagnostics"]))
        self.assertEqual(original.read_bytes(), b"Unchanged external original")
        self.assertNotIn("artifact_type", native.read_text())
        self.put("docs/new.md", "No metadata\n")
        self.assertTrue(any(d["file"] == "docs/new.md" for d in run(self.root)["diagnostics"]))

    def navigation(self):
        self.registry("navigation.yaml")
        self.put("AGENTS.md", "[Docs](docs/)\n")
        self.put("docs/README.md", "[Registry](REGISTRY.md)\n")
        self.put("docs/REGISTRY.md", "[Guide](guide.md)\n")
        self.put("docs/guide.md", "Guide\n")

    def test_navigation_directory_readme_does_not_implicitly_discover_registry(self):
        self.navigation()
        self.commit()
        self.assertEqual(run(self.root)["exit_code"], 0)
        self.put("docs/README.md", "Registry exists but is not linked\n")
        changed = run(self.root, mode="changed")
        self.assertEqual(changed["exit_code"], 1)
        self.assertIn("docs/guide.md", {d["file"] for d in changed["diagnostics"]})
        (self.root / "docs/README.md").unlink()
        self.assertEqual(run(self.root, mode="changed")["exit_code"], 1)

    def test_navigation_target_exclusion_retains_transit_but_global_exclusion_removes_it(self):
        self.navigation()
        registry = self.root / ".repo-policy/checks/example.yaml"
        config = yaml.safe_load(registry.read_text())
        config["rules"][0]["exclude"].append("docs/README.md")
        registry.write_text(yaml.safe_dump(config))
        self.assertEqual(run(self.root)["exit_code"], 0)
        manifest = self.root / ".repo-policy/policy.yaml"
        config = yaml.safe_load(manifest.read_text())
        config["exclude"] = ["docs/README.md"]
        manifest.write_text(yaml.safe_dump(config))
        self.assertEqual(run(self.root)["exit_code"], 1)

    def typed(self):
        shutil.copytree(EXAMPLES / "typed-artifacts", self.root / ".repo-policy")
        self.put(
            "AGENTS.md", "---\nrepo_policy_root: .repo-policy\n---\n[Specs](specs/README.md)\n"
        )
        self.put(
            "specs/README.md",
            "---\nrepo_policy_contracts: [example-specification]\n---\n[Contract](../.repo-policy/contracts/example-specification.yaml)\n",
        )
        self.put(
            "specs/card.md",
            "---\nartifact_type: specification\nid: example\ntitle: Sample\n---\nBody\n",
        )
        self.put(
            ".agents/skills/native/SKILL.md",
            "---\nname: native\ndescription: Example\n---\nNative instructions\n",
        )

    def test_type_guard_rejects_removed_unknown_or_non_string_tag_before_contract_selection(self):
        self.typed()
        self.assertEqual(run(self.root, allow_plugins=True)["exit_code"], 0)
        for tag in [
            "",
            "artifact_type: index\n",
            "artifact_type: 1\n",
            "artifact_type: [specification]\n",
        ]:
            with self.subTest(tag=tag):
                self.put("specs/card.md", "---\n" + tag + "id: example\ntitle: Sample\n---\nBody\n")
                report = run(self.root, allow_plugins=True)
                self.assertEqual(report["exit_code"], 1)
                self.assertTrue(
                    any(d["rule"] == "example-specification-type" for d in report["diagnostics"])
                )
                self.assertFalse(any(d["file"].endswith("SKILL.md") for d in report["diagnostics"]))

    def test_type_guard_does_not_accept_fenced_metadata_and_strict_headers_do_not_escape(self):
        self.typed()
        self.put("specs/card.md", "```yaml\nartifact_type: specification\n```\n")
        self.assertEqual(run(self.root, allow_plugins=True)["exit_code"], 1)
        for header in [
            "---\nartifact_type: specification\n",
            "---\nartifact_type: index\nartifact_type: specification\n---\n",
        ]:
            with self.subTest(header=header), self.assertRaises(PolicyError):
                self.put("specs/card.md", header)
                run(self.root, allow_plugins=True)

    def test_typed_example_uses_committed_bytes_without_git_inside_plugin_snapshot(self):
        self.typed()
        first = self.commit()
        good = run(self.root, commit=first, allow_plugins=True)
        self.assertEqual(good["exit_code"], 0)
        self.assertEqual(good["review_requests"], [])
        self.put("specs/card.md", "---\nartifact_type: index\nid: example\ntitle: Sample\n---\n")
        bad = self.commit()
        self.put(
            "specs/card.md",
            "---\nartifact_type: specification\nid: example\ntitle: Dirty repair\n---\n",
        )
        result = run(self.root, commit=bad, allow_plugins=True)
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual(json.loads(json.dumps(result))["commit"], bad)


if __name__ == "__main__":
    unittest.main()
