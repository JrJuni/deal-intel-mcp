from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace

from deal_intel import _context, mcp_server
from deal_intel.schema.customer_themes import (
    normalize_customer_themes,
    parse_meeting_analysis,
    rebuild_deal_customer_themes,
)
from deal_intel.tools import (
    add_interaction,
    backfill_customer_themes,
    get_customer_themes,
)


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)

    def chat_once(self, **_kwargs):
        return SimpleNamespace(
            text=next(self.responses),
            usage={"input_tokens": 10, "output_tokens": 5},
        )


class FakeMongo:
    def __init__(self, deals: list[dict] | None = None) -> None:
        self.deals = deepcopy(deals or [])
        self.saved: list[dict] = []
        self.aggregate_result: list[dict] = []
        self.count_results: list[int] = []
        self.count_queries: list[dict] = []
        self.pipeline = None

    def get_deal(self, deal_id: str):
        return next((deepcopy(d) for d in self.deals if d["deal_id"] == deal_id), None)

    def upsert_deal(self, deal: dict) -> None:
        self.saved.append(deepcopy(deal))

    def list_deals_for_theme_backfill(self, *, limit: int = 0):
        deals = deepcopy(self.deals)
        return deals[:limit] if limit > 0 else deals

    def list_deals_for_metrics(self):
        return deepcopy(self.deals)

    def count_deals(self, query: dict) -> int:
        self.count_queries.append(deepcopy(query))
        return self.count_results.pop(0)

    def aggregate_deals(self, pipeline: list[dict]) -> list[dict]:
        self.pipeline = pipeline
        return deepcopy(self.aggregate_result)


def test_normalize_customer_themes_uses_controlled_taxonomy() -> None:
    themes = normalize_customer_themes(
        [
            {
                "theme_key": "cost_reduction",
                "dimension": "metrics",
                "evidence": "운영비 20% 절감",
                "importance": 7,
            },
            {
                "theme_key": "invented_category",
                "dimension": "decision_criteria",
                "evidence": "특수 요구사항",
                "importance": "2",
            },
            {"theme_key": "cost_reduction", "dimension": "champion", "evidence": "invalid"},
        ]
    )

    assert themes == [
        {
            "theme_key": "cost_reduction",
            "label": "비용 절감",
            "dimension": "metrics",
            "evidence": "운영비 20% 절감",
            "importance": 5,
        },
        {
            "theme_key": "other",
            "label": "기타",
            "dimension": "decision_criteria",
            "evidence": "특수 요구사항",
            "importance": 2,
        },
    ]


def test_normalize_customer_themes_caps_each_meeting_at_five() -> None:
    raw = [
        {
            "theme_key": "cost_reduction",
            "dimension": "metrics",
            "evidence": f"evidence-{index}",
            "importance": 3,
        }
        for index in range(6)
    ]

    assert len(normalize_customer_themes(raw)) == 5


def test_parse_meeting_analysis_accepts_fenced_combined_json() -> None:
    text = """```json
{"meddpicc":{"decision_criteria":{"score":5,"evidence":"감사 로그 필수"}},
"customer_themes":[{"theme_key":"compliance_security","dimension":"decision_criteria",
"evidence":"감사 로그 필수","importance":5}]}
```"""

    meddpicc, themes, stage_signal = parse_meeting_analysis(text)

    assert meddpicc["decision_criteria"]["score"] == 5
    assert themes[0]["theme_key"] == "compliance_security"
    assert stage_signal is None


def test_rebuild_deal_customer_themes_flattens_meeting_provenance() -> None:
    deal = {
        "meetings": [
            {
                "meeting_id": "m1",
                "date": "2026-06-01",
                "customer_themes": [
                    {
                        "theme_key": "cost_reduction",
                        "dimension": "metrics",
                        "evidence": "비용 20% 절감",
                        "importance": 5,
                    }
                ],
            }
        ]
    }

    result = rebuild_deal_customer_themes(deal)

    assert result[0]["label"] == "비용 절감"
    assert result[0]["meeting_id"] == "m1"
    assert result[0]["meeting_date"] == "2026-06-01"


