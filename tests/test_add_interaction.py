from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from deal_intel import _context, mcp_server
from deal_intel.errors import ErrorCode, MCPError
from deal_intel.storage.local_personal import LOCAL_PERSONAL_DEALS_FILE
from deal_intel.storage.local_sample import LocalSampleClient
from deal_intel.tools import add_interaction, create_deal


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)
        self.calls: list[dict] = []

    def chat_once(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            text=next(self.responses),
            usage={"input_tokens": 10, "output_tokens": 5},
        )


class FakeMongo:
    def __init__(self, deal: dict | None = None) -> None:
        self.deal = deepcopy(deal)
        self.saved: dict | None = None

    def get_deal(self, deal_id: str) -> dict | None:
        if self.deal is None or self.deal.get("deal_id") != deal_id:
            return None
        return deepcopy(self.deal)

    def upsert_deal(self, deal: dict) -> None:
        self.saved = deepcopy(deal)
        self.deal = deepcopy(deal)


def _deal() -> dict:
    return {
        "deal_id": "deal-1",
        "company": "Acme",
        "deal_stage": "discovery",
        "interactions": [],
        "meetings": [],
        "customer_themes": [],
        "meddpicc_latest": {},
    }


def _analysis(score: int = 4) -> str:
    return json.dumps(
        {
            "meddpicc": {
                "identify_pain": {
                    "score": score,
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
    )


def _local_cfg(tmp_path) -> dict:
    return {
        "storage": {
            "backend": "local_sample",
            "local_data_dir": str(tmp_path),
        },
        "reporting": {"timezone": "Asia/Seoul"},
        "meddpicc": {"weights": {}},
    }


def test_add_interaction_stores_canonical_customer_evidence() -> None:
    mongo = FakeMongo(_deal())
    llm = FakeLLM([_analysis(), "Customer says reporting is too slow."])

    result = add_interaction.handle(
        mongo=mongo,
        llm=llm,
        cfg={"meddpicc": {"weights": {}}},
        embedding_provider=None,
        deal_id="deal-1",
        date="2026-06-11",
        interaction_type="email_thread",
        direction="inbound",
        content="Customer reply: manual reporting takes too long.",
        participants="buyer@example.com, ae@example.com",
        subject="Re: reporting workflow",
    )

    assert result["ok"] is True
    assert result["interaction_type"] == "email_thread"
    assert result["source_confidence"] == "customer_stated"
    assert result["scoring_applied"] is True
    assert result["source_policy"] == {
        "interaction_type": "email_thread",
        "direction": "inbound",
        "source_confidence": "customer_stated",
        "scoring_applied": True,
        "score_policy": "confirmed_evidence",
        "reason": (
            "Direct customer-stated evidence can update MEDDPICC and customer "
            "themes."
        ),
        "stage_policy": "suggest_only",
        "content_policy": "retained_for_single_deal_detail_excluded_from_bi",
    }
    assert result["meddpicc"]["identify_pain"]["score"] == 4
    assert result["meddpicc_latest"]["filled_count"] == 1

    assert mongo.saved is not None
    interaction = mongo.saved["interactions"][0]
    assert mongo.saved["meetings"] == []
    assert interaction["interaction_id"] == result["interaction_id"]
    assert interaction["meeting_id"] == result["interaction_id"]
    assert "raw_notes" not in interaction
    assert interaction["raw_content"] == "Customer reply: manual reporting takes too long."
    assert interaction["summary"] == "Customer says reporting is too slow."
    assert mongo.saved["customer_themes"][0]["theme_key"] == "operational_efficiency"
    assert mongo.saved["customer_themes"][0]["interaction_id"] == result["interaction_id"]


def test_outbound_only_interaction_is_stored_but_not_scored() -> None:
    mongo = FakeMongo(_deal())
    llm = FakeLLM([_analysis(score=5), "Seller sent an outbound pitch."])

    result = add_interaction.handle(
        mongo=mongo,
        llm=llm,
        cfg={"meddpicc": {"weights": {}}},
        deal_id="deal-1",
        date="2026-06-11",
        interaction_type="email_thread",
        direction="outbound",
        content="We can reduce manual reporting time by 80%.",
    )

    assert result["source_confidence"] == "outbound_unconfirmed"
    assert result["scoring_applied"] is False
    assert result["source_policy"]["score_policy"] == "stored_unconfirmed"
    assert "does not update MEDDPICC" in result["source_policy"]["reason"]
    assert result["meddpicc"] == {}
    assert result["unconfirmed_meddpicc"]["identify_pain"]["score"] == 5
    assert result["meddpicc_latest"]["filled_count"] == 0

    assert mongo.saved is not None
    interaction = mongo.saved["interactions"][0]
    assert mongo.saved["meetings"] == []
    assert interaction["meddpicc"] == {}
    assert interaction["customer_themes"] == []
    assert interaction["unconfirmed_meddpicc"]["identify_pain"]["score"] == 5
    assert mongo.saved["customer_themes"] == []


def test_add_interaction_preserves_legacy_meeting_evidence_in_latest_snapshot() -> None:
    deal = _deal()
    deal["meetings"] = [
        {
            "meeting_id": "legacy-meeting",
            "date": "2026-06-10",
            "meddpicc": {
                "metrics": {
                    "score": 4,
                    "evidence": "reduce reporting time by 50%",
                }
            },
        }
    ]
    mongo = FakeMongo(deal)
    llm = FakeLLM([_analysis(), "Customer says reporting is too slow."])

    result = add_interaction.handle(
        mongo=mongo,
        llm=llm,
        cfg={"meddpicc": {"weights": {}}},
        deal_id="deal-1",
        date="2026-06-11",
        interaction_type="email_thread",
        direction="inbound",
        content="Customer reply: manual reporting takes too long.",
    )

    assert result["meddpicc_latest"]["filled_count"] == 2
    assert "metrics" in result["meddpicc_latest"]
    assert "identify_pain" in result["meddpicc_latest"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"interaction_type": "fax", "direction": "inbound"}, "interaction_type"),
        ({"interaction_type": "email_thread", "direction": "sideways"}, "direction"),
        (
            {
                "interaction_type": "email_thread",
                "direction": "inbound",
                "source_confidence": "certain",
            },
            "source_confidence",
        ),
    ],
)
def test_add_interaction_rejects_invalid_preflight_values(kwargs, message) -> None:
    with pytest.raises(MCPError) as exc_info:
        add_interaction.handle(
            mongo=FakeMongo(_deal()),
            llm=FakeLLM([_analysis(), "summary"]),
            cfg={},
            deal_id="deal-1",
            date="2026-06-11",
            content="customer replied",
            **kwargs,
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
    assert message in exc_info.value.message


def test_local_personal_add_interaction_persists_raw_content_but_restricts_lists(
    tmp_path,
) -> None:
    cfg = _local_cfg(tmp_path)
    client = LocalSampleClient(local_data_dir=tmp_path)
    created = create_deal.handle(
        mongo=client,
        cfg=cfg,
        company="Local Interaction Co",
        industry="Trial",
        deal_size_amount=None,
        deal_size_status="unknown",
    )

    result = add_interaction.handle(
        mongo=LocalSampleClient(local_data_dir=tmp_path),
        llm=FakeLLM([_analysis(), "Customer interview summary."]),
        cfg=cfg,
        embedding_provider=None,
        deal_id=created["deal_id"],
        date="2026-06-11",
        interaction_type="user_interview",
        direction="inbound",
        content="private interaction sentinel: manual reporting takes too long",
    )

    after = LocalSampleClient(local_data_dir=tmp_path)
    deal = after.get_deal(created["deal_id"])
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
    assert deal["interactions"][0]["interaction_type"] == "user_interview"
    assert deal["interactions"][0]["summary"] == "Customer interview summary."
    assert deal["interactions"][0]["raw_content"].startswith("private interaction sentinel")
    assert "private interaction sentinel" in serialized
    assert "raw_notes" not in serialized
    assert "raw_content" not in json.dumps(
        after.list_deals_for_metrics(),
        ensure_ascii=False,
    )


def test_local_add_interaction_cannot_persist_bundled_fixture_deals(tmp_path) -> None:
    with pytest.raises(MCPError) as exc_info:
        add_interaction.handle(
            mongo=LocalSampleClient(local_data_dir=tmp_path),
            llm=FakeLLM([_analysis(), "summary"]),
            cfg=_local_cfg(tmp_path),
            embedding_provider=None,
            deal_id="sample-pavebridge",
            date="2026-06-11",
            interaction_type="email_thread",
            direction="inbound",
            content="should not be persisted on bundled fixture data",
        )

    assert exc_info.value.error_code == ErrorCode.STORAGE_ERROR
    assert "fixture deals are read-only" in exc_info.value.message
    assert not (tmp_path / LOCAL_PERSONAL_DEALS_FILE).exists()


def test_sample_mcp_add_interaction_skips_embedding_provider(monkeypatch) -> None:
    mongo = FakeMongo(_deal())

    monkeypatch.setattr(
        _context,
        "config",
        lambda: {"storage": {"backend": "local_sample"}, "meddpicc": {"weights": {}}},
    )
    monkeypatch.setattr(_context, "storage_backend_name", lambda: "local_sample")
    monkeypatch.setattr(_context, "mongo", lambda: mongo)
    monkeypatch.setattr(
        _context,
        "llm_provider",
        lambda: FakeLLM([_analysis(), "Customer says reporting is too slow."]),
    )

    def fail_if_called():
        raise AssertionError("local_sample add_interaction must not initialize embeddings")

    monkeypatch.setattr(_context, "embedding_provider", fail_if_called)

    result = mcp_server.add_interaction(
        deal_id="deal-1",
        date="2026-06-11",
        interaction_type="email_thread",
        direction="inbound",
        content="Customer reply: manual reporting takes too long.",
    )

    assert result["ok"] is True
    assert result["embedding_stored"] is False
    assert mongo.saved is not None
    assert mongo.saved["meetings"] == []
    assert mongo.saved["interactions"][0]["interaction_type"] == "email_thread"


def test_custom_interaction_type_requires_config_registration() -> None:
    with pytest.raises(MCPError) as exc_info:
        add_interaction.handle(
            mongo=FakeMongo(_deal()),
            llm=FakeLLM([_analysis(), "summary"]),
            cfg={},
            deal_id="deal-1",
            date="2026-06-11",
            interaction_type="security_review",
            direction="inbound",
            content="Customer asked for security review.",
        )

    assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
    assert "interaction_type" in exc_info.value.message

    mongo = FakeMongo(_deal())
    result = add_interaction.handle(
        mongo=mongo,
        llm=FakeLLM([_analysis(), "Security review summary."]),
        cfg={
            "interactions": {"custom_types": ["security_review"]},
            "meddpicc": {"weights": {}},
        },
        deal_id="deal-1",
        date="2026-06-11",
        interaction_type="security_review",
        direction="inbound",
        content="Customer asked for security review.",
        custom_fields_json='{"review_type":"soc2"}',
    )

    assert result["ok"] is True
    assert mongo.saved is not None
    interaction = mongo.saved["interactions"][0]
    assert interaction["interaction_type"] == "security_review"
    assert interaction["custom_fields"] == {"review_type": "soc2"}
