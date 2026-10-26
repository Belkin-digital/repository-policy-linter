"""Check that standalone setup assets agree with the installed engine's starter bundle."""

import json
import sys
from pathlib import Path

import yaml

from repo_policy.config import DEFAULT_CONFIG, DEFAULT_REGISTRY

EXPECTED = {
    "skills/repo-policy-setup/assets/policy/policy.yaml": DEFAULT_CONFIG,
    "skills/repo-policy-setup/assets/policy/checks/common.yaml": DEFAULT_REGISTRY,
}


def main():
    diagnostics = []
    for argument in sys.argv[1:]:
        name = Path(argument).as_posix().removeprefix("./")
        if name not in EXPECTED:
            continue
        try:
            matches = yaml.safe_load(Path(name).read_text()) == yaml.safe_load(EXPECTED[name])
        except (OSError, ValueError, yaml.YAMLError):
            matches = False
        if not matches:
            diagnostics.append(
                {
                    "file": name,
                    "line": 1,
                    "message": "Setup asset differs from the engine's starter bundle",
                }
            )
    print(json.dumps(diagnostics))
    return 1 if diagnostics else 0


if __name__ == "__main__":
    raise SystemExit(main())