def test_add_interaction_meeting_persists_customer_themes() -> None:
    mongo = FakeMongo(
        [
            {
                "deal_id": "d1",
                "company": "테스트",
                "deal_stage": "discovery",
                "meetings": [],
            }
        ]
    )
    analysis = json.dumps(
        {
            "meddpicc": {
                "identify_pain": {"score": 4, "evidence": "수작업 보고가 오래 걸림"}
            },
            "customer_themes": [
                {
                    "theme_key": "operational_efficiency",
                    "dimension": "identify_pain",
                    "evidence": "수작업 보고가 오래 걸림",
                    "importance": 4,
                }
            ],
        },
        ensure_ascii=False,
    )
    llm = FakeLLM([analysis, "회의 요약"])

    result = add_interaction.handle(
        mongo=mongo,
        llm=llm,
        cfg={"meddpicc": {"weights": {}}},
        deal_id="d1",
        date="2026-06-08",
        interaction_type="meeting",
        direction="inbound",
        content="수작업 보고가 오래 걸린다.",
    )

    assert result["customer_themes"][0]["theme_key"] == "operational_efficiency"
    assert mongo.saved[0]["customer_themes"][0]["meeting_id"] == result["meeting_id"]
    assert mongo.saved[0]["customer_themes"][0]["interaction_id"] == result["meeting_id"]
    assert mongo.saved[0]["meetings"] == []
    assert mongo.saved[0]["interactions"][0]["summary"] == "회의 요약"
    # No closing language in the notes → no stage suggestion.
    assert result["stage_suggestion"] is None


def test_add_interaction_meeting_suggests_stage_without_changing_it() -> None:
    mongo = FakeMongo(
        [
            {
                "deal_id": "d1",
                "company": "그린로지스틱스",
                "deal_stage": "discovery",
                "meetings": [],
            }
        ]
    )
    analysis = json.dumps(
        {
            "meddpicc": {
                "decision_process": {"score": 5, "evidence": "RFP 최종 선정, PO 발행"}
            },
            "customer_themes": [],
            "stage_signal": {
                "suggested_stage": "won",
                "confidence": "high",
                "evidence": "RFP 최종 선정 통보, 계약 서명 완료",
            },
        },
        ensure_ascii=False,
    )
    llm = FakeLLM([analysis, "계약 체결"])

    result = add_interaction.handle(
        mongo=mongo,
        llm=llm,
        cfg={"meddpicc": {"weights": {}}},
        deal_id="d1",
        date="2026-06-13",
        interaction_type="meeting",
        direction="inbound",
        content="RFP 최종 선정 통보. 계약 서명 완료. CLOSED WON.",
    )

    # Suggestion is surfaced...
    assert result["stage_suggestion"] is not None
    assert result["stage_suggestion"]["suggested_stage"] == "won"
    assert result["stage_suggestion"]["current_stage"] == "discovery"
    assert result["stage_suggestion"]["confidence"] == "high"
    # ...but the stage is NOT changed automatically.
    assert mongo.saved[0]["deal_stage"] == "discovery"


def test_add_interaction_meeting_omits_suggestion_when_signal_matches_current_stage() -> None:
    mongo = FakeMongo(
        [{"deal_id": "d1", "company": "테스트", "deal_stage": "won", "meetings": []}]
    )
    analysis = json.dumps(
        {
            "meddpicc": {},
            "customer_themes": [],
            "stage_signal": {
                "suggested_stage": "won",
                "confidence": "high",
                "evidence": "이미 계약 완료",
            },
        },
        ensure_ascii=False,
    )
    llm = FakeLLM([analysis, "온보딩 진행"])

    result = add_interaction.handle(
        mongo=mongo,
        llm=llm,
        cfg={"meddpicc": {"weights": {}}},
        deal_id="d1",
        date="2026-06-13",
        interaction_type="meeting",
        direction="inbound",
        content="온보딩 진행 중.",
    )

    # Signal equals the current stage → nothing to suggest.
    assert result["stage_suggestion"] is None


def test_get_customer_themes_counts_unique_deals_and_adds_shares() -> None:
    mongo = FakeMongo(
        [
            {
                "deal_id": "d1",
                "company": "A",
                "deal_stage": "discovery",
                "customer_themes": [
                    {
                        "theme_key": "operational_efficiency",
                        "dimension": "decision_criteria",
                        "evidence": "manual reporting takes too long",
                        "importance": 5,
                    },
                    {
                        "theme_key": "operational_efficiency",
                        "dimension": "decision_criteria",
                        "evidence": "same deal second signal",
                        "importance": 4,
                    },
                ],
            },
            {
                "deal_id": "d2",
                "company": "B",
                "deal_stage": "proposal",
                "customer_themes": [
                    {
                        "theme_key": "operational_efficiency",
                        "dimension": "decision_criteria",
                        "evidence": "approval workflow is slow",
                        "importance": 4,
                    }
                ],
            },
            {
                "deal_id": "d3",
                "company": "NoThemes",
                "deal_stage": "proposal",
                "customer_themes": [],
            },
            {
                "deal_id": "d4",
                "company": "Closed",
                "deal_stage": "won",
                "customer_themes": [
                    {
                        "theme_key": "cost_reduction",
                        "dimension": "metrics",
                        "evidence": "reduce reporting cost",
                        "importance": 5,
                    }
                ],
            },
        ]
    )
    result = get_customer_themes.handle(
        mongo,
        dimension="decision_criteria",
        stage="active",
        top_k=5,
    )

    assert result["coverage"] == {
        "deals_analyzed": 3,
        "deals_with_evidence": 2,
        "coverage_pct": 66.7,
    }
    assert result["workflow"]["current_step"] == "ranking"
    assert result["workflow"]["current_tool"] == "get_customer_themes"
    assert {
        next_step["tool"] for next_step in result["workflow"]["next_tools"]
    } == {"get_customer_theme_breakdown", "get_customer_theme_evidence"}
    assert result["themes"][0]["theme_key"] == "operational_efficiency"
    assert result["themes"][0]["deal_count"] == 2
    assert result["themes"][0]["avg_importance"] == 4.5
    assert result["themes"][0]["companies"] == ["A", "B"]
    assert len(result["themes"][0]["evidence_samples"]) == 3
    assert result["themes"][0]["share_of_evidenced_pct"] == 100.0
    assert result["themes"][0]["share_of_all_deals_pct"] == 66.7


