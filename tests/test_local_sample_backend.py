from __future__ import annotations

import json

from deal_intel.cli import _build_natural_question_smoke_pack
from deal_intel.storage.backend import (
    SampleReadStorageBackend,
    validate_backend_capabilities,
)
from deal_intel.storage.local_sample import LocalSampleClient
from deal_intel.storage.local_sample_fixture import SENSITIVE_FIELD_NAMES
from deal_intel.tools import get_deal_review, get_metrics, list_deals


def test_local_sample_client_satisfies_read_contract() -> None:
    client = LocalSampleClient()

    assert isinstance(client, SampleReadStorageBackend)
    validate_backend_capabilities(client, kind="local_sample_mvp")
    ping = client.ping()
    assert ping["status"] == "ok"
    assert ping["storage_backend"] == "local_sample"
    assert ping["deal_count"] >= 10
    assert ping["snapshot_count"] >= 20


def test_local_sample_client_filters_and_returns_copies() -> None:
    client = LocalSampleClient()

    proposal_deals = client.list_deals(stage="proposal", limit=10)
    assert proposal_deals
    assert {deal["deal_stage"] for deal in proposal_deals} == {"proposal"}

    first_id = proposal_deals[0]["deal_id"]
    proposal_deals[0]["company"] = "mutated"

    fresh = client.get_deal(first_id)
    assert fresh is not None
    assert fresh["company"] != "mutated"


def test_local_sample_client_excludes_sensitive_fields() -> None:
    client = LocalSampleClient()

    payload = json.dumps(
        {
            "deal": client.get_deal("sample-pavebridge"),
            "deals": client.list_deals_for_metrics(),
            "snapshots": client.list_analytics_snapshots(
                start_date="2026-06-03",
                end_date="2026-06-10",
            ),
        },
        ensure_ascii=False,
    )

    for field_name in SENSITIVE_FIELD_NAMES:
        assert field_name not in payload


def test_local_sample_client_filters_analytics_snapshots() -> None:
    client = LocalSampleClient()

    snapshots = client.list_analytics_snapshots(
        start_date="2026-06-03",
        end_date="2026-06-10",
        stage="negotiation",
        industry="Fintech",
    )

    assert snapshots
    assert {snapshot["deal_stage"] for snapshot in snapshots} == {"negotiation"}
    assert {snapshot["industry"] for snapshot in snapshots} == {"Fintech"}


def test_local_sample_backend_drives_core_read_tools() -> None:
    client = LocalSampleClient()
    cfg = {
        "storage": {"backend": "local_sample"},
        "reporting": {"timezone": "Asia/Seoul"},
        "metrics": {
            "health_bands": {"healthy_min": 70, "watch_min": 40},
            "overdue": {"grace_days": 0},
            "win_rate": {"minimum_closed_sample": 10},
        },
        "pipeline": {
            "stuck_threshold_days": 14,
            "stuck_threshold_days_by_stage": {
                "discovery": 7,
                "qualification": 14,
                "proposal": 21,
                "negotiation": 30,
            },
        },
    }

    deals = list_deals.handle(
        client,
        cfg,
        stage=None,
        limit=5,
        as_of="2026-06-10",
    )
    health = get_metrics.handle(
        client,
        cfg,
        metric_type="pipeline_health",
        as_of="2026-06-10",
    )
    trend = get_metrics.handle(
        client,
        cfg,
        metric_type="pipeline_trend",
        as_of="2026-06-10",
    )
    review = get_deal_review.handle(
        client,
        cfg,
        deal_id="sample-orion-insurance",
        as_of="2026-06-10",
    )

    assert deals["ok"] is True
    assert deals["count"] == 5
    assert health["ok"] is True
    assert health["kpis"]["open_deal_count"] > 0
    assert trend["ok"] is True
    assert trend["stage_changes"]["transition_count"] > 0
    assert review["ok"] is True
    assert review["review"]["health_interpretation"]["alert_level"] == "alert"


def test_local_sample_backend_drives_natural_question_smoke_pack() -> None:
    client = LocalSampleClient()
    cfg = {"storage": {"backend": "local_sample"}, "reporting": {"timezone": "Asia/Seoul"}}

    payload = _build_natural_question_smoke_pack(
        mongo=client,
        cfg=cfg,
        as_of="2026-06-10",
    )
    q02 = next(
        question
        for question in payload["questions"]
        if question["id"] == "q02_company_status_paybridge"
    )

    assert payload["ok"] is True
    assert payload["blocked_questions"] == []
    assert payload["sensitive_failures"] == []
    assert q02["payload"]["review"]["company"] == "페이브릿지"
