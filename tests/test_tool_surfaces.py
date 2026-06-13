from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from deal_intel import _context, mcp_server
from deal_intel.tool_surfaces import (
    build_tool_surface_matrix,
    default_surface_for_profile,
    get_tool_surface_contract,
    list_tool_surface_contracts,
    resolve_tool_surface,
    sample_local_personal_target_tool_names,
    surface_names,
    tool_names_for_config,
    tool_names_for_surface,
)


def test_tool_surface_contract_covers_registered_mcp_tools(monkeypatch) -> None:
    monkeypatch.setattr(
        _context,
        "config",
        lambda: {"tools": {"surface": "developer"}},
    )
    registered = {tool.name for tool in asyncio.run(mcp_server.app.list_tools())}
    contracted = {contract.name for contract in list_tool_surface_contracts()}

    assert registered == contracted
    assert len(contracted) == 26


def test_tool_surface_matrix_is_stable_and_serializable() -> None:
    matrix = build_tool_surface_matrix()

    assert list(matrix["surfaces"]) == ["sample", "standard", "developer"]
    assert matrix["default_surface_by_profile"] == {
        "sample": "sample",
        "full": "standard",
        "pro": "standard",
        "custom": "standard",
    }
    assert matrix["sample_local_personal_target"] == list(
        sample_local_personal_target_tool_names()
    )
    assert json.loads(json.dumps(matrix)) == matrix


def test_sample_surface_is_zero_config_safe_local_personal() -> None:
    sample_tools = set(tool_names_for_surface("sample"))

    assert sample_tools == {
        "config_doctor",
        "create_deal",
        "add_interaction",
        "update_stage",
        "update_deal",
        "archive_deal",
        "restore_deal",
        "delete_deal",
        "migrate_local_data",
        "get_deal",
        "list_deals",
        "get_metrics",
        "get_deal_gaps",
        "get_deal_review",
        "export_report",
        "get_user_memory",
        "record_user_memory",
        "get_customer_theme_breakdown",
        "get_customer_theme_evidence",
    }

    for tool_name in sample_tools:
        contract = get_tool_surface_contract(tool_name)
        assert contract.llm_calls is (tool_name == "add_interaction")
    assert {
        tool_name
        for tool_name in sample_tools
        if get_tool_surface_contract(tool_name).db_writes
    } == {
        "create_deal",
        "add_interaction",
        "update_stage",
        "update_deal",
        "archive_deal",
        "restore_deal",
        "delete_deal",
        "migrate_local_data",
    }


@pytest.mark.parametrize(
    "hidden_tool",
    [
        "create_sample_data",
        "delete_sample_data",
        "search_deals",
        "analyze_deal",
        "add_meeting",
        "get_insights",
        "get_customer_themes",
    ],
)
def test_sample_surface_hides_tools_that_break_first_run_expectations(
    hidden_tool: str,
) -> None:
    assert hidden_tool not in tool_names_for_surface("sample")


def test_sample_local_personal_target_promotes_safe_non_llm_writes() -> None:
    target_tools = set(sample_local_personal_target_tool_names())

    assert set(tool_names_for_surface("sample")).issubset(target_tools)
    assert {
        "create_deal",
        "update_stage",
        "update_deal",
        "archive_deal",
        "restore_deal",
        "delete_deal",
        "migrate_local_data",
    }.issubset(target_tools)
    assert "add_interaction" in target_tools
    assert {
        "analyze_deal",
        "search_deals",
        "add_meeting",
        "create_sample_data",
        "delete_sample_data",
    }.isdisjoint(target_tools)


def test_standard_surface_keeps_real_operator_admin_tools() -> None:
    standard_tools = set(tool_names_for_surface("standard"))

    assert {
        "create_deal",
        "add_interaction",
        "update_stage",
        "update_deal",
        "archive_deal",
        "restore_deal",
        "delete_deal",
        "migrate_local_data",
        "analyze_deal",
        "search_deals",
    }.issubset(standard_tools)
    assert "add_meeting" not in standard_tools
    assert "create_sample_data" not in standard_tools
    assert "delete_sample_data" not in standard_tools

    assert get_tool_surface_contract("delete_deal").category == "admin"
    assert get_tool_surface_contract("delete_deal").user_facing is True


def test_developer_surface_contains_everything() -> None:
    developer_tools = set(tool_names_for_surface("developer"))
    contracted = {contract.name for contract in list_tool_surface_contracts()}

    assert developer_tools == contracted
    assert {"add_meeting", "create_sample_data", "delete_sample_data"}.issubset(
        developer_tools
    )
    assert get_tool_surface_contract("add_meeting").user_facing is False


