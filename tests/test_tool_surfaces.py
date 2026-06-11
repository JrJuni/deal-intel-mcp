from __future__ import annotations

import asyncio
import json

import pytest

from deal_intel import mcp_server
from deal_intel.tool_surfaces import (
    build_tool_surface_matrix,
    default_surface_for_profile,
    get_tool_surface_contract,
    list_tool_surface_contracts,
    sample_local_personal_target_tool_names,
    surface_names,
    tool_names_for_surface,
)


def test_tool_surface_contract_covers_registered_mcp_tools() -> None:
    registered = {tool.name for tool in asyncio.run(mcp_server.app.list_tools())}
    contracted = {contract.name for contract in list_tool_surface_contracts()}

    assert registered == contracted
    assert len(contracted) == 22


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


def test_sample_surface_is_zero_config_read_first() -> None:
    sample_tools = set(tool_names_for_surface("sample"))

    assert sample_tools == {
        "config_doctor",
        "get_deal",
        "list_deals",
        "get_metrics",
        "get_deal_gaps",
        "get_deal_review",
        "export_report",
        "get_customer_theme_breakdown",
        "get_customer_theme_evidence",
    }

    for tool_name in sample_tools:
        contract = get_tool_surface_contract(tool_name)
        assert contract.llm_calls is False
        assert contract.db_writes is False


@pytest.mark.parametrize(
    "hidden_tool",
    [
        "create_deal",
        "add_meeting",
        "update_stage",
        "update_deal",
        "archive_deal",
        "restore_deal",
        "delete_deal",
        "create_sample_data",
        "delete_sample_data",
        "search_deals",
        "analyze_deal",
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
    }.issubset(target_tools)
    assert {
        "add_meeting",
        "analyze_deal",
        "search_deals",
        "create_sample_data",
        "delete_sample_data",
    }.isdisjoint(target_tools)


def test_standard_surface_keeps_real_operator_admin_tools() -> None:
    standard_tools = set(tool_names_for_surface("standard"))

    assert {
        "create_deal",
        "add_meeting",
        "update_stage",
        "update_deal",
        "archive_deal",
        "restore_deal",
        "delete_deal",
        "analyze_deal",
        "search_deals",
    }.issubset(standard_tools)
    assert "create_sample_data" not in standard_tools
    assert "delete_sample_data" not in standard_tools

    assert get_tool_surface_contract("delete_deal").category == "admin"
    assert get_tool_surface_contract("delete_deal").user_facing is True


def test_developer_surface_contains_everything() -> None:
    developer_tools = set(tool_names_for_surface("developer"))
    contracted = {contract.name for contract in list_tool_surface_contracts()}

    assert developer_tools == contracted
    assert {"create_sample_data", "delete_sample_data"}.issubset(developer_tools)


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
