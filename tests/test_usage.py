from __future__ import annotations

from types import SimpleNamespace

from deal_intel.tools import add_interaction, get_usage
from deal_intel.usage import (
    build_llm_usage_metadata,
    build_usage_report,
    estimate_usage_cost,
)


class FakeLLM:
    def __init__(self) -> None:
        self.responses = iter([
            '{"meddpicc": {}, "customer_themes": []}',
            "Customer asked for a workflow review.",
        ])

    def chat_once(self, **_kwargs):
        return SimpleNamespace(
            text=next(self.responses),
            usage={"input_tokens": 100, "output_tokens": 25},
        )


class FakeMongo:
    def __init__(self, deals: list[dict]) -> None:
        self.deals = deals
        self.saved: dict | None = None

    def list_deals_for_metrics(self) -> list[dict]:
        return self.deals

    def get_deal(self, deal_id: str) -> dict | None:
        for deal in self.deals:
            if deal["deal_id"] == deal_id:
                return deal
        return None

    def upsert_deal(self, deal: dict) -> None:
        self.saved = deal
        self.deals = [deal]


def test_build_llm_usage_metadata_tracks_subscription_oauth_without_api_cost() -> None:
    metadata = build_llm_usage_metadata(
        {"llm": {"provider": "chatgpt_oauth", "chatgpt_oauth_model": "gpt-5.5"}},
        source_tool="add_interaction",
        calls=[
            {"operation": "extract_signals", "usage": {"input_tokens": 10}},
            {"operation": "summarize_interaction", "usage": {"output_tokens": 5}},
        ],
    )

    assert metadata["provider"] == "chatgpt_oauth"
    assert metadata["model"] == "gpt-5.5"
    assert metadata["totals"]["total_tokens"] == 15
    assert metadata["estimated_cost_usd"] == 0.0
    assert metadata["cost_basis"] == "chatgpt_oauth_subscription_no_incremental_api_bill"


def test_api_cost_is_estimated_only_when_pricing_is_configured() -> None:
    usage = {"input_tokens": 1_000, "output_tokens": 500}

    missing = estimate_usage_cost(
        {"usage": {"pricing": {}}},
        provider="openai_api",
        model="gpt-5.4-mini",
        usage=usage,
    )
    configured = estimate_usage_cost(
        {
            "usage": {
                "pricing": {
                    "openai_api": {
                        "gpt-5.4-mini": {
                            "input_per_1m_usd": 1.0,
                            "output_per_1m_usd": 2.0,
                        }
                    }
                }
            }
        },
        provider="openai_api",
        model="gpt-5.4-mini",
        usage=usage,
    )

    assert missing == {
        "estimated_cost_usd": None,
        "cost_basis": "pricing_not_configured",
    }
    assert configured == {
        "estimated_cost_usd": 0.002,
        "cost_basis": "configured_usage_pricing",
    }


def test_usage_report_summarizes_persisted_metadata_without_raw_content() -> None:
    metadata = build_llm_usage_metadata(
        {"llm": {"provider": "chatgpt_oauth"}},
        source_tool="add_interaction",
        calls=[{"operation": "extract_signals", "usage": {"input_tokens": 10}}],
    )
    report = build_usage_report(
        cfg={},
        deals=[
            {
                "deal_id": "deal-1",
                "company": "Acme",
                "interactions": [
                    {
                        "date": "2026-06-11",
                        "interaction_type": "meeting",
                        "raw_content": "must not appear",
                        "llm_usage": metadata,
                    }
                ],
            }
        ],
    )

    assert report["summary"]["usage_entries"] == 1
    assert report["summary"]["llm_call_count"] == 1
    assert report["summary"]["tokens"]["input_tokens"] == 10
    assert "must not appear" not in str(report)


def test_get_usage_tool_filters_dates_and_returns_empty_warning() -> None:
    metadata = build_llm_usage_metadata(
        {"llm": {"provider": "chatgpt_oauth"}},
        source_tool="add_interaction",
        calls=[{"operation": "extract_signals", "usage": {"input_tokens": 10}}],
    )
    result = get_usage.handle(
        mongo=FakeMongo([
            {
                "deal_id": "deal-1",
                "company": "Acme",
                "interactions": [{"date": "2026-06-01", "llm_usage": metadata}],
            }
        ]),
        cfg={},
        since="2026-06-10",
    )

    assert result["ok"] is True
    assert result["summary"]["usage_entries"] == 0
    assert "no_persisted_usage_metadata_found" in result["warnings"]


def test_add_interaction_persists_llm_usage_metadata() -> None:
    mongo = FakeMongo([
        {
            "deal_id": "deal-1",
            "company": "Acme",
            "deal_stage": "discovery",
            "interactions": [],
            "meetings": [],
            "customer_themes": [],
        }
    ])

    result = add_interaction.handle(
        mongo=mongo,
        llm=FakeLLM(),
        cfg={"llm": {"provider": "chatgpt_oauth"}, "meddpicc": {"weights": {}}},
        deal_id="deal-1",
        date="2026-06-11",
        interaction_type="meeting",
        direction="inbound",
        content="Customer asked for a workflow review.",
    )

    assert result["usage"] == {"input_tokens": 100, "output_tokens": 25}
    assert result["usage_summary"]["totals"]["total_tokens"] == 250
    assert mongo.saved is not None
    usage = mongo.saved["interactions"][0]["llm_usage"]
    assert usage["source_tool"] == "add_interaction"
    assert [call["operation"] for call in usage["calls"]] == [
        "extract_signals",
        "summarize_interaction",
    ]
