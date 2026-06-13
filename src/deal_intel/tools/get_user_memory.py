from __future__ import annotations

from typing import Any

from deal_intel.user_memory import get_user_memory


def handle(
    *,
    cfg: dict[str, Any],
    category: str = "",
    custom_doc_slug: str = "",
    limit: int = 5,
) -> dict[str, Any]:
    return get_user_memory(
        cfg,
        category=category,
        custom_doc_slug=custom_doc_slug,
        limit=limit,
    )