@pytest.mark.parametrize(
    ("profile", "surface"),
    [
        ("sample", "sample"),
        ("full", "standard"),
        ("pro", "standard"),
        ("custom", "standard"),
    ],
)
def test_default_surface_for_profile(profile: str, surface: str) -> None:
    assert default_surface_for_profile(profile) == surface


def test_surface_names_and_invalid_inputs_are_explicit() -> None:
    assert surface_names() == ("sample", "standard", "developer")

    with pytest.raises(ValueError, match="surface must be one of"):
        tool_names_for_surface("enterprise")

    with pytest.raises(ValueError, match="unknown MCP tool"):
        get_tool_surface_contract("missing_tool")

    with pytest.raises(ValueError, match="profile must be one of"):
        default_surface_for_profile("enterprise")

    with pytest.raises(ValueError, match="tools.surface must be"):
        resolve_tool_surface({"tools": {"surface": 3}})


def test_resolve_tool_surface_defaults_from_profile() -> None:
    assert tool_names_for_config({"storage": {"backend": "local_sample"}}) == (
        tool_names_for_surface("sample")
    )
    assert tool_names_for_config({"storage": {"backend": "mongo"}}) == (
        tool_names_for_surface("standard")
    )
    assert tool_names_for_config({"tools": {"surface": "developer"}}) == (
        tool_names_for_surface("developer")
    )


def test_mcp_runtime_filters_tools_by_surface(monkeypatch) -> None:
    monkeypatch.setattr(
        _context,
        "config",
        lambda: {"storage": {"backend": "local_sample"}, "tools": {"surface": "auto"}},
    )

    names = {tool.name for tool in asyncio.run(mcp_server.app.list_tools())}

    assert names == set(tool_names_for_surface("sample"))
    assert "create_deal" in names
    assert "add_interaction" in names
    assert "add_meeting" not in names
    assert "create_sample_data" not in names


def test_mcp_runtime_blocks_hidden_tool_calls(monkeypatch) -> None:
    from fastmcp.exceptions import NotFoundError

    monkeypatch.setattr(
        _context,
        "config",
        lambda: {"storage": {"backend": "local_sample"}, "tools": {"surface": "auto"}},
    )

    with pytest.raises(NotFoundError):
        asyncio.run(mcp_server.app.call_tool("search_deals", {}))


def test_sample_mcp_add_interaction_meeting_skips_embedding_provider(
    monkeypatch,
) -> None:
    class FakeMongo:
        def __init__(self) -> None:
            self.saved = []

        def get_deal(self, deal_id: str) -> dict:
            return {
                "deal_id": deal_id,
                "company": "Local Intake Co",
                "deal_stage": "discovery",
                "meetings": [],
            }

        def upsert_deal(self, deal: dict) -> None:
            self.saved.append(deal)

    class FakeLLM:
        def __init__(self) -> None:
            self.responses = iter([
                json.dumps(
                    {
                        "meddpicc": {
                            "identify_pain": {
                                "score": 4,
                                "evidence": "manual reporting is slow",
                            }
                        },
                        "customer_themes": [],
                    }
                ),
                "Manual reporting is slow.",
            ])

        def chat_once(self, **_kwargs):
            return SimpleNamespace(
                text=next(self.responses),
                usage={"input_tokens": 10, "output_tokens": 5},
            )

    mongo = FakeMongo()
    monkeypatch.setattr(
        _context,
        "config",
        lambda: {"storage": {"backend": "local_sample"}, "meddpicc": {"weights": {}}},
    )
    monkeypatch.setattr(_context, "storage_backend_name", lambda: "local_sample")
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "llm_provider", lambda: FakeLLM())

    def fail_if_called():
        raise AssertionError(
            "local_sample add_interaction must not initialize embeddings"
        )

    monkeypatch.setattr(_context, "embedding_provider", fail_if_called)

    result = mcp_server.add_interaction(
        deal_id="local-intake-1",
        date="2026-06-11",
        interaction_type="meeting",
        direction="inbound",
        content="Manual reporting is slow.",
    )

    assert result["ok"] is True
    assert result["embedding_stored"] is False
    assert mongo.saved[0]["meetings"] == []
    assert mongo.saved[0]["interactions"][0]["summary"] == "Manual reporting is slow."
