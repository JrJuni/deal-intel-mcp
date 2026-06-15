from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from deal_intel import _context, mcp_server
from deal_intel.errors import ErrorCode, MCPError
from deal_intel.schema.metrics import (
    CloseDateStatus,
    ExpectedCloseSettings,
    HealthBand,
    PipelineTimingSettings,
    StuckStatus,
    WinRateSettings,
    assess_pipeline_timing,
    build_attention_reasons,
    resolve_expected_close_date,
    summarize_win_rate,
)
from deal_intel.tools import create_deal, get_insights, list_deals


class FakeMongo:
    def __init__(self, deals: list[dict] | None = None) -> None:
        self.deals = deepcopy(deals or [])
        self.saved: dict | None = None

    def upsert_deal(self, deal: dict) -> None:
        self.saved = deepcopy(deal)

    def list_deals(self, *, stage: str | None = None, limit: int = 50) -> list[dict]:
        deals = [
            deepcopy(deal)
            for deal in self.deals
            if stage is None or deal.get("deal_stage") == stage
        ]
        return deals[:limit]


def _active_deal(
    *,
    stage: str = "discovery",
    entered_at: str = "2026-06-01T00:00:00+00:00",
    expected_close_date: str | None = "2026-06-20",
) -> dict:
    return {
        "deal_id": "deal-1",
        "company": "Test Co",
        "deal_stage": stage,
        "expected_close_date": expected_close_date,
        "stage_history": [{"stage": stage, "entered_at": entered_at}],
        "meddpicc_latest": {"filled_count": 1, "health_pct": 30},
        "meetings": [],
    }


def test_expected_close_defaults_to_seven_days_and_supports_industry_override() -> None:
    settings = ExpectedCloseSettings.from_config(
        {
            "pipeline": {
                "expected_close": {
                    "default_days": 7,
                    "days_by_segment": {
                        "enterprise": 21,
                    },
                    "days_by_industry": {
                        "공공": 60,
                        "대기업": 28,
                    },
                }
            }
        }
    )

    assert resolve_expected_close_date(
        provided=None,
        industry="스타트업",
        customer_segment=None,
        created_on=date(2026, 6, 8),
        settings=settings,
    ) == ("2026-06-15", "config_default")
    assert resolve_expected_close_date(
        provided=None,
        industry=" 공공 ",
        customer_segment=None,
        created_on=date(2026, 6, 8),
        settings=settings,
    ) == ("2026-08-07", "config_industry")
    assert resolve_expected_close_date(
        provided="2026-09-30",
        industry="공공",
        customer_segment="enterprise",
        created_on=date(2026, 6, 8),
        settings=settings,
    ) == ("2026-09-30", "user_provided")
    assert resolve_expected_close_date(
        provided=None,
        industry="대기업",
        customer_segment=" Enterprise ",
        created_on=date(2026, 6, 8),
        settings=settings,
    ) == ("2026-06-29", "config_segment")
    assert resolve_expected_close_date(
        provided=None,
        industry="스타트업",
        customer_segment="startup; Series B",
        created_on=date(2026, 6, 8),
        settings=ExpectedCloseSettings.from_config(
            {
                "pipeline": {
                    "expected_close": {
                        "default_days": 7,
                        "days_by_segment": {"startup": 14},
                    }
                }
            }
        ),
    ) == ("2026-06-22", "config_segment")


@pytest.mark.parametrize(
    "cfg",
    [
        {"pipeline": {"expected_close": {"default_days": -1}}},
        {"pipeline": {"expected_close": {"default_days": True}}},
        {"pipeline": {"expected_close": {"days_by_segment": []}}},
        {"pipeline": {"expected_close": {"days_by_segment": {"enterprise": "21"}}}},
        {"pipeline": {"expected_close": {"days_by_industry": []}}},
        {"pipeline": {"expected_close": {"days_by_industry": {"공공": "60"}}}},
    ],
)
def test_invalid_expected_close_config_fails_explicitly(cfg: dict) -> None:
    with pytest.raises(ValueError, match="expected_close"):
        ExpectedCloseSettings.from_config(cfg)


