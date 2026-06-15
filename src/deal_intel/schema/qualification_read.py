from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

MEDDPICC_DIMENSIONS = (
    "metrics",
    "economic_buyer",
    "decision_criteria",
    "decision_process",
    "identify_pain",
    "champion",
    "competition",
)

MEDDPICC_FIELD_LABELS = {
    "metrics": "Metrics",
    "economic_buyer": "Economic Buyer",
    "decision_criteria": "Decision Criteria",
    "decision_process": "Decision Process",
    "paper_process": "Paper Process",
    "identify_pain": "Identify Pain",
    "champion": "Champion",
    "competition": "Competition",
}

QUESTION_BY_MEDDPICC_GAP = {
    "metrics": "고객이 기대하는 정량 효과와 성공 기준은 무엇인가요?",
    "economic_buyer": "예산 최종 승인권자는 누구이며 직접 확인했나요?",
    "decision_criteria": "벤더 선정 기준과 필수 통과 조건은 무엇인가요?",
    "decision_process": "구매, 보안, 법무 승인 절차와 일정은 어떻게 되나요?",
    "paper_process": "계약서, 보안 검토, 구매 발주에 필요한 문서 절차는 무엇인가요?",
    "identify_pain": "지금 해결하지 않으면 고객에게 어떤 업무 또는 비용 문제가 생기나요?",
    "champion": "고객 내부에서 우리 도입을 밀어줄 champion은 누구인가요?",
    "competition": "경쟁사 또는 현 상태 유지와 비교해 무엇이 결정 변수인가요?",
}


@dataclass(frozen=True)
class QualificationReadSnapshot:
    framework_key: str
    framework_display_name: str
    source_field: str
    snapshot: dict[str, Any]
    dimensions: dict[str, dict[str, Any]]
    dimension_metadata: dict[str, dict[str, Any]]
    gaps: list[str]
    filled_count: int
    total_count: int
    coverage_pct: float | None
    quality_pct: float | None
    field_prefix: str

    @property
    def is_meddpicc(self) -> bool:
        return self.framework_key == "meddpicc"

    @property
    def dimension_keys(self) -> list[str]:
        if self.is_meddpicc:
            return list(MEDDPICC_DIMENSIONS)
        keys: list[str] = []
        for source in (
            self.dimension_metadata.keys(),
            self.dimensions.keys(),
            self.gaps,
        ):
            for key in source:
                if key not in keys:
                    keys.append(str(key))
        return keys


def select_qualification_snapshot(deal: dict) -> QualificationReadSnapshot:
    """Return the active qualification snapshot, falling back to legacy MEDDPICC."""
    qualification_latest = deal.get("qualification_latest")
    if _is_qualification_snapshot(qualification_latest):
        return _snapshot_from_qualification(qualification_latest)
    return _snapshot_from_legacy_meddpicc(deal.get("meddpicc_latest") or {})


def qualification_summary(snapshot: QualificationReadSnapshot) -> dict:
    return {
        "framework_key": snapshot.framework_key,
        "framework_display_name": snapshot.framework_display_name,
        "source_field": snapshot.source_field,
        "health_pct": snapshot.snapshot.get("health_pct"),
        "quality_pct": snapshot.quality_pct,
        "coverage_pct": snapshot.coverage_pct,
        "uncertainty_level": snapshot.snapshot.get("uncertainty_level"),
        "filled_count": snapshot.filled_count,
        "total_count": snapshot.total_count,
        "gaps": snapshot.gaps,
    }


def dimension_label(snapshot: QualificationReadSnapshot, dimension: str) -> str:
    item = snapshot.dimensions.get(dimension) or {}
    metadata = snapshot.dimension_metadata.get(dimension) or {}
    if isinstance(item.get("label"), str) and item["label"].strip():
        return str(item["label"])
    if isinstance(metadata.get("label"), str) and metadata["label"].strip():
        return str(metadata["label"])
    if snapshot.is_meddpicc:
        return MEDDPICC_FIELD_LABELS.get(dimension, dimension)
    return dimension.replace("_", " ").title()


