from __future__ import annotations

import json

import pytest

from deal_intel.cli import _build_natural_question_smoke_pack
from deal_intel.errors import ErrorCode, MCPError
from deal_intel.storage.backend import (
    SampleReadStorageBackend,
    validate_backend_capabilities,
)
from deal_intel.storage.local_personal import (
    LOCAL_PERSONAL_DEALS_FILE,
    LOCAL_PERSONAL_DELETE_AUDIT_FILE,
    LocalPersonalStore,
    resolve_local_data_dir,
)
from deal_intel.storage.local_sample import LocalSampleClient
from deal_intel.storage.local_sample_fixture import SENSITIVE_FIELD_NAMES
from deal_intel.tools import (
    add_meeting,
    archive_deal,
    create_deal,
    delete_deal,
    get_deal_review,
    get_metrics,
    list_deals,
    restore_deal,
    update_deal,
    update_stage,
)


def _local_cfg(tmp_path) -> dict:
    return {
        "storage": {
            "backend": "local_sample",
            "local_data_dir": str(tmp_path),
        },
        "reporting": {"timezone": "Asia/Seoul"},
        "pipeline": {
            "expected_close": {"default_days": 7},
            "stuck_threshold_days": 14,
            "stuck_threshold_days_by_stage": {
                "discovery": 7,
                "qualification": 14,
                "proposal": 21,
                "negotiation": 30,
            },
        },
        "metrics": {
            "health_bands": {"healthy_min": 70, "watch_min": 40},
            "overdue": {"grace_days": 0},
            "win_rate": {"minimum_closed_sample": 10},
        },
    }


def _local_deal(**overrides) -> dict:
    deal = {
        "deal_id": "local-life-1",
        "company": "Local Lifecycle Co",
        "industry": "Trial",
        "deal_stage": "discovery",
        "deal_size_krw": 1_000_000,
        "deal_size_status": "rough_estimate",
        "expected_close_date": "2026-06-30",
        "stage_history": [
            {
                "stage": "discovery",
                "entered_at": "2026-06-10T00:00:00+00:00",
            }
        ],
        "meetings": [
            {
                "meeting_id": "meeting-1",
                "summary": "safe summary",
                "raw_notes": "private raw notes",
            }
        ],
        "contacts": [{"email": "private@example.com"}],
        "summary_embedding": [0.1, 0.2],
        "updated_at": "2026-06-10T00:00:00+00:00",
    }
    deal.update(overrides)
    return deal


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


def test_local_sample_missing_personal_file_keeps_fixture_active(tmp_path) -> None:
    client = LocalSampleClient(local_data_dir=tmp_path)
    ping = client.ping()

    assert ping["data_mode"] == "fixture"
    assert ping["fixture_archived"] is False
    assert ping["local_deal_count"] == 0
    assert client.get_deal("sample-pavebridge") is not None


def test_local_sample_empty_personal_file_keeps_fixture_archived(tmp_path) -> None:
    (tmp_path / LOCAL_PERSONAL_DEALS_FILE).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "dataset": "local_personal",
                "deals": [],
            }
        ),
        encoding="utf-8",
    )

    client = LocalSampleClient(local_data_dir=tmp_path)
    ping = client.ping()

    assert ping["data_mode"] == "local_personal"
    assert ping["fixture_archived"] is True
    assert ping["deal_count"] == 0
    assert ping["local_deal_count"] == 0
    assert client.get_deal("sample-pavebridge") is None
    assert client.list_deals_for_metrics() == []


