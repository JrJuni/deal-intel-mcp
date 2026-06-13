from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from deal_intel.errors import ErrorCode, MCPError, Stage

DEFAULT_CATEGORY = "general"
BUILT_IN_CATEGORIES: dict[str, str] = {
    "operating_preferences": "operating-preferences.md",
    "metric_tuning": "metric-tuning-feedback.md",
    "taxonomy": "taxonomy-feedback.md",
    "report_review": "report-review-feedback.md",
    "evidence_policy": "evidence-policy.md",
    "general": "general.md",
}

_SAFE_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}\.md$")
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("mongodb_uri", re.compile(r"mongodb(?:\+srv)?://[^\s)>\]\"']+", re.I)),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b")),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{16,}\b")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b")),
    (
        "named_secret",
        re.compile(
            r"\b(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|MONGODB_URI|"
            r"CHATGPT_TOKEN|OAUTH_TOKEN|ACCESS_TOKEN|REFRESH_TOKEN)\s*=\s*\S+",
            re.I,
        ),
    ),
    (
        "private_key",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I),
    ),
)


@dataclass(frozen=True)
class UserMemoryTarget:
    memory_dir: Path
    path: Path
    category: str
    document: str
    is_custom: bool


def record_user_memory(
    cfg: dict[str, Any],
    *,
    content: str,
    category: str = DEFAULT_CATEGORY,
    custom_doc_slug: str = "",
    title: str = "",
    source: str = "",
    importance: str = "normal",
    tags: str = "",
) -> dict[str, Any]:
    """Append durable user feedback to a constrained Markdown memory file."""
    text = _clean_text(content)
    if not text:
        raise _invalid("content is required")

    secret_hits = detect_secret_patterns(text)
    if secret_hits:
        raise MCPError(
            error_code=ErrorCode.INVALID_INPUT,
            stage=Stage.PREFLIGHT,
            message="content appears to contain a secret and was not written",
            hint={
                "secret_patterns": secret_hits,
                "fix": (
                    "Remove API keys, OAuth tokens, MongoDB URIs, private keys, "
                    "or credential-like values before recording user memory."
                ),
            },
            retryable=False,
        )

    target = resolve_user_memory_target(
        cfg,
        category=category,
        custom_doc_slug=custom_doc_slug,
    )
    target.memory_dir.mkdir(parents=True, exist_ok=True)

    if not target.path.exists():
        target.path.write_text(_initial_document_text(target), encoding="utf-8")

    entry_id = datetime.now(UTC).strftime("mem-%Y%m%dT%H%M%SZ")
    entry = _format_entry(
        entry_id=entry_id,
        content=text,
        title=title,
        source=source,
        importance=importance,
        tags=tags,
    )

    with target.path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(entry)

    return {
        "ok": True,
        "entry_id": entry_id,
        "memory_dir": str(target.memory_dir),
        "path": str(target.path),
        "category": target.category,
        "document": target.document,
        "is_custom_document": target.is_custom,
        "bytes_written": len(entry.encode("utf-8")),
        "secret_scan": {"checked": True, "hits": []},
    }


def get_user_memory(
    cfg: dict[str, Any],
    *,
    category: str = "",
    custom_doc_slug: str = "",
    limit: int = 5,
) -> dict[str, Any]:
    """Read constrained Markdown memory docs for assistant context loading."""
    max_docs = _bounded_limit(limit)
    memory_dir = resolve_user_memory_dir(cfg)
    if category or custom_doc_slug:
        target = resolve_user_memory_target(
            cfg,
            category=category or DEFAULT_CATEGORY,
            custom_doc_slug=custom_doc_slug,
        )
        documents = [_document_payload(target.path, target)]
    else:
        documents = [
            _document_payload(path, _target_from_path(memory_dir, path))
            for path in sorted(memory_dir.glob("*.md"))
            if _is_memory_document(path)
        ][:max_docs]

    return {
        "ok": True,
        "memory_dir": str(memory_dir),
        "filters": {
            "category": category or None,
            "custom_doc_slug": custom_doc_slug or None,
            "limit": max_docs,
        },
        "documents": documents,
        "summary": {
            "document_count": len(documents),
            "existing_count": sum(1 for doc in documents if doc["exists"]),
            "missing_count": sum(1 for doc in documents if not doc["exists"]),
        },
        "warnings": [] if memory_dir.exists() else ["memory_dir_not_created_yet"],
    }