@pytest.mark.parametrize(
    ("factory", "cfg", "message"),
    [
        (
            PipelineTimingSettings.from_config,
            {"metrics": {"overdue": {"grace_days": -1}}},
            "grace_days",
        ),
        (
            PipelineTimingSettings.from_config,
            {"pipeline": {"stuck_threshold_days_by_stage": []}},
            "stuck_threshold",
        ),
        (
            WinRateSettings.from_config,
            {"metrics": {"win_rate": {"minimum_closed_sample": 0}}},
            "minimum_closed_sample",
        ),
        (
            WinRateSettings.from_config,
            {"metrics": {"win_rate": []}},
            "win_rate",
        ),
    ],
)
def test_invalid_part_c_config_fails_explicitly(factory, cfg: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        factory(cfg)


def test_stuck_boundary_is_inclusive_and_only_applies_to_active_deals() -> None:
    settings = PipelineTimingSettings.from_config(
        {
            "pipeline": {
                "stuck_threshold_days": 14,
                "stuck_threshold_days_by_stage": {"discovery": 7},
            }
        }
    )

    stuck = assess_pipeline_timing(
        _active_deal(entered_at="2026-06-01T23:59:00+00:00"),
        as_of=date(2026, 6, 8),
        settings=settings,
    )
    stalled = assess_pipeline_timing(
        _active_deal(stage="stalled"),
        as_of=date(2026, 6, 8),
        settings=settings,
    )

    assert stuck.days_in_stage == 7
    assert stuck.stuck_status == StuckStatus.STUCK
    assert stuck.is_stuck is True
    assert stalled.stuck_status == StuckStatus.NOT_APPLICABLE
    assert stalled.is_stuck is False


def test_missing_or_mismatched_stage_history_is_unassessed() -> None:
    settings = PipelineTimingSettings.from_config({})
    deal = _active_deal()
    deal["stage_history"] = [{"stage": "qualification", "entered_at": "2026-06-01"}]

    result = assess_pipeline_timing(
        deal,
        as_of=date(2026, 6, 8),
        settings=settings,
    )

    assert result.days_in_stage is None
    assert result.stuck_status == StuckStatus.UNASSESSED
    assert result.is_stuck is None


def test_overdue_uses_open_deal_close_date_and_configurable_grace() -> None:
    settings = PipelineTimingSettings.from_config(
        {"metrics": {"overdue": {"grace_days": 2}}}
    )

    within_grace = assess_pipeline_timing(
        _active_deal(expected_close_date="2026-06-06"),
        as_of=date(2026, 6, 8),
        settings=settings,
    )
    overdue = assess_pipeline_timing(
        _active_deal(expected_close_date="2026-06-05"),
        as_of=date(2026, 6, 8),
        settings=settings,
    )

    assert within_grace.close_date_status == CloseDateStatus.ON_TRACK
    assert within_grace.is_overdue is False
    assert overdue.close_date_status == CloseDateStatus.OVERDUE
    assert overdue.is_overdue is True
    assert overdue.overdue_days == 3


@pytest.mark.parametrize(
    ("stage", "expected_close_date", "status", "is_overdue"),
    [
        ("discovery", None, CloseDateStatus.MISSING, None),
        ("discovery", "not-a-date", CloseDateStatus.INVALID, None),
        ("won", "2026-01-01", CloseDateStatus.NOT_APPLICABLE, False),
    ],
)
def test_close_date_assessment_preserves_unknown_and_not_applicable(
    stage: str,
    expected_close_date: str | None,
    status: CloseDateStatus,
    is_overdue: bool | None,
) -> None:
    result = assess_pipeline_timing(
        _active_deal(stage=stage, expected_close_date=expected_close_date),
        as_of=date(2026, 6, 8),
        settings=PipelineTimingSettings.from_config({}),
    )

    assert result.close_date_status == status
    assert result.is_overdue is is_overdue


def test_attention_reasons_keep_distinct_risks_in_priority_order() -> None:
    timing = assess_pipeline_timing(
        _active_deal(
            entered_at="2026-05-01T00:00:00+00:00",
            expected_close_date="2026-05-30",
        ),
        as_of=date(2026, 6, 8),
        settings=PipelineTimingSettings.from_config({}),
    )

    assert build_attention_reasons(
        stage="discovery",
        health_band=HealthBand.AT_RISK,
        timing=timing,
    ) == ["overdue", "stuck", "at_risk"]


def test_win_rate_counts_only_terminal_deals_and_warns_on_small_sample() -> None:
    result = summarize_win_rate(
        [
            {"deal_stage": "won"},
            {"deal_stage": "won", "deal_size_amount": 0},
            {"deal_stage": "lost"},
            {"deal_stage": "proposal"},
        ],
        settings=WinRateSettings(minimum_closed_sample=10),
    )

    assert result["win_rate_pct"] == 66.7
    assert result["won_count"] == 2
    assert result["lost_count"] == 1
    assert result["closed_count"] == 3
    assert result["insufficient_sample"] is True
    assert result["warnings"] == ["insufficient_closed_sample"]


def test_win_rate_without_closed_deals_is_null_not_zero() -> None:
    result = summarize_win_rate(
        [{"deal_stage": "discovery"}],
        settings=WinRateSettings(minimum_closed_sample=10),
    )

    assert result["win_rate_pct"] is None
    assert result["closed_count"] == 0
    assert result["insufficient_sample"] is True


def test_period_win_rate_uses_actual_close_date_without_silent_fallback() -> None:
    result = summarize_win_rate(
        [
            {"deal_stage": "won", "actual_close_date": "2026-06-02"},
            {"deal_stage": "lost", "actual_close_date": "2026-05-30"},
            {"deal_stage": "won", "actual_close_date": None},
            {"deal_stage": "lost", "actual_close_date": "invalid"},
        ],
        settings=WinRateSettings(minimum_closed_sample=1),
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
    )

    assert result["win_rate_pct"] == 100.0
    assert result["closed_count"] == 1
    assert result["missing_actual_close_date_count"] == 1
    assert result["invalid_actual_close_date_count"] == 1
    assert result["warnings"] == [
        "missing_actual_close_date",
        "invalid_actual_close_date",
    ]


def test_create_deal_applies_default_close_date_and_records_source() -> None:
    mongo = FakeMongo()
    before = datetime.now(ZoneInfo("Asia/Seoul")).date()

    result = create_deal.handle(
        mongo=mongo,
        cfg={"pipeline": {"expected_close": {"default_days": 7}}},
        company="Test Co",
        industry="스타트업",
        deal_size_amount=None,
    )
    after = datetime.now(ZoneInfo("Asia/Seoul")).date()

    assert result["expected_close_date"] in {
        (before + timedelta(days=7)).isoformat(),
        (after + timedelta(days=7)).isoformat(),
    }
    assert result["expected_close_date_source"] == "config_default"
    assert mongo.saved is not None
    assert mongo.saved["expected_close_date"] == result["expected_close_date"]
    assert mongo.saved["expected_close_date_source"] == "config_default"
    assert mongo.saved["deal_size_amount"] is None
    assert mongo.saved["deal_size_status"] is None
    assert mongo.saved["deal_size_low_amount"] is None
    assert mongo.saved["deal_size_high_amount"] is None
    assert mongo.saved["deal_size_note"] is None
    assert mongo.saved["qualification_latest"] == {}


def test_create_deal_accepts_classified_value_range_and_note() -> None:
    mongo = FakeMongo()

    result = create_deal.handle(
        mongo=mongo,
        cfg={},
        company="Budget Co",
        industry="IT",
        deal_size_amount=40_000_000,
        deal_size_status=" rough_estimate ",
        deal_size_low_amount=30_000_000,
        deal_size_high_amount=50_000_000,
        deal_size_note="  early scope from discovery call  ",
    )

    assert result["ok"] is True
    assert result["deal_size_amount"] == 40_000_000
    assert result["deal_size_status"] == "rough_estimate"
    assert result["deal_size_low_amount"] == 30_000_000
    assert result["deal_size_high_amount"] == 50_000_000
    assert result["deal_size_note"] == "early scope from discovery call"
    assert mongo.saved is not None
    assert mongo.saved["deal_size_status"] == "rough_estimate"


def test_create_deal_accepts_strategic_zero_without_dropping_amount() -> None:
    mongo = FakeMongo()

    result = create_deal.handle(
        mongo=mongo,
        cfg={},
        company="Reference Co",
        industry="Enterprise",
        deal_size_amount=0,
        deal_size_status="strategic_zero",
        deal_size_note="reference project approved by user",
    )

    assert result["deal_size_amount"] == 0
    assert result["deal_size_status"] == "strategic_zero"
    assert mongo.saved is not None
    assert mongo.saved["deal_size_amount"] == 0
    assert mongo.saved["deal_size_status"] == "strategic_zero"


def test_create_deal_requires_confirmation_for_bare_zero_before_storage() -> None:
    mongo = FakeMongo()

    with pytest.raises(MCPError) as exc_info:
        create_deal.handle(
            mongo=mongo,
            cfg={},
            company="Ambiguous Zero Co",
            industry="IT",
            deal_size_amount=0,
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
    assert exc_info.value.stage == "preflight"
    assert exc_info.value.message == (
        "deal_size_amount=0 needs user confirmation before saving"
    )
    assert exc_info.value.hint == {
        "ask_user": (
            "이 0원은 전략적 무료/레퍼런스 딜인가요, "
            "아니면 아직 금액 미정인가요?"
        ),
        "retry_options": [
            {
                "meaning": "amount_unknown",
                "deal_size_status": "unknown",
                "deal_size_amount": None,
            },
            {
                "meaning": "strategic_zero_revenue",
                "deal_size_status": "strategic_zero",
                "deal_size_amount": 0,
            },
        ],
    }
    assert mongo.saved is None


def test_create_deal_normalizes_unknown_zero_to_missing_amount() -> None:
    mongo = FakeMongo()

    result = create_deal.handle(
        mongo=mongo,
        cfg={},
        company="Unknown Budget Co",
        industry="IT",
        deal_size_amount=0,
        deal_size_status="unknown",
        deal_size_low_amount=0,
        deal_size_high_amount=0,
    )

    assert result["deal_size_amount"] is None
    assert result["deal_size_status"] == "unknown"
    assert result["deal_size_low_amount"] is None
    assert result["deal_size_high_amount"] is None
    assert mongo.saved is not None
    assert mongo.saved["deal_size_amount"] is None
    assert mongo.saved["deal_size_status"] == "unknown"


def test_create_deal_requires_status_for_positive_amount_before_storage() -> None:
    mongo = FakeMongo()

    with pytest.raises(MCPError) as exc_info:
        create_deal.handle(
            mongo=mongo,
            cfg={},
            company="Unclassified Amount Co",
            industry="IT",
            deal_size_amount=10_000_000,
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
    assert exc_info.value.stage == "preflight"
    assert exc_info.value.message == (
        "deal_size_status is required when deal_size_amount is provided"
    )
    assert exc_info.value.hint == {
        "ask_user": (
            "이 금액은 영업 추정, 고객 예산 확인, 견적 발송 중 "
            "어떤 기준으로 저장할까요?"
        ),
        "retry_options": [
            {
                "meaning": "seller_estimate",
                "deal_size_status": "rough_estimate",
            },
            {
                "meaning": "customer_disclosed_budget",
                "deal_size_status": "customer_budget",
            },
            {
                "meaning": "formal_quote_sent",
                "deal_size_status": "quoted",
            },
        ],
    }
    assert mongo.saved is None


@pytest.mark.parametrize(
    ("kwargs", "issue"),
    [
        (
            {"deal_size_amount": None, "deal_size_status": "quoted"},
            "known_status_requires_positive_amount",
        ),
        (
            {"deal_size_amount": 1, "deal_size_status": "unknown"},
            "unknown_status_must_not_have_amount",
        ),
    ],
)
def test_create_deal_rejects_invalid_deal_value_before_storage(
    kwargs: dict,
    issue: str,
) -> None:
    mongo = FakeMongo()

    with pytest.raises(MCPError) as exc_info:
        create_deal.handle(
            mongo=mongo,
            cfg={},
            company="Invalid Co",
            industry=None,
            **kwargs,
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
    assert issue in exc_info.value.message
    assert exc_info.value.hint == {
        "valid_statuses": [
            "unknown",
            "rough_estimate",
            "customer_budget",
            "quoted",
            "strategic_zero",
        ],
        "issue": issue,
    }
    assert mongo.saved is None


def test_create_deal_rejects_invalid_user_date_as_input_error() -> None:
    with pytest.raises(MCPError) as exc_info:
        create_deal.handle(
            mongo=FakeMongo(),
            cfg={},
            company="Test Co",
            industry=None,
            deal_size_amount=None,
            expected_close_date="06/30/2026",
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT


def test_mcp_create_deal_uses_industry_override(monkeypatch) -> None:
    mongo = FakeMongo()
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(
        _context,
        "config",
        lambda: {
            "pipeline": {
                "expected_close": {
                    "default_days": 7,
                    "days_by_industry": {"Government": 60},
                }
            }
        },
    )
    before = datetime.now(ZoneInfo("Asia/Seoul")).date()

    result = mcp_server.create_deal("Public Co", industry="공공")

    assert result["ok"] is True
    assert result["industry"] == "Government"
    assert result["industry_tags"] == ["Government"]
    assert result["expected_close_date"] == (before + timedelta(days=60)).isoformat()
    assert result["expected_close_date_source"] == "config_industry"


def test_mcp_create_deal_prefers_segment_override(monkeypatch) -> None:
    mongo = FakeMongo()
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(
        _context,
        "config",
        lambda: {
            "pipeline": {
                "expected_close": {
                    "default_days": 7,
                    "days_by_segment": {"enterprise": 21},
                    "days_by_industry": {"Finance": 60},
                }
            }
        },
    )
    before = datetime.now(ZoneInfo("Asia/Seoul")).date()

    result = mcp_server.create_deal(
        "Enterprise Fintech Co",
        industry="Finance",
        customer_segment="Enterprise",
    )

    assert result["ok"] is True
    assert result["industry"] == "Finance"
    assert result["industry_tags"] == ["Finance"]
    assert result["customer_segment"] == "Enterprise"
    assert result["expected_close_date"] == (before + timedelta(days=21)).isoformat()
    assert result["expected_close_date_source"] == "config_segment"
    assert mongo.saved is not None
    assert mongo.saved["customer_segment"] == "Enterprise"


def test_mcp_create_deal_auto_classifies_mixed_industry_metadata(monkeypatch) -> None:
    mongo = FakeMongo()
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(
        _context,
        "config",
        lambda: {
            "pipeline": {
                "expected_close": {
                    "default_days": 7,
                    "days_by_segment": {"enterprise": 21},
                }
            }
        },
    )
    before = datetime.now(ZoneInfo("Asia/Seoul")).date()

    result = mcp_server.create_deal("Aurora Insurance", industry="보험·금융·대기업")

    assert result["ok"] is True
    assert result["industry"] == "Insurance"
    assert result["industry_tags"] == ["Insurance", "Finance"]
    assert result["customer_segment"] == "enterprise"
    assert result["expected_close_date"] == (before + timedelta(days=21)).isoformat()
    assert result["expected_close_date_source"] == "config_segment"
    assert result["taxonomy_warnings"][0]["code"] == "auto_classified_industry_metadata"
    assert mongo.saved is not None
    assert mongo.saved["industry"] == "Insurance"
    assert mongo.saved["industry_tags"] == ["Insurance", "Finance"]


def test_mcp_create_deal_infers_missing_industry_from_company_name(monkeypatch) -> None:
    mongo = FakeMongo()
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {})

    result = mcp_server.create_deal("Aurora Insurance")

    assert result["ok"] is True
    assert result["industry"] == "Insurance"
    assert result["industry_tags"] == ["Insurance"]
    assert result["taxonomy_warnings"][0]["code"] == "auto_classified_industry_metadata"
    assert mongo.saved is not None
    assert mongo.saved["industry"] == "Insurance"
    assert mongo.saved["industry_tags"] == ["Insurance"]


def test_mcp_create_deal_forwards_value_classification(monkeypatch) -> None:
    mongo = FakeMongo()
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {})

    result = mcp_server.create_deal(
        "Reference Co",
        industry="IT",
        deal_size_amount=0,
        deal_size_status="strategic_zero",
        deal_size_note="reference project",
    )

    assert result["ok"] is True
    assert result["deal_size_amount"] == 0
    assert result["deal_size_status"] == "strategic_zero"
    assert mongo.saved is not None
    assert mongo.saved["deal_size_amount"] == 0
    assert mongo.saved["deal_size_status"] == "strategic_zero"


def test_mcp_create_deal_returns_confirmation_for_bare_zero(monkeypatch) -> None:
    mongo = FakeMongo()
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(_context, "config", lambda: {})

    result = mcp_server.create_deal("Ambiguous Zero Co", deal_size_amount=0)

    assert result["ok"] is False
    assert result["error_code"] == ErrorCode.INVALID_INPUT
    assert result["stage"] == "preflight"
    assert result["hint"]["retry_options"] == [
        {
            "meaning": "amount_unknown",
            "deal_size_status": "unknown",
            "deal_size_amount": None,
        },
        {
            "meaning": "strategic_zero_revenue",
            "deal_size_status": "strategic_zero",
            "deal_size_amount": 0,
        },
    ]
    assert mongo.saved is None


def test_list_deals_surfaces_timing_and_attention_fields() -> None:
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    deal = _active_deal(
        entered_at=(today - timedelta(days=7)).isoformat(),
        expected_close_date=(today - timedelta(days=1)).isoformat(),
    )
    deal["industry"] = "SaaS"
    deal["industry_tags"] = ["SaaS", "Insurance"]

    result = list_deals.handle(
        mongo=FakeMongo([deal]),
        cfg={
            "pipeline": {
                "stuck_threshold_days_by_stage": {"discovery": 7},
            }
        },
        stage=None,
        limit=20,
    )

    row = result["deals"][0]
    assert row["industry_tags"] == ["SaaS", "Insurance"]
    assert row["is_stuck"] is True
    assert row["is_overdue"] is True
    assert row["attention_reasons"] == ["overdue", "stuck", "at_risk"]


def test_mcp_list_deals_surfaces_part_c_fields(monkeypatch) -> None:
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    deal = _active_deal(
        entered_at=(today - timedelta(days=7)).isoformat(),
        expected_close_date=(today - timedelta(days=1)).isoformat(),
    )
    monkeypatch.setattr(_context, "mongo", lambda: FakeMongo([deal]))
    monkeypatch.setattr(
        _context,
        "config",
        lambda: {
            "pipeline": {
                "stuck_threshold_days_by_stage": {"discovery": 7},
            }
        },
    )

    result = mcp_server.list_deals()

    assert result["ok"] is True
    assert result["deals"][0]["is_stuck"] is True
    assert result["deals"][0]["is_overdue"] is True


def test_industry_benchmark_win_rate_uses_closed_count() -> None:
    class FakeCollection:
        pipeline: list[dict] | None = None

        def aggregate(self, pipeline: list[dict]) -> list[dict]:
            self.pipeline = pipeline
            return [
                {
                    "_id": "IT",
                    "deal_count": 10,
                    "avg_health_pct": 50,
                    "won_count": 2,
                    "lost_count": 1,
                    "closed_count": 3,
                    "win_rate_pct": 66.7,
                    "amounts": [
                        {"amount": 100, "currency": "KRW"},
                    ],
                }
            ]

    col = FakeCollection()
    result = get_insights._industry_benchmark(col)

    assert result["industries"][0]["win_rate_pct"] == 66.7
    assert result["industries"][0]["closed_count"] == 3
    assert result["industries"][0]["total_size_amount"] == 100
    assert result["industries"][0]["total_size_currency"] == "KRW"
    assert result["industries"][0]["mixed_total_size_currency"] is False
    assert result["industries"][0]["insufficient_sample"] is True
    assert result["industries"][0]["warnings"] == ["insufficient_closed_sample"]
    assert col.pipeline is not None
    add_fields = next(stage["$addFields"] for stage in col.pipeline if "$addFields" in stage)
    divide = add_fields["win_rate_pct"]["$cond"][1]["$round"][0][
        "$multiply"
    ][0]["$divide"]
    assert divide == ["$won_count", "$closed_count"]


def test_industry_benchmark_does_not_sum_mixed_currencies() -> None:
    class FakeCollection:
        def aggregate(self, _pipeline: list[dict]) -> list[dict]:
            return [
                {
                    "_id": "IT",
                    "deal_count": 2,
                    "avg_health_pct": 50,
                    "won_count": 0,
                    "lost_count": 0,
                    "closed_count": 0,
                    "win_rate_pct": None,
                    "amounts": [
                        {"amount": 100, "currency": "KRW"},
                        {"amount": 20, "currency": "USD"},
                    ],
                }
            ]

    result = get_insights._industry_benchmark(FakeCollection())
    row = result["industries"][0]

    assert row["total_size_amount"] is None
    assert row["total_size_currency"] is None
    assert row["total_size_currencies"] == ["KRW", "USD"]
    assert row["mixed_total_size_currency"] is True
    assert row["total_size_by_currency"] == {"KRW": 100, "USD": 20}
