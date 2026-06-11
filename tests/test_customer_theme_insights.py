from __future__ import annotations

import asyncio
import json

import pytest

import deal_intel.mcp_server as mcp_server
from deal_intel.errors import ErrorCode, MCPError, Stage
from deal_intel.schema.customer_theme_insights import (
    build_customer_theme_breakdown,
    build_customer_theme_evidence,
)
from deal_intel.tools import (
    get_customer_theme_breakdown,
    get_customer_theme_evidence,
)


class FakeMongo:
    def __init__(self, deals=None, *, fail: bool = False):
        self.deals = deals if deals is not None else _deals()
        self.fail = fail
        self.reads = 0

    def list_deals_for_metrics(self):
        self.reads += 1
        if self.fail:
            raise RuntimeError("storage down")
        return self.deals


def _theme(
    theme_key: str,
    dimension: str,
    evidence: str,
    *,
    importance: int = 4,
    meeting_date: str = "2026-06-01",
    interaction_type: str | None = None,
    source_confidence: str | None = None,
    subject: str | None = None,
) -> dict:
    theme = {
        "theme_key": theme_key,
        "label": theme_key,
        "dimension": dimension,
        "evidence": evidence,
        "importance": importance,
        "meeting_id": f"m-{theme_key}-{dimension}-{meeting_date}",
        "meeting_date": meeting_date,
    }
    if interaction_type:
        theme["interaction_id"] = f"i-{theme_key}-{dimension}-{meeting_date}"
        theme["interaction_date"] = meeting_date
        theme["interaction_type"] = interaction_type
    if source_confidence:
        theme["source_confidence"] = source_confidence
    if subject:
        theme["subject"] = subject
    return theme


def _deal(
    deal_id: str,
    company: str,
    stage: str,
    industry: str,
    themes: list[dict],
) -> dict:
    return {
        "deal_id": deal_id,
        "company": company,
        "deal_stage": stage,
        "industry": industry,
        "customer_themes": themes,
        "meetings": [{"raw_notes": "do not leak"}],
        "contacts": [{"name": "secret"}],
        "summary_embedding": [0.1, 0.2],
    }


def _deals() -> list[dict]:
    return [
        _deal(
            "d1",
            "Alpha",
            "discovery",
            "SaaS",
            [
                _theme(
                    "compliance_security",
                    "decision_criteria",
                    "security review required",
                    importance=5,
                    meeting_date="2026-06-03",
                ),
                _theme(
                    "integration_migration",
                    "decision_criteria",
                    "migration must be easy",
                    importance=4,
                    meeting_date="2026-06-02",
                ),
                _theme(
                    "reporting_visibility",
                    "identify_pain",
                    "leaders lack visibility",
                    importance=3,
                    meeting_date="2026-06-01",
                ),
            ],
        ),
        _deal(
            "d2",
            "Beta",
            "proposal",
            "Finance",
            [
                _theme(
                    "compliance_security",
                    "decision_criteria",
                    "audit log is mandatory",
                    importance=4,
                    meeting_date="2026-06-04",
                ),
                _theme(
                    "cost_reduction",
                    "metrics",
                    "reduce license spend",
                    importance=5,
                    meeting_date="2026-06-05",
                ),
            ],
        ),
        _deal(
            "d3",
            "Gamma",
            "won",
            "Finance",
            [
                _theme(
                    "compliance_security",
                    "decision_criteria",
                    "won because security passed",
                    importance=5,
                    meeting_date="2026-06-06",
                    interaction_type="user_interview",
                    source_confidence="customer_stated",
                    subject="Win review interview",
                )
            ],
        ),
        _deal("d4", "NoTheme", "proposal", "SaaS", []),
    ]


def test_customer_theme_breakdown_groups_by_stage_and_counts_unique_deals() -> None:
    result = build_customer_theme_breakdown(
        _deals(),
        dimension="decision_criteria",
        stage="active",
        group_by="stage",
        top_k=3,
    )

    assert result["summary"] == {
        "deals_analyzed": 3,
        "deals_with_evidence": 2,
        "coverage_pct": 66.7,
        "group_count": 2,
    }
    discovery = result["groups"][0]
    proposal = result["groups"][1]
    assert discovery["group_value"] == "discovery"
    assert discovery["themes"][0]["theme_key"] == "compliance_security"
    assert discovery["themes"][0]["deal_count"] == 1
    assert proposal["group_value"] == "proposal"
    assert proposal["deal_count"] == 2
    assert proposal["deals_with_evidence"] == 1
    assert proposal["themes"][0]["share_of_group_deals_pct"] == 50.0


def test_customer_theme_breakdown_groups_by_dimension() -> None:
    result = build_customer_theme_breakdown(
        _deals(),
        dimension="all",
        stage="active",
        group_by="dimension",
        top_k=2,
    )

    assert [group["group_value"] for group in result["groups"]] == [
        "identify_pain",
        "decision_criteria",
        "metrics",
    ]
    decision_group = result["groups"][1]
    assert decision_group["themes"][0]["theme_key"] == "compliance_security"
    assert decision_group["themes"][0]["deal_count"] == 2


