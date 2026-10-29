"""Disposable repositories for bootstrap and shipped-example verification."""

import importlib.util
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
SKILL = PROJECT / "skills/repo-policy-setup"


def load_helper():
    spec = importlib.util.spec_from_file_location(
        "setup_under_test", SKILL / "scripts/configure.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SkillFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="repo-policy-skill-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "repo"
        self.root.mkdir()
        environment = dict(os.environ)
        for key in list(environment):
            if key in {
                "GIT_DIR",
                "GIT_WORK_TREE",
                "GIT_INDEX_FILE",
                "GIT_COMMON_DIR",
                "GIT_OBJECT_DIRECTORY",
                "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            } or key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
                environment.pop(key)
        environment.update(
            GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_COUNT="0"
        )
        isolated = patch.dict(os.environ, environment, clear=True)
        isolated.start()
        self.addCleanup(isolated.stop)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.git("config", "commit.gpgsign", "false")
        hooks = self.root.parent / "empty-hooks"
        hooks.mkdir()
        self.git("config", "core.hooksPath", str(hooks))

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-C", str(self.root), *args], stderr=subprocess.STDOUT
        )

    def commit(self):
        self.git("add", "--all")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD").decode().strip()

    def put(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode() if isinstance(content, str) else content)
        return path

    def snapshot(self):
        result = {}
        for path in self.root.rglob("*"):
            name = path.relative_to(self.root)
            if ".git" in name.parts:
                continue
            if path.is_symlink():
                result[name.as_posix()] = ("symlink", os.readlink(path))
            elif path.is_file():
                result[name.as_posix()] = (
                    "file",
                    stat.S_IMODE(path.stat().st_mode),
                    path.read_bytes(),
                )
        return result
