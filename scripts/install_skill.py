#!/usr/bin/env python3
"""Install only the skill, preserving any different existing destination."""

import argparse
import hashlib
import shutil
from pathlib import Path


def install(source, destination):
    source, destination = Path(source), Path(destination).expanduser().absolute()
    for path in [destination, *destination.parents]:
        if path.is_symlink():
            raise ValueError(f"refusing symlink destination: {path}")
    if destination.exists():

        def snapshot(directory):
            result = {}
            for item in directory.rglob("*"):
                if item.is_symlink():
                    raise ValueError("skill destination contains a symlink")
                if item.is_file() and "__pycache__" not in item.parts:
                    result[item.relative_to(directory).as_posix()] = hashlib.sha256(
                        item.read_bytes()
                    ).hexdigest()
            return result

        if snapshot(source) != snapshot(destination):
            raise ValueError(
                "different skill already installed; review differences before upgrading"
            )
        return "Already installed (identical)"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return f"Installed skill: {destination}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--destination", required=True, help="explicit skill folder, not its parent"
    )
    args = parser.parse_args()
    try:
        print(
            install(
                Path(__file__).resolve().parents[1] / "skills/repo-policy-setup", args.destination
            )
        )
    except (ValueError, OSError) as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    main()
