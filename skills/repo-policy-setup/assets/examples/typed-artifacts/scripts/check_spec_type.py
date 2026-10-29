"""Optional example: validate classification independently of conditional contracts."""

import json
import sys
from pathlib import Path

import yaml

from repo_policy.files import safe_path
from repo_policy.history import frontmatter_values
from repo_policy.model import PolicyError

LIMIT = 1_048_576


def check(root, names):
    issues = []
    for name in names:
        try:
            with safe_path(root, name).open("rb") as stream:
                raw = stream.read(LIMIT + 1)
            if len(raw) > LIMIT:
                raise ValueError("input too large")
            metadata = frontmatter_values(raw, [])
            valid = metadata.get("artifact_type") == "specification"
            message = "specification path requires artifact_type: specification"
        except (OSError, UnicodeError, ValueError, RecursionError, yaml.YAMLError, PolicyError):
            valid = False
            message = "cannot read bounded, safe UTF-8 frontmatter"
        if not valid:
            issues.append({"file": name, "line": 1, "code": "artifact-type", "message": message})
    return issues


if __name__ == "__main__":
    diagnostics = check(Path.cwd(), sys.argv[1:])
    print(json.dumps(diagnostics))
    raise SystemExit(1 if diagnostics else 0)
