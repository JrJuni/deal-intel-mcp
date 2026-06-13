from __future__ import annotations

from typing import Any

from deal_intel.user_memory import record_user_memory


def handle(
    *,
    cfg: dict[str, Any],
    content: str,
    category: str = "general",
    custom_doc_slug: str = "",
    title: str = "",
    source: str = "",
    importance: str = "normal",
    tags: str = "",
) -> dict[str, Any]:
    return record_user_memory(
        cfg,
        content=content,
        category=category,
        custom_doc_slug=custom_doc_slug,
        title=title,
        source=source,
        importance=importance,
        tags=tags,
    )
