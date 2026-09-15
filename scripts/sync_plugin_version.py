#!/usr/bin/env python3
"""Sync the plugin / package version from ``pyproject.toml`` (single source).

``pyproject.toml`` is the authoritative version. This script propagates it to:

- ``.claude-plugin/plugin.json``  -> ``version``
- ``.codex-plugin/plugin.json``   -> ``version``
- ``package.json``                -> ``version`` (DeepSeek Harness bundle)
- ``src/autocode_mcp/__init__.py`` -> ``__version__`` (single line literal)

Run it on release / build so the four never drift; ``--check`` reports drift
instead of rewriting. No external deps beyond the standard library.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # Python 3.10 (project floor) has no tomllib
    tomllib = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
CODEX_PLUGIN_JSON = REPO_ROOT / ".codex-plugin" / "plugin.json"
PACKAGE_JSON = REPO_ROOT / "package.json"
INIT_PY = REPO_ROOT / "src" / "autocode_mcp" / "__init__.py"


def read_pyproject_version() -> str:
    if not PYPROJECT.is_file():
        raise SystemExit(f"pyproject.toml not found at {PYPROJECT}")
    text = PYPROJECT.read_text(encoding="utf-8")
    if tomllib is not None:
        version = tomllib.loads(text).get("project", {}).get("version")
    else:  # stdlib-only fallback for Python 3.10
        match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
        version = match.group(1) if match else None
    if not version:
        raise SystemExit("version missing under [project] in pyproject.toml")
    return str(version)


def write_plugin_json(version: str) -> None:
    if not PLUGIN_JSON.is_file():
        raise SystemExit(f"plugin.json not found at {PLUGIN_JSON}")
    plugin = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    old = plugin.get("version")
    plugin["version"] = version
    PLUGIN_JSON.write_text(json.dumps(plugin, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f".claude-plugin/plugin.json: {old} -> {version}")


def write_codex_plugin_json(version: str) -> None:
    if not CODEX_PLUGIN_JSON.exists():
        raise SystemExit(f"Codex plugin manifest not found at {CODEX_PLUGIN_JSON}")
    plugin = json.loads(CODEX_PLUGIN_JSON.read_text(encoding="utf-8"))
    old = plugin.get("version")
    plugin["version"] = version
    CODEX_PLUGIN_JSON.write_text(
        json.dumps(plugin, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f".codex-plugin/plugin.json: {old} -> {version}")


def write_package_json(version: str) -> None:
    if not PACKAGE_JSON.is_file():
        raise SystemExit(f"package.json not found at {PACKAGE_JSON}")
    package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    old = package.get("version")
    package["version"] = version
    PACKAGE_JSON.write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"package.json: {old} -> {version}")


def write_init_version(version: str) -> None:
    if not INIT_PY.is_file():
        raise SystemExit(f"__init__.py not found at {INIT_PY}")
    text = INIT_PY.read_text(encoding="utf-8")
    pattern = re.compile(r'^__version__\s*=\s*["\'][^"\']*["\']', re.MULTILINE)
    if not pattern.search(text):
        raise SystemExit("__version__ assignment not found in __init__.py")
    new_text, count = pattern.subn(f'__version__ = "{version}"', text)
    if count != 1:
        raise SystemExit(f"expected exactly one __version__ assignment, found {count}")
    INIT_PY.write_text(new_text, encoding="utf-8")
    print(f"__init__.py: __version__ -> {version}")


def read_manifest_version(path: Path) -> str | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("version")


def read_init_version() -> str | None:
    if not INIT_PY.is_file():
        return None
    match = re.search(
        r'^__version__\s*=\s*["\']([^"\']+)["\']',
        INIT_PY.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    return match.group(1) if match else None


def check_sync(version: str) -> list[str]:
    """Report every target that drifted from the authoritative version."""
    targets = (
        (".claude-plugin/plugin.json", read_manifest_version(PLUGIN_JSON)),
        (".codex-plugin/plugin.json", read_manifest_version(CODEX_PLUGIN_JSON)),
        ("package.json", read_manifest_version(PACKAGE_JSON)),
        ("src/autocode_mcp/__init__.py", read_init_version()),
    )
    return [
        f"{name}: {found!r} != {version!r} (pyproject.toml)"
        for name, found in targets
        if found != version
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync plugin versions from pyproject.toml")
    parser.add_argument(
        "--check",
        action="store_true",
        help="report version drift and exit non-zero instead of rewriting files",
    )
    args = parser.parse_args(argv)
    version = read_pyproject_version()
    if args.check:
        drift = check_sync(version)
        if drift:
            for line in drift:
                print(f"ERROR: {line}")
            print("Run scripts/sync_plugin_version.py to re-sync.")
            return 1
        print(f"All version targets are in sync at {version}")
        return 0
    write_plugin_json(version)
    write_codex_plugin_json(version)
    write_package_json(version)
    write_init_version(version)
    print(f"Synced version {version} from pyproject.toml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
