from __future__ import annotations

import builtins
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

from deal_intel.tool_surfaces import list_tool_surface_contracts

ROOT = Path(__file__).resolve().parents[1]
MCPB_DIR = ROOT / "mcpb"
MANIFEST_PATH = MCPB_DIR / "manifest.json"
LAUNCHER_PATH = MCPB_DIR / "server" / "launcher.py"


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _launcher_module():
    spec = importlib.util.spec_from_file_location("deal_intel_mcpb_launcher", LAUNCHER_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_mcpb_manifest_tools_match_registered_surface_contracts() -> None:
    manifest = _manifest()
    manifest_tool_names = [tool["name"] for tool in manifest["tools"]]
    contract_tool_names = [contract.name for contract in list_tool_surface_contracts()]

    assert manifest_tool_names == contract_tool_names
    assert len(manifest_tool_names) == 23


def test_mcpb_manifest_user_config_is_sample_first_and_secret_safe() -> None:
    manifest = _manifest()
    user_config = manifest["user_config"]

    assert manifest["version"] == "0.1.10"
    assert user_config["python_path"]["required"] is True
    assert user_config["storage_backend"]["default"] == "local_sample"
    assert user_config["storage_backend"]["required"] is False
    assert user_config["tools_surface"]["default"] == "auto"
    assert user_config["mongodb_uri"]["required"] is False
    assert user_config["mongodb_uri"]["sensitive"] is True
    assert user_config["llm_provider"]["default"] == "chatgpt_oauth"
    assert user_config["anthropic_api_key"]["sensitive"] is True
    assert user_config["openai_api_key"]["sensitive"] is True


def test_mcpb_manifest_launches_installed_python_module_without_shell_wrapper() -> None:
    server = _manifest()["server"]
    mcp_config = server["mcp_config"]

    assert server["type"] == "python"
    assert server["entry_point"] == "server/launcher.py"
    assert mcp_config["command"] == "${user_config.python_path}"
    assert mcp_config["args"] == ["-m", "deal_intel.mcp_server"]
    assert "cmd.exe" not in json.dumps(mcp_config, ensure_ascii=False).lower()
    assert "powershell" not in json.dumps(mcp_config, ensure_ascii=False).lower()


def test_mcpb_manifest_env_maps_installer_fields_to_runtime_config() -> None:
    env = _manifest()["server"]["mcp_config"]["env"]

    assert env["MONGODB_URI"] == "${user_config.mongodb_uri}"
    assert env["DEAL_INTEL_STORAGE_BACKEND"] == "${user_config.storage_backend}"
    assert env["DEAL_INTEL_TOOLS_SURFACE"] == "${user_config.tools_surface}"
    assert env["DEAL_INTEL_LLM_PROVIDER"] == "${user_config.llm_provider}"
    assert env["DEAL_INTEL_USE_CHATGPT_OAUTH"] == "${user_config.use_chatgpt_oauth}"
    assert env["ANTHROPIC_API_KEY"] == "${user_config.anthropic_api_key}"
    assert env["OPENAI_API_KEY"] == "${user_config.openai_api_key}"
    assert env["PYTHONIOENCODING"] == "utf-8"


def test_mcpb_launcher_delegates_to_installed_mcp_server(monkeypatch) -> None:
    launcher = _launcher_module()
    called: list[bool] = []
    fake_mcp_server = types.ModuleType("deal_intel.mcp_server")
    fake_mcp_server.main = lambda: called.append(True)

    monkeypatch.setitem(sys.modules, "deal_intel.mcp_server", fake_mcp_server)

    launcher.main()

    assert called == [True]


def test_mcpb_launcher_failure_message_points_to_editable_install(
    monkeypatch,
    capsys,
) -> None:
    launcher = _launcher_module()
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "deal_intel.mcp_server":
            raise ImportError("missing test module")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.delitem(sys.modules, "deal_intel.mcp_server", raising=False)
    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(SystemExit) as exc_info:
        launcher.main()

    stderr = capsys.readouterr().err
    assert exc_info.value.code == 1
    assert "cannot import deal_intel.mcp_server" in stderr
    assert "pip install -e ." in stderr