def test_local_personal_deals_replace_fixture_in_active_reads(tmp_path) -> None:
    (tmp_path / LOCAL_PERSONAL_DEALS_FILE).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "dataset": "local_personal",
                "deals": [
                    {
                        "deal_id": "local-deal-1",
                        "company": "Local Trial Co",
                        "industry": "Trial",
                        "deal_stage": "discovery",
                        "deal_size_krw": 1_000_000,
                        "deal_size_status": "rough_estimate",
                        "expected_close_date": "2026-06-30",
                        "meddpicc_latest": {"health_pct": 42, "gaps": []},
                        "stage_history": [
                            {
                                "stage": "discovery",
                                "entered_at": "2026-06-10T00:00:00+00:00",
                            }
                        ],
                        "meetings": [{"raw_notes": "sensitive local note"}],
                        "contacts": [{"email": "private@example.com"}],
                        "summary_embedding": [0.1, 0.2],
                        "updated_at": "2026-06-10T00:00:00+00:00",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    client = LocalSampleClient(local_data_dir=tmp_path)
    ping = client.ping()
    payload = json.dumps(
        {
            "deal": client.get_deal("local-deal-1"),
            "fixture_deal": client.get_deal("sample-pavebridge"),
            "deals": client.list_deals_for_metrics(),
            "snapshots": client.list_analytics_snapshots(
                start_date="2026-06-03",
                end_date="2026-06-10",
            ),
        },
        ensure_ascii=False,
    )

    assert ping["data_mode"] == "local_personal"
    assert ping["fixture_archived"] is True
    assert ping["deal_count"] == 1
    assert ping["snapshot_count"] == 0
    assert ping["local_deal_count"] == 1
    assert client.get_deal("sample-pavebridge") is None
    assert client.list_deals_for_metrics()[0]["company"] == "Local Trial Co"
    assert client.list_analytics_snapshots(
        start_date="2026-06-03",
        end_date="2026-06-10",
    ) == []
    for field_name in SENSITIVE_FIELD_NAMES:
        assert field_name not in payload


def test_local_personal_store_rejects_duplicate_deal_ids(tmp_path) -> None:
    (tmp_path / LOCAL_PERSONAL_DEALS_FILE).write_text(
        json.dumps(
            {
                "deals": [
                    {"deal_id": "dup", "company": "One"},
                    {"deal_id": "dup", "company": "Two"},
                ]
            }
        ),
        encoding="utf-8",
    )

    store = LocalPersonalStore(tmp_path)

    try:
        store.load_deals()
    except ValueError as exc:
        assert "duplicate local personal deal_id" in str(exc)
    else:
        raise AssertionError("duplicate deal ids should fail local personal load")


def test_resolve_local_data_dir_default_and_custom(tmp_path) -> None:
    assert str(resolve_local_data_dir()).endswith(".deal-intel\\local-data") or str(
        resolve_local_data_dir()
    ).endswith(".deal-intel/local-data")
    assert resolve_local_data_dir(tmp_path) == tmp_path


def test_local_sample_upsert_persists_user_deal_and_hides_fixture(tmp_path) -> None:
    client = LocalSampleClient(local_data_dir=tmp_path)

    client.upsert_deal(
        {
            "deal_id": "local-upsert-1",
            "company": "Local Upsert Co",
            "deal_stage": "discovery",
            "updated_at": "2026-06-10T00:00:00+00:00",
            "meetings": [{"raw_notes": "private local notes"}],
            "contacts": [{"email": "private@example.com"}],
            "summary_embedding": [0.1, 0.2],
        }
    )

    fresh = LocalSampleClient(local_data_dir=tmp_path)
    payload = json.dumps(
        {
            "deal": fresh.get_deal("local-upsert-1"),
            "deals": fresh.list_deals_for_metrics(),
            "raw_file": (tmp_path / LOCAL_PERSONAL_DEALS_FILE).read_text(
                encoding="utf-8"
            ),
        },
        ensure_ascii=False,
    )

    assert fresh.ping()["data_mode"] == "local_personal"
    assert fresh.get_deal("sample-pavebridge") is None
    assert fresh.get_deal("local-upsert-1")["company"] == "Local Upsert Co"
    for field_name in SENSITIVE_FIELD_NAMES:
        assert field_name not in payload


def test_local_personal_safe_write_tools_persist_across_clients(tmp_path) -> None:
    cfg = _local_cfg(tmp_path)
    client = LocalSampleClient(local_data_dir=tmp_path)

    created = create_deal.handle(
        mongo=client,
        cfg=cfg,
        company="Local Write Co",
        industry="Trial",
        deal_size_krw=12_000_000,
        deal_size_status="rough_estimate",
        deal_size_note="user confirmed local test amount",
    )
    deal_id = created["deal_id"]

    after_create = LocalSampleClient(local_data_dir=tmp_path)
    assert after_create.get_deal(deal_id)["company"] == "Local Write Co"
    assert after_create.get_deal("sample-pavebridge") is None

    stage_result = update_stage.handle(
        mongo=after_create,
        cfg=cfg,
        deal_id=deal_id,
        new_stage="proposal",
    )
    assert stage_result["ok"] is True

    after_stage = LocalSampleClient(local_data_dir=tmp_path)
    assert after_stage.get_deal(deal_id)["deal_stage"] == "proposal"

    value_result = update_deal.handle(
        mongo=after_stage,
        deal_id=deal_id,
        deal_size_status="quoted",
        deal_size_krw=15_000_000,
        deal_size_note="user confirmed quote sent",
        confirmed_by_user=True,
    )
    assert value_result["storage_written"] is True

    after_update = LocalSampleClient(local_data_dir=tmp_path)
    deal = after_update.get_deal(deal_id)
    assert deal["deal_stage"] == "proposal"
    assert deal["deal_size_status"] == "quoted"
    assert deal["deal_size_krw"] == 15_000_000
    assert deal["deal_value_history"][-1]["source"] == "update_deal"


def test_local_personal_add_meeting_persists_canonical_raw_content(
    tmp_path,
) -> None:
    from types import SimpleNamespace

    class FakeLLM:
        def __init__(self) -> None:
            self.responses = iter([
                json.dumps(
                    {
                        "meddpicc": {
                            "identify_pain": {
                                "score": 4,
                                "evidence": "manual reporting takes too long",
                            }
                        },
                        "customer_themes": [
                            {
                                "theme_key": "operational_efficiency",
                                "dimension": "identify_pain",
                                "evidence": "manual reporting takes too long",
                                "importance": 4,
                            }
                        ],
                    }
                ),
                "The customer said manual reporting takes too long.",
            ])

        def chat_once(self, **_kwargs):
            return SimpleNamespace(
                text=next(self.responses),
                usage={"input_tokens": 10, "output_tokens": 5},
            )

    cfg = _local_cfg(tmp_path)
    client = LocalSampleClient(local_data_dir=tmp_path)
    created = create_deal.handle(
        mongo=client,
        cfg=cfg,
        company="Local Intake Co",
        industry="Trial",
        deal_size_krw=None,
        deal_size_status="unknown",
    )

    result = add_meeting.handle(
        mongo=LocalSampleClient(local_data_dir=tmp_path),
        llm=FakeLLM(),
        cfg=cfg,
        embedding_provider=None,
        deal_id=created["deal_id"],
        date="2026-06-11",
        raw_notes="private raw note sentinel: manual reporting takes too long",
    )

    after_meeting = LocalSampleClient(local_data_dir=tmp_path)
    deal = after_meeting.get_deal(created["deal_id"])
    serialized = json.dumps(
        {
            "deal": deal,
            "raw_file": (tmp_path / LOCAL_PERSONAL_DEALS_FILE).read_text(
                encoding="utf-8"
            ),
        },
        ensure_ascii=False,
    )

    assert result["ok"] is True
    assert result["embedding_stored"] is False
    assert deal["meetings"] == []
    assert deal["interactions"][0]["summary"] == (
        "The customer said manual reporting takes too long."
    )
    assert deal["interactions"][0]["raw_content"].startswith("private raw note sentinel")
    assert deal["meddpicc_latest"]["filled_count"] == 1
    assert deal["customer_themes"][0]["theme_key"] == "operational_efficiency"
    assert "private raw note sentinel" in serialized
    assert "raw_notes" not in serialized
    assert "raw_content" not in json.dumps(
        after_meeting.list_deals_for_metrics(),
        ensure_ascii=False,
    )


def test_local_personal_archive_and_restore_persist_across_clients(tmp_path) -> None:
    client = LocalSampleClient(local_data_dir=tmp_path)
    client.upsert_deal(_local_deal())

    archived = archive_deal.handle(
        mongo=client,
        deal_id="local-life-1",
        expected_company="Local Lifecycle Co",
        archive_reason="user cleanup",
        confirmed_by_user=True,
    )

    after_archive = LocalSampleClient(local_data_dir=tmp_path)
    assert archived["storage_written"] is True
    assert after_archive.get_deal("local-life-1")["archived"] is True
    assert after_archive.list_deals(limit=10) == []

    restored = restore_deal.handle(
        mongo=after_archive,
        deal_id="local-life-1",
        expected_company="Local Lifecycle Co",
        restore_reason="undo cleanup",
        confirmed_by_user=True,
    )

    after_restore = LocalSampleClient(local_data_dir=tmp_path)
    restored_deal = after_restore.get_deal("local-life-1")
    assert restored["storage_written"] is True
    assert restored_deal["archived"] is False
    assert restored_deal["archive_history"][-1]["action"] == "restore"
    assert after_restore.list_deals(limit=10)[0]["deal_id"] == "local-life-1"


def test_local_personal_delete_preserves_audit_and_keeps_fixture_archived(tmp_path) -> None:
    client = LocalSampleClient(local_data_dir=tmp_path)
    client.upsert_deal(_local_deal(archived=True))

    dry_run = delete_deal.handle(
        mongo=client,
        deal_id="local-life-1",
        expected_company="Local Lifecycle Co",
        delete_reason="user cleanup",
    )
    assert dry_run["can_delete"] is True
    assert dry_run["storage_written"] is False
    assert not (tmp_path / LOCAL_PERSONAL_DELETE_AUDIT_FILE).exists()

    deleted = delete_deal.handle(
        mongo=client,
        deal_id="local-life-1",
        expected_company="Local Lifecycle Co",
        delete_reason="user cleanup",
        confirmed_by_user=True,
        dry_run=False,
    )

    after_delete = LocalSampleClient(local_data_dir=tmp_path)
    audit_logs = LocalPersonalStore(tmp_path).load_delete_audit_logs()
    serialized_logs = json.dumps(audit_logs, ensure_ascii=False)
    serialized_snapshot = json.dumps(
        audit_logs[0]["deal_snapshot"],
        ensure_ascii=False,
    )
    assert deleted["storage_written"] is True
    assert deleted["deleted_count"] == 1
    assert after_delete.get_deal("local-life-1") is None
    assert after_delete.get_deal("sample-pavebridge") is None
    assert after_delete.ping()["data_mode"] == "local_personal"
    assert after_delete.list_deals_for_metrics() == []
    assert len(audit_logs) == 1
    assert audit_logs[0]["delete_reason"] == "user cleanup"
    assert "private raw notes" not in serialized_logs
    assert "private@example.com" not in serialized_logs
    assert "summary_embedding" not in serialized_snapshot
    assert audit_logs[0]["deal_snapshot"]["meetings"][0]["summary"] == "safe summary"


def test_local_personal_delete_stops_when_audit_write_fails(tmp_path) -> None:
    class FailingAuditClient(LocalSampleClient):
        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            self.hard_delete_called = False

        def insert_delete_audit_log(self, entry: dict) -> None:
            raise RuntimeError("audit unavailable")

        def hard_delete_deal(self, deal_id: str) -> int:
            self.hard_delete_called = True
            return super().hard_delete_deal(deal_id)

    client = FailingAuditClient(local_data_dir=tmp_path)
    client.upsert_deal(_local_deal(archived=True))

    with pytest.raises(MCPError) as exc_info:
        delete_deal.handle(
            mongo=client,
            deal_id="local-life-1",
            expected_company="Local Lifecycle Co",
            delete_reason="user cleanup",
            confirmed_by_user=True,
            dry_run=False,
        )

    after_failure = LocalSampleClient(local_data_dir=tmp_path)
    assert exc_info.value.error_code == ErrorCode.STORAGE_ERROR
    assert client.hard_delete_called is False
    assert after_failure.get_deal("local-life-1") is not None
    assert not (tmp_path / LOCAL_PERSONAL_DELETE_AUDIT_FILE).exists()


def test_local_tools_cannot_persist_bundled_fixture_deals(tmp_path) -> None:
    client = LocalSampleClient(local_data_dir=tmp_path)

    with pytest.raises(MCPError) as exc_info:
        update_stage.handle(
            mongo=client,
            cfg=_local_cfg(tmp_path),
            deal_id="sample-pavebridge",
            new_stage="proposal",
        )

    assert exc_info.value.error_code == ErrorCode.STORAGE_ERROR
    assert "fixture deals are read-only" in exc_info.value.message
    assert not (tmp_path / LOCAL_PERSONAL_DEALS_FILE).exists()


def test_local_add_meeting_cannot_persist_bundled_fixture_deals(tmp_path) -> None:
    from types import SimpleNamespace

    class FakeLLM:
        def chat_once(self, **_kwargs):
            return SimpleNamespace(
                text=json.dumps({"meddpicc": {}, "customer_themes": []}),
                usage={},
            )

    client = LocalSampleClient(local_data_dir=tmp_path)

    with pytest.raises(MCPError) as exc_info:
        add_meeting.handle(
            mongo=client,
            llm=FakeLLM(),
            cfg=_local_cfg(tmp_path),
            embedding_provider=None,
            deal_id="sample-pavebridge",
            date="2026-06-11",
            raw_notes="should not be persisted on bundled fixture data",
        )

    assert exc_info.value.error_code == ErrorCode.STORAGE_ERROR
    assert "fixture deals are read-only" in exc_info.value.message
    assert not (tmp_path / LOCAL_PERSONAL_DEALS_FILE).exists()


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
