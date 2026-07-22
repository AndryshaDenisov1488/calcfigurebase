#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assert Google SA credential JSON files are absent from the project tree.

SEC-SEC-011: presence-only check — never open or parse credential contents.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent

FORBIDDEN_BASENAMES = frozenset(
    {
        "google_credentials.json",
    }
)

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        "ENV",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".tox",
        "site-packages",
    }
)


def _iter_forbidden_credential_paths(root: Path) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES]
        for filename in filenames:
            if filename in FORBIDDEN_BASENAMES:
                found.append(Path(dirpath) / filename)
            elif filename.endswith("-credentials.json"):
                found.append(Path(dirpath) / filename)
            elif filename.startswith("service-account") and filename.endswith(".json"):
                found.append(Path(dirpath) / filename)
    return found


class TestNoGoogleCredentialsInTree(unittest.TestCase):
    def test_no_google_credentials_json_in_tree(self) -> None:
        hits = _iter_forbidden_credential_paths(REPO_ROOT)
        self.assertEqual(
            hits,
            [],
            "Forbidden credential files present (paths only): "
            + ", ".join(str(path.relative_to(REPO_ROOT)) for path in hits),
        )


if __name__ == "__main__":
    unittest.main()