def test_customer_theme_evidence_returns_curated_snippets_only() -> None:
    result = build_customer_theme_evidence(
        _deals(),
        theme_key="compliance_security",
        dimension="decision_criteria",
        stage="all",
        limit=2,
        min_importance=4,
    )

    assert result["summary"] == {
        "deals_analyzed": 4,
        "unique_deal_count": 3,
        "evidence_count": 3,
        "returned_count": 2,
    }
    assert [row["company"] for row in result["evidence"]] == ["Gamma", "Alpha"]
    assert result["evidence"][0]["interaction_type"] == "user_interview"
    assert result["evidence"][0]["source_confidence"] == "customer_stated"
    assert result["evidence"][0]["source_label"] == "User interview (customer-stated)"
    assert result["evidence"][0]["subject"] == "Win review interview"
    payload = json.dumps(result, ensure_ascii=False)
    assert "raw_notes" not in payload
    assert "raw_content" not in payload
    assert "contacts" not in payload
    assert "summary_embedding" not in payload
    assert "do not leak" not in payload


def test_customer_theme_evidence_filters_by_industry_and_importance() -> None:
    result = build_customer_theme_evidence(
        _deals(),
        theme_key="compliance_security",
        dimension="decision_criteria",
        stage="active",
        industry="Finance",
        min_importance=5,
    )

    assert result["summary"]["evidence_count"] == 0
    assert result["warnings"] == ["no_customer_theme_evidence"]


def test_customer_theme_evidence_filters_by_interaction_source() -> None:
    result = build_customer_theme_evidence(
        _deals(),
        theme_key="compliance_security",
        dimension="decision_criteria",
        stage="all",
        interaction_type="user_interview",
        source_confidence="customer_stated",
    )

    assert result["filters"]["interaction_type"] == "user_interview"
    assert result["filters"]["source_confidence"] == "customer_stated"
    assert result["summary"]["evidence_count"] == 1
    assert result["evidence"][0]["company"] == "Gamma"


def test_customer_theme_evidence_treats_legacy_meeting_as_meeting_source() -> None:
    result = build_customer_theme_evidence(
        _deals(),
        theme_key="compliance_security",
        dimension="decision_criteria",
        stage="all",
        interaction_type="meeting",
    )

    assert result["summary"]["evidence_count"] == 2
    assert {row["company"] for row in result["evidence"]} == {"Alpha", "Beta"}


def test_customer_theme_tools_validate_before_storage() -> None:
    mongo = FakeMongo(fail=True)

    with pytest.raises(MCPError) as invalid_group:
        get_customer_theme_breakdown.handle(mongo, group_by="company")
    assert invalid_group.value.error_code == ErrorCode.INVALID_INPUT
    assert invalid_group.value.stage == Stage.PREFLIGHT
    assert mongo.reads == 0

    with pytest.raises(MCPError) as invalid_theme:
        get_customer_theme_evidence.handle(mongo, theme_key="made_up")
    assert invalid_theme.value.error_code == ErrorCode.INVALID_INPUT
    assert invalid_theme.value.stage == Stage.PREFLIGHT
    assert mongo.reads == 0

    with pytest.raises(MCPError) as invalid_interaction:
        get_customer_theme_evidence.handle(
            mongo,
            theme_key="compliance_security",
            interaction_type="fax",
        )
    assert invalid_interaction.value.error_code == ErrorCode.INVALID_INPUT
    assert invalid_interaction.value.stage == Stage.PREFLIGHT
    assert mongo.reads == 0

    with pytest.raises(MCPError) as invalid_confidence:
        get_customer_theme_evidence.handle(
            mongo,
            theme_key="compliance_security",
            source_confidence="certain",
        )
    assert invalid_confidence.value.error_code == ErrorCode.INVALID_INPUT
    assert invalid_confidence.value.stage == Stage.PREFLIGHT
    assert mongo.reads == 0


def test_customer_theme_tools_return_storage_errors() -> None:
    mongo = FakeMongo(fail=True)

    with pytest.raises(MCPError) as exc_info:
        get_customer_theme_breakdown.handle(mongo, group_by="stage")

    assert exc_info.value.error_code == ErrorCode.STORAGE_ERROR
    assert exc_info.value.stage == Stage.STORAGE
    assert exc_info.value.retryable is True


def test_customer_theme_tool_handlers_return_expected_shape() -> None:
    breakdown = get_customer_theme_breakdown.handle(
        FakeMongo(),
        dimension="decision_criteria",
        group_by="industry",
        top_k=2,
    )
    evidence = get_customer_theme_evidence.handle(
        FakeMongo(),
        theme_key="compliance_security",
        stage="active",
        limit=3,
        interaction_type="meeting",
    )

    assert breakdown["ok"] is True
    assert breakdown["filters"]["group_by"] == "industry"
    assert breakdown["groups"]
    assert evidence["ok"] is True
    assert evidence["summary"]["returned_count"] == 2
    assert evidence["filters"]["interaction_type"] == "meeting"


def test_mcp_runtime_registers_customer_theme_expansion_tools() -> None:
    tools = asyncio.run(mcp_server.app.list_tools())
    names = sorted(tool.name for tool in tools)

    assert {"get_customer_theme_breakdown", "get_customer_theme_evidence"}.issubset(
        names
    )
