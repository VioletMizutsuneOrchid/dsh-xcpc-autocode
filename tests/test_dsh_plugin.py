"""DeepSeek Harness (dsh) bundle contract tests.

The dsh plugin ships as an npm package: ``package.json`` declares
``dsh.bundle.patch`` and the referenced ``cordis.patch.yml`` is the configuration
layer dsh applies when a profile lists this package.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import yaml

PACKAGE_JSON = Path("package.json")
PATCH_FILE = Path("cordis.patch.yml")
ENTRY_FILE = Path("dsh/paths.mjs")

#: Plugin rows this bundle may insert. Anything else - notably a host-side hook
#: row - would move workflow enforcement out of the MCP server.
EXPECTED_ROWS = {"autocode-paths", "autocode-mcp", "autocode-skills"}


class DshLoader(yaml.SafeLoader):
    """SafeLoader that keeps dsh ``!!js`` expressions as plain scalars."""


def _construct_js(loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node) -> Any:
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    return loader.construct_mapping(node, deep=True)


DshLoader.add_multi_constructor("tag:yaml.org,2002:js", _construct_js)


def load_package() -> dict[str, Any]:
    return json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))


def load_rows() -> dict[str, dict[str, Any]]:
    layer = yaml.load(PATCH_FILE.read_text(encoding="utf-8"), Loader=DshLoader)
    return {row["id"]: row for entry in layer for row in entry["insert"]}


def test_dsh_bundle_declares_its_patch_layer():
    """Without `dsh.bundle.patch` the package installs but never mounts."""
    package = load_package()

    assert package["dsh"]["bundle"]["patch"] == "./cordis.patch.yml"
    assert PATCH_FILE.is_file()
    assert "./cordis.patch.yml" in package["exports"].values()
    assert "cordis.patch.yml" in package["files"]


def test_dsh_bundle_entry_publishes_paths_from_its_own_location():
    """A bundle cannot know where it is installed, so the entry locates itself."""
    package = load_package()

    assert package["type"] == "module"
    assert package["main"] == "./dsh/paths.mjs"
    assert package["exports"]["."] == "./dsh/paths.mjs"
    assert ENTRY_FILE.is_file()
    assert "dsh/" in package["files"]


def test_dsh_patch_registers_the_autocode_mcp_server():
    row = load_rows()["autocode-mcp"]
    config = row["config"]

    assert row["name"] == "@deepseek-ai/dsh-mcp-client"
    # `serverName` fixes the model-facing namespace, so AutoCode tools stay
    # `mcp__autocode__*` exactly as the Claude plugin already gates on.
    assert config["serverName"] == "autocode"
    assert config["transport"] == "stdio"
    # Authoring compiles, stress tests and verifies data well past the 60s default.
    assert config["toolCallTimeoutMs"] > 60_000


def test_dsh_patch_registers_the_bundled_skills():
    row = load_rows()["autocode-skills"]

    assert row["name"] == "@deepseek-ai/dsh-skill-filesystem"
    assert row["config"]["providerName"] == "autocode"
    assert row["config"]["includeDefaultRoots"] is True
    assert Path("skills/autocode-workflow/SKILL.md").is_file()


def test_dsh_patch_resolves_paths_through_the_bundle_service():
    """Every absolute path must be read back from `ctx.autocodePaths`."""
    rows = load_rows()

    assert rows["autocode-paths"]["name"] == load_package()["name"]
    for row_id, row in rows.items():
        if row_id == "autocode-paths":
            continue
        assert row["inject"] == ["autocodePaths"]
        for value in row["config"].values():
            if isinstance(value, str) and value.startswith("ctx."):
                assert value.startswith("ctx.autocodePaths.")


def test_dsh_bundle_keeps_enforcement_inside_the_mcp_server():
    """dsh, like the Codex host, gets no hook layer: the server owns the gates."""
    assert set(load_rows()) == EXPECTED_ROWS
    assert "pre-execute" not in PATCH_FILE.read_text(encoding="utf-8")


def load_version_sync_module() -> Any:
    path = Path("scripts/sync_plugin_version.py")
    spec = importlib.util.spec_from_file_location("sync_plugin_version", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dsh_bundle_version_follows_the_single_version_source():
    """`pyproject.toml` stays authoritative for the published npm version."""
    sync = load_version_sync_module()

    assert load_package()["version"] == sync.read_pyproject_version()