def resolve_user_memory_dir(cfg: dict[str, Any]) -> Path:
    user_memory = cfg.get("user_memory") if isinstance(cfg, dict) else None
    configured = (
        user_memory.get("dir")
        if isinstance(user_memory, dict) and user_memory.get("dir")
        else "user_docs"
    )
    raw = os.path.expandvars(str(configured))
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def resolve_user_memory_target(
    cfg: dict[str, Any],
    *,
    category: str = DEFAULT_CATEGORY,
    custom_doc_slug: str = "",
) -> UserMemoryTarget:
    memory_dir = resolve_user_memory_dir(cfg)
    if custom_doc_slug.strip():
        document = normalize_custom_doc_slug(custom_doc_slug)
        return _safe_target(memory_dir, document, category="custom", is_custom=True)

    normalized_category = _normalize_category(category)
    document = BUILT_IN_CATEGORIES[normalized_category]
    return _safe_target(
        memory_dir,
        document,
        category=normalized_category,
        is_custom=False,
    )


def normalize_custom_doc_slug(value: str) -> str:
    slug = value.strip().lower()
    if not slug.endswith(".md"):
        slug = f"{slug}.md"
    if not _SAFE_SLUG_RE.fullmatch(slug):
        raise _invalid(
            "custom_doc_slug must be a safe Markdown slug like "
            "pricing-objections.md"
        )
    return slug


def detect_secret_patterns(text: str) -> list[str]:
    return [name for name, pattern in _SECRET_PATTERNS if pattern.search(text)]


def _safe_target(
    memory_dir: Path,
    document: str,
    *,
    category: str,
    is_custom: bool,
) -> UserMemoryTarget:
    path = (memory_dir / document).resolve()
    try:
        path.relative_to(memory_dir)
    except ValueError as exc:
        raise _invalid("memory document must stay inside the user memory directory") from exc
    return UserMemoryTarget(
        memory_dir=memory_dir,
        path=path,
        category=category,
        document=document,
        is_custom=is_custom,
    )


def _normalize_category(value: str) -> str:
    normalized = (value or DEFAULT_CATEGORY).strip().lower().replace("-", "_")
    if normalized not in BUILT_IN_CATEGORIES:
        raise _invalid(
            "category must be one of: "
            + ", ".join(sorted(BUILT_IN_CATEGORIES))
            + "; use custom_doc_slug for user-created documents"
        )
    return normalized


def _clean_text(value: str) -> str:
    return str(value or "").strip()


def _bounded_limit(value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise _invalid("limit must be an integer") from exc
    if parsed < 1:
        return 1
    return min(parsed, 20)


def _initial_document_text(target: UserMemoryTarget) -> str:
    title = target.document.removesuffix(".md").replace("-", " ").title()
    return (
        f"# {title}\n\n"
        "This user-memory document stores durable user feedback for Deal "
        "Intelligence assistants. Keep entries concise and secret-free.\n"
    )


def _format_entry(
    *,
    entry_id: str,
    content: str,
    title: str,
    source: str,
    importance: str,
    tags: str,
) -> str:
    lines = [
        "",
        f"## {title.strip() or 'Memory Entry'}",
        "",
        f"- entry_id: `{entry_id}`",
        f"- recorded_at: `{datetime.now(UTC).isoformat(timespec='seconds')}`",
        f"- importance: `{(importance or 'normal').strip() or 'normal'}`",
    ]
    if source.strip():
        lines.append(f"- source: `{source.strip()}`")
    if tags.strip():
        lines.append(f"- tags: `{tags.strip()}`")
    lines.extend(["", content, ""])
    return "\n".join(lines)


def _document_payload(path: Path, target: UserMemoryTarget) -> dict[str, Any]:
    exists = path.exists()
    content = path.read_text(encoding="utf-8") if exists else ""
    return {
        "category": target.category,
        "document": target.document,
        "path": str(path),
        "exists": exists,
        "is_custom_document": target.is_custom,
        "content": content,
        "bytes": len(content.encode("utf-8")) if exists else 0,
    }


def _target_from_path(memory_dir: Path, path: Path) -> UserMemoryTarget:
    category = next(
        (
            category
            for category, document in BUILT_IN_CATEGORIES.items()
            if document == path.name
        ),
        "custom",
    )
    return UserMemoryTarget(
        memory_dir=memory_dir,
        path=path,
        category=category,
        document=path.name,
        is_custom=category == "custom",
    )


def _is_memory_document(path: Path) -> bool:
    if path.name == "README.md":
        return False
    return not path.name.endswith(".sample.md")


def _invalid(message: str) -> MCPError:
    return MCPError(
        error_code=ErrorCode.INVALID_INPUT,
        stage=Stage.PREFLIGHT,
        message=message,
        retryable=False,
    )