def test_get_customer_themes_industry_filter_matches_primary_or_tags() -> None:
    mongo = FakeMongo(
        [
            {
                "deal_id": "d1",
                "company": "Insurance Primary",
                "industry": "Insurance",
                "industry_tags": ["Insurance"],
                "deal_stage": "discovery",
                "customer_themes": [
                    {
                        "theme_key": "compliance_security",
                        "dimension": "decision_criteria",
                        "evidence": "audit logs required",
                        "importance": 5,
                    }
                ],
            },
            {
                "deal_id": "d2",
                "company": "Insurance Tag",
                "industry": "Finance",
                "industry_tags": ["Insurance", "Finance"],
                "deal_stage": "proposal",
                "customer_themes": [
                    {
                        "theme_key": "compliance_security",
                        "dimension": "decision_criteria",
                        "evidence": "security review",
                        "importance": 4,
                    }
                ],
            },
            {
                "deal_id": "d3",
                "company": "Retail",
                "industry": "Retail",
                "industry_tags": ["Retail"],
                "deal_stage": "proposal",
                "customer_themes": [
                    {
                        "theme_key": "operational_efficiency",
                        "dimension": "decision_criteria",
                        "evidence": "ops reporting",
                        "importance": 3,
                    }
                ],
            },
        ]
    )
    result = get_customer_themes.handle(
        mongo,
        dimension="all",
        stage="active",
        industry="Insurance",
        top_k=5,
    )

    assert result["filters"]["industry"] == "Insurance"
    assert result["coverage"]["deals_analyzed"] == 2
    assert result["themes"][0]["theme_key"] == "compliance_security"
    assert result["themes"][0]["deal_count"] == 2


def test_backfill_is_idempotent_and_rebuilds_deal_themes() -> None:
    mongo = FakeMongo(
        [
            {
                "deal_id": "d1",
                "company": "테스트",
                "meetings": [
                    {
                        "meeting_id": "m1",
                        "date": "2026-06-01",
                        "raw_notes": "감사 로그가 필수다.",
                    },
                    {
                        "meeting_id": "m2",
                        "date": "2026-06-02",
                        "raw_notes": "이미 처리됨",
                        "customer_themes": [],
                    },
                ],
            }
        ]
    )
    response = json.dumps(
        {
            "customer_themes": [
                {
                    "theme_key": "compliance_security",
                    "dimension": "decision_criteria",
                    "evidence": "감사 로그가 필수다",
                    "importance": 5,
                }
            ]
        },
        ensure_ascii=False,
    )

    result = backfill_customer_themes.handle(
        mongo,
        FakeLLM([response]),
        dry_run=False,
    )

    assert result["meetings_processed"] == 1
    assert result["meetings_skipped"] == 1
    assert result["deals_updated"] == 1
    assert result["theme_counts"] == {"compliance_security": 1}
    assert mongo.saved[0]["customer_themes"][0]["theme_key"] == "compliance_security"


def test_mcp_get_customer_themes_delegates_to_tool(monkeypatch) -> None:
    mongo = object()
    captured = {}
    monkeypatch.setattr(_context, "mongo", lambda: mongo)

    def fake_handle(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "themes": []}

    monkeypatch.setattr(get_customer_themes, "handle", fake_handle)

    result = mcp_server.get_customer_themes(
        dimension="metrics",
        stage="won",
        industry="금융",
        top_k=3,
    )

    assert result["ok"] is True
    assert captured == {
        "mongo": mongo,
        "dimension": "metrics",
        "stage": "won",
        "industry": "금융",
        "top_k": 3,
    }