def dimension_question(snapshot: QualificationReadSnapshot, dimension: str) -> str:
    metadata = snapshot.dimension_metadata.get(dimension) or {}
    question = metadata.get("suggested_question")
    if isinstance(question, str) and question.strip():
        return question.strip()
    if snapshot.is_meddpicc:
        return QUESTION_BY_MEDDPICC_GAP.get(
            dimension,
            (
                f"{dimension_label(snapshot, dimension)}에 대해 "
                "다음 미팅에서 무엇을 확인해야 하나요?"
            ),
        )
    return f"What should we verify for {dimension_label(snapshot, dimension)}?"


def _is_qualification_snapshot(value: Any) -> bool:
    if not isinstance(value, dict) or not value:
        return False
    if not isinstance(value.get("framework_key"), str):
        return False
    if not isinstance(value.get("dimensions"), dict):
        return False
    return True


def _snapshot_from_qualification(snapshot: dict) -> QualificationReadSnapshot:
    framework_key = str(snapshot.get("framework_key") or "qualification")
    dimensions = _safe_dict_mapping(snapshot.get("dimensions"))
    metadata = _safe_dict_mapping(snapshot.get("dimension_metadata"))
    total_count = _safe_positive_int(snapshot.get("total_count")) or max(
        len(metadata),
        len(dimensions),
        len(_safe_str_list(snapshot.get("gaps"))),
    )
    filled_count = _safe_non_negative_int(snapshot.get("filled_count")) or len(dimensions)
    coverage_pct = _safe_number(snapshot.get("coverage_pct"))
    if coverage_pct is None and total_count:
        coverage_pct = round(filled_count / total_count * 100, 1)
    return QualificationReadSnapshot(
        framework_key=framework_key,
        framework_display_name=str(
            snapshot.get("framework_display_name") or framework_key
        ),
        source_field="qualification_latest",
        snapshot=snapshot,
        dimensions=dimensions,
        dimension_metadata=metadata,
        gaps=_safe_str_list(snapshot.get("gaps")),
        filled_count=max(0, min(filled_count, total_count)) if total_count else 0,
        total_count=total_count,
        coverage_pct=coverage_pct,
        quality_pct=_safe_number(snapshot.get("quality_pct")),
        field_prefix="meddpicc" if framework_key == "meddpicc" else "qualification",
    )


def _snapshot_from_legacy_meddpicc(snapshot: dict) -> QualificationReadSnapshot:
    dimensions = {
        dim: item
        for dim in MEDDPICC_DIMENSIONS
        if isinstance((item := snapshot.get(dim)), dict)
    }
    filled_count = _filled_count(snapshot)
    total_count = len(MEDDPICC_DIMENSIONS)
    coverage_pct = round(filled_count / total_count * 100, 1) if total_count else None
    return QualificationReadSnapshot(
        framework_key="meddpicc",
        framework_display_name="MEDDPICC",
        source_field="meddpicc_latest",
        snapshot=snapshot,
        dimensions=dimensions,
        dimension_metadata={},
        gaps=_safe_str_list(snapshot.get("gaps")),
        filled_count=filled_count,
        total_count=total_count,
        coverage_pct=coverage_pct,
        quality_pct=None,
        field_prefix="meddpicc",
    )


def _filled_count(meddpicc_latest: dict) -> int:
    filled_count = meddpicc_latest.get("filled_count")
    if isinstance(filled_count, int) and not isinstance(filled_count, bool):
        return max(0, min(filled_count, len(MEDDPICC_DIMENSIONS)))
    return sum(
        1 for dim in MEDDPICC_DIMENSIONS if isinstance(meddpicc_latest.get(dim), dict)
    )


def _safe_str_list(value: Any) -> list[str]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, dict)):
        return []
    result: list[str] = []
    for item in value:
        text = str(item)
        if text not in result:
            result.append(text)
    return result


def _safe_dict_mapping(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items() if isinstance(item, dict)}


def _safe_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(float(value), 2)


def _safe_non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _safe_positive_int(value: Any) -> int | None:
    parsed = _safe_non_negative_int(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed
