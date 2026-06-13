from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from deal_intel import _context, mcp_server
from deal_intel.errors import MCPError
from deal_intel.tools import get_user_memory, record_user_memory
from deal_intel.user_memory import (
    detect_secret_patterns,
    normalize_custom_doc_slug,
    resolve_user_memory_dir,
)


def _cfg(tmp_path: Path) -> dict:
    return {"user_memory": {"dir": str(tmp_path / "memory")}}


def test_record_user_memory_appends_to_builtin_category(tmp_path: Path) -> None:
    payload = record_user_memory.handle(
        cfg=_cfg(tmp_path),
        category="metric_tuning",
        title="Health threshold feedback",
        content="Unknown evidence should raise uncertainty, not neutral health.",
        source="user_chat",
        tags="scoring,uncertainty",
    )

    assert payload["ok"] is True
    assert payload["category"] == "metric_tuning"
    assert payload["document"] == "metric-tuning-feedback.md"
    written = Path(payload["path"]).read_text(encoding="utf-8")
    assert "Health threshold feedback" in written
    assert "Unknown evidence should raise uncertainty" in written
    assert "scoring,uncertainty" in written


def test_record_user_memory_allows_user_requested_custom_document(
    tmp_path: Path,
) -> None:
    payload = record_user_memory.handle(
        cfg=_cfg(tmp_path),
        custom_doc_slug="public-sector-sales-notes",
        content="Public-sector deals should show procurement timeline uncertainty.",
    )

    assert payload["ok"] is True
    assert payload["category"] == "custom"
    assert payload["document"] == "public-sector-sales-notes.md"
    written = Path(payload["path"]).read_text(encoding="utf-8")
    assert "# Public Sector Sales Notes" in written
    assert "procurement timeline uncertainty" in written


@pytest.mark.parametrize(
    "slug",
    [
        "../secrets.md",
        "nested/path.md",
        ".hidden.md",
        "run.ps1",
        "Bad Spaces.md",
    ],
)
def test_custom_document_slug_rejects_unsafe_paths(slug: str) -> None:
    with pytest.raises(MCPError, match="custom_doc_slug"):
        normalize_custom_doc_slug(slug)


def test_record_user_memory_rejects_secret_shaped_content(tmp_path: Path) -> None:
    with pytest.raises(MCPError) as exc_info:
        record_user_memory.handle(
            cfg=_cfg(tmp_path),
            content="Use MONGODB_URI=mongodb+srv://user:pass@example/db later.",
        )

    envelope = exc_info.value.to_envelope()
    assert envelope["error_code"] == "INVALID_INPUT"
    assert "secret" in envelope["message"]
    assert "mongodb_uri" in envelope["hint"]["secret_patterns"]
    assert not resolve_user_memory_dir(_cfg(tmp_path)).exists()


def test_detect_secret_patterns_covers_common_credentials() -> None:
    hits = detect_secret_patterns(
        "OPENAI_API_KEY=sk-testsecret1234567890 and ghp_abcdefghijklmnopqrstuvwxyz"
    )

    assert "named_secret" in hits
    assert "github_token" in hits


def test_get_user_memory_reads_existing_docs_and_reports_missing(
    tmp_path: Path,
) -> None:
    record_user_memory.handle(
        cfg=_cfg(tmp_path),
        category="taxonomy",
        content="Insurance and Finance can both be tags.",
    )

    payload = get_user_memory.handle(cfg=_cfg(tmp_path), category="taxonomy")

    assert payload["ok"] is True
    assert payload["summary"] == {
        "document_count": 1,
        "existing_count": 1,
        "missing_count": 0,
    }
    assert payload["documents"][0]["category"] == "taxonomy"
    assert "Insurance and Finance" in payload["documents"][0]["content"]


def test_get_user_memory_lists_docs_without_sample_templates(tmp_path: Path) -> None:
    memory_dir = resolve_user_memory_dir(_cfg(tmp_path))
    memory_dir.mkdir(parents=True)
    (memory_dir / "README.md").write_text("policy", encoding="utf-8")
    (memory_dir / "evidence-policy.sample.md").write_text("sample", encoding="utf-8")
    (memory_dir / "pricing-objections.md").write_text("custom", encoding="utf-8")

    payload = get_user_memory.handle(cfg=_cfg(tmp_path), limit=10)

    assert [doc["document"] for doc in payload["documents"]] == [
        "pricing-objections.md"
    ]


def test_user_memory_tools_are_registered_in_mcp_runtime(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        _context,
        "config",
        lambda: {
            "storage": {"backend": "local_sample"},
            "tools": {"surface": "auto"},
            "user_memory": {"dir": str(tmp_path / "memory")},
        },
    )

    names = {tool.name for tool in asyncio.run(mcp_server.app.list_tools())}

    assert "get_user_memory" in names
    assert "record_user_memory" in names
