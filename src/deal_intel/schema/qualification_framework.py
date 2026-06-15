from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from deal_intel.schema.gap_actionability import (
    CTA_POLICY_ALLOWED,
    CTA_POLICY_OBSERVATION_ONLY,
)
from deal_intel.schema.stages import VALID_STAGES
from deal_intel.user_memory import detect_secret_patterns

FrameworkIssueSeverity = Literal["error", "warning"]
CTAPolicy = Literal["cta_allowed", "observation_only"]

FRAMEWORK_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
DIMENSION_KEY_RE = FRAMEWORK_KEY_RE
SCORE_SCALE_MIN = 0
SCORE_SCALE_MAX = 5
MIN_ENABLED_DIMENSIONS = 2

MEDDPICC_DEFAULT_WEIGHTS: dict[str, float] = {
    "metrics": 1.0,
    "economic_buyer": 1.5,
    "decision_criteria": 1.0,
    "decision_process": 1.0,
    "identify_pain": 1.5,
    "champion": 2.0,
    "competition": 0.5,
}
MEDDPICC_DEFAULT_GAP_THRESHOLD = 2

_GENERIC_EXTRACTION_HINTS = {
    "score this well",
    "score it well",
    "evaluate this",
    "assess this",
    "good fit",
    "make a judgment",
    "judge the deal",
}


class QualificationFrameworkIssue(BaseModel):
    severity: FrameworkIssueSeverity
    code: str
    path: str
    message: str


class QualificationScoreScale(BaseModel):
    min: int = SCORE_SCALE_MIN
    max: int = SCORE_SCALE_MAX

    @model_validator(mode="after")
    def _fixed_v2_scale(self) -> QualificationScoreScale:
        if self.min != SCORE_SCALE_MIN or self.max != SCORE_SCALE_MAX:
            raise ValueError("score_scale must be fixed at 0-5 in v2")
        return self


class QualificationStageRule(BaseModel):
    stages: list[str] = Field(default_factory=list)
    gap_threshold: int | None = None
    suppress_gap: bool = False
    note: str = ""

    @field_validator("stages")
    @classmethod
    def _valid_stages(cls, value: list[str]) -> list[str]:
        invalid = sorted({stage for stage in value if stage not in VALID_STAGES})
        if invalid:
            raise ValueError("invalid stages: " + ", ".join(invalid))
        return value

    @field_validator("gap_threshold", mode="before")
    @classmethod
    def _valid_gap_threshold(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if isinstance(value, bool):
            raise ValueError("gap_threshold must be an integer from 0 to 5")
        parsed = int(value)
        if parsed < SCORE_SCALE_MIN or parsed > SCORE_SCALE_MAX:
            raise ValueError("gap_threshold must be an integer from 0 to 5")
        return parsed


class QualificationDimension(BaseModel):
    label: str
    description: str
    extraction_hint: str
    weight: float = 1.0
    gap_threshold: int = MEDDPICC_DEFAULT_GAP_THRESHOLD
    suggested_question: str = ""
    cta_policy: CTAPolicy = CTA_POLICY_OBSERVATION_ONLY
    enabled: bool = True
    stage_rules: list[QualificationStageRule] = Field(default_factory=list)

    @field_validator("label", "description", "extraction_hint")
    @classmethod
    def _required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("field is required")
        _reject_secret_like(normalized)
        return normalized

    @field_validator("suggested_question", "cta_policy")
    @classmethod
    def _optional_secret_safe_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if normalized:
            _reject_secret_like(normalized)
        return normalized

    @field_validator("weight", mode="before")
    @classmethod
    def _positive_weight(cls, value: float) -> float:
        if isinstance(value, bool):
            raise ValueError("weight must be greater than 0")
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("weight must be a number greater than 0") from exc
        if parsed <= 0:
            raise ValueError("weight must be greater than 0")
        return parsed

    @field_validator("gap_threshold", mode="before")
    @classmethod
    def _valid_gap_threshold(cls, value: int) -> int:
        if isinstance(value, bool):
            raise ValueError("gap_threshold must be an integer from 0 to 5")
        parsed = int(value)
        if parsed < SCORE_SCALE_MIN or parsed > SCORE_SCALE_MAX:
            raise ValueError("gap_threshold must be an integer from 0 to 5")
        return parsed

    @field_validator("cta_policy", mode="before")
    @classmethod
    def _normalize_cta_policy(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if normalized == "observation_by_default":
            return CTA_POLICY_OBSERVATION_ONLY
        return normalized

    @field_validator("extraction_hint")
    @classmethod
    def _scorable_hint(cls, value: str) -> str:
        lowered = value.strip().lower()
        word_count = len(re.findall(r"[A-Za-z0-9가-힣]+", lowered))
        if word_count < 6 or lowered in _GENERIC_EXTRACTION_HINTS:
            raise ValueError(
                "extraction_hint must describe observable evidence, not a generic instruction"
            )
        return value


class QualificationFramework(BaseModel):
    key: str
    display_name: str
    score_scale: QualificationScoreScale = Field(default_factory=QualificationScoreScale)
    dimensions: dict[str, QualificationDimension]

    @field_validator("key")
    @classmethod
    def _valid_framework_key(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not FRAMEWORK_KEY_RE.fullmatch(normalized):
            raise ValueError("framework key must be snake_case")
        _reject_secret_like(normalized)
        return normalized

    @field_validator("display_name")
    @classmethod
    def _valid_display_name(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("display_name is required")
        _reject_secret_like(normalized)
        return normalized

    @field_validator("dimensions")
    @classmethod
    def _valid_dimension_keys(
        cls,
        value: dict[str, QualificationDimension],
    ) -> dict[str, QualificationDimension]:
        if not value:
            raise ValueError("dimensions are required")
        for key in value:
            if not DIMENSION_KEY_RE.fullmatch(str(key)):
                raise ValueError(f"dimension key must be snake_case: {key}")
            _reject_secret_like(str(key))
        return value

    @model_validator(mode="after")
    def _enough_enabled_dimensions(self) -> QualificationFramework:
        enabled = [dim for dim in self.dimensions.values() if dim.enabled]
        if len(enabled) < MIN_ENABLED_DIMENSIONS:
            raise ValueError("framework must have at least two enabled dimensions")
        return self


def built_in_qualification_templates() -> dict[str, QualificationFramework]:
    """Return bundled framework templates as validated models."""
    return {
        key: QualificationFramework.model_validate(payload)
        for key, payload in _BUILT_IN_TEMPLATE_PAYLOADS.items()
    }


def get_qualification_template(key: str) -> QualificationFramework:
    templates = built_in_qualification_templates()
    try:
        return templates[key]
    except KeyError as exc:
        raise ValueError("unknown qualification framework template: " + key) from exc


def qualification_framework_fingerprint(framework: QualificationFramework) -> str:
    """Return a stable fingerprint for extraction-affecting framework settings."""

    payload = framework.model_dump(mode="json")
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def validate_qualification_framework(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a framework payload and return a secret-safe report."""
    try:
        framework = QualificationFramework.model_validate(payload)
    except ValidationError as exc:
        return {
            "ok": False,
            "framework": None,
            "errors": [_issue_from_pydantic_error(error).model_dump() for error in exc.errors()],
            "warnings": [],
        }

    warnings = _framework_warnings(framework)
    return {
        "ok": True,
        "framework": framework.model_dump(mode="json"),
        "errors": [],
        "warnings": [issue.model_dump() for issue in warnings],
    }


def _framework_warnings(framework: QualificationFramework) -> list[QualificationFrameworkIssue]:
    warnings: list[QualificationFrameworkIssue] = []
    for key, dimension in framework.dimensions.items():
        if not dimension.suggested_question:
            warnings.append(
                QualificationFrameworkIssue(
                    severity="warning",
                    code="missing_suggested_question",
                    path=f"dimensions.{key}.suggested_question",
                    message="suggested_question is empty; gap tools may give less helpful prompts",
                )
            )
    return warnings


def _issue_from_pydantic_error(error: dict[str, Any]) -> QualificationFrameworkIssue:
    loc = ".".join(str(part) for part in error.get("loc", ())) or "framework"
    message = str(error.get("msg") or "invalid framework")
    return QualificationFrameworkIssue(
        severity="error",
        code="invalid_framework",
        path=loc,
        message=message,
    )


def _reject_secret_like(value: str) -> None:
    hits = detect_secret_patterns(value)
    if hits:
        raise ValueError("field appears to contain a secret: " + ", ".join(sorted(hits)))


def _dimension(
    *,
    label: str,
    description: str,
    extraction_hint: str,
    weight: float = 1.0,
    gap_threshold: int = MEDDPICC_DEFAULT_GAP_THRESHOLD,
    suggested_question: str,
    cta_policy: str = CTA_POLICY_OBSERVATION_ONLY,
    stage_rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "label": label,
        "description": description,
        "extraction_hint": extraction_hint,
        "weight": weight,
        "gap_threshold": gap_threshold,
        "suggested_question": suggested_question,
        "cta_policy": cta_policy,
        "stage_rules": stage_rules or [],
    }


_BUILT_IN_TEMPLATE_PAYLOADS: dict[str, dict[str, Any]] = {
    "meddpicc": {
        "key": "meddpicc",
        "display_name": "MEDDPICC",
        "score_scale": {"min": 0, "max": 5},
        "dimensions": {
            "metrics": _dimension(
                label="Metrics",
                description="Quantified business impact or success metric.",
                extraction_hint=(
                    "Look for measurable business impact, KPI, ROI, cost, revenue, "
                    "time, risk, or efficiency signals stated by the customer."
                ),
                weight=MEDDPICC_DEFAULT_WEIGHTS["metrics"],
                suggested_question="What measurable outcome does the customer expect?",
            ),
            "economic_buyer": _dimension(
                label="Economic Buyer",
                description="Person or group with final budget authority.",
                extraction_hint=(
                    "Look for evidence of who owns budget, final approval, executive "
                    "sponsorship, or financial sign-off for the purchase."
                ),
                weight=MEDDPICC_DEFAULT_WEIGHTS["economic_buyer"],
                suggested_question="Who owns final budget approval for this project?",
            ),
            "decision_criteria": _dimension(
                label="Decision Criteria",
                description="Customer's stated evaluation and success criteria.",
                extraction_hint=(
                    "Look for explicit buying criteria, required capabilities, "
                    "security needs, compliance requirements, KPIs, or success tests."
                ),
                weight=MEDDPICC_DEFAULT_WEIGHTS["decision_criteria"],
                suggested_question="What criteria will the customer use to choose a solution?",
            ),
            "decision_process": _dimension(
                label="Decision Process",
                description="Known buying, approval, procurement, and signing path.",
                extraction_hint=(
                    "Look for named approval steps, procurement process, legal or "
                    "security review, timeline, stakeholder sequence, or signing owner."
                ),
                weight=MEDDPICC_DEFAULT_WEIGHTS["decision_process"],
                suggested_question="What are the exact steps from evaluation to signature?",
            ),
            "identify_pain": _dimension(
                label="Identify Pain",
                description="Confirmed customer pain, urgency, or cost of inaction.",
                extraction_hint=(
                    "Look for customer-stated pain, operational friction, urgency, "
                    "business loss, manual work, delays, or risk of inaction."
                ),
                weight=MEDDPICC_DEFAULT_WEIGHTS["identify_pain"],
                suggested_question="What happens if the customer does not solve this now?",
                stage_rules=[
                    {
                        "stages": ["proposal", "negotiation"],
                        "gap_threshold": 1,
                        "note": "Late-stage pain can decline when the solution is working.",
                    }
                ],
            ),
            "champion": _dimension(
                label="Champion",
                description="Customer-side advocate with influence and urgency.",
                extraction_hint=(
                    "Look for someone actively selling internally, giving political "
                    "guidance, introducing stakeholders, or helping move the deal forward."
                ),
                weight=MEDDPICC_DEFAULT_WEIGHTS["champion"],
                suggested_question="Who is actively helping this move forward internally?",
            ),
            "competition": _dimension(
                label="Competition",
                description="Known external, internal, or status-quo alternatives.",
                extraction_hint=(
                    "Look for named competitors, internal build options, incumbent "
                    "tools, budget alternatives, status quo, or no-decision risk."
                ),
                weight=MEDDPICC_DEFAULT_WEIGHTS["competition"],
                suggested_question="What alternatives is the customer comparing against?",
            ),
        },
    },
    "simple_b2b": {
        "key": "simple_b2b",
        "display_name": "Simple B2B Qualification",
        "dimensions": {
            "business_need": _dimension(
                label="Business Need",
                description="Clear business problem and urgency.",
                extraction_hint=(
                    "Look for customer-stated business problem, urgency, expected "
                    "benefit, operational blocker, or cost of not acting."
                ),
                suggested_question="What business problem is the customer trying to solve?",
            ),
            "buyer_owner": _dimension(
                label="Buyer Owner",
                description="Known person responsible for decision or budget.",
                extraction_hint=(
                    "Look for named owner, budget holder, approver, sponsor, or "
                    "department leader responsible for moving the deal."
                ),
                suggested_question="Who owns the buying decision?",
            ),
            "next_step": _dimension(
                label="Next Step",
                description="Concrete agreed next action with owner and date.",
                extraction_hint=(
                    "Look for agreed next meeting, requested materials, decision date, "
                    "trial plan, owner, or explicit follow-up action."
                ),
                suggested_question="What is the next agreed action and by when?",
                cta_policy=CTA_POLICY_ALLOWED,
            ),
        },
    },
    "pilot_poc": {
        "key": "pilot_poc",
        "display_name": "Pilot / PoC Qualification",
        "dimensions": {
            "success_criteria": _dimension(
                label="Success Criteria",
                description="Measurable criteria for a successful pilot.",
                extraction_hint=(
                    "Look for pilot KPIs, pass or fail criteria, measurable target, "
                    "acceptance test, or success definition stated by the customer."
                ),
                suggested_question="What must be true for the pilot to be considered successful?",
            ),
            "technical_fit": _dimension(
                label="Technical Fit",
                description="Feasibility with the customer's systems and workflow.",
                extraction_hint=(
                    "Look for integration needs, data access, security constraints, "
                    "workflow fit, implementation blockers, or technical validation."
                ),
                suggested_question="What technical conditions must be met for the pilot?",
            ),
            "pilot_owner": _dimension(
                label="Pilot Owner",
                description="Person accountable for running and evaluating the pilot.",
                extraction_hint=(
                    "Look for named pilot owner, evaluator, project manager, technical "
                    "sponsor, or team responsible for adoption and feedback."
                ),
                suggested_question="Who owns the pilot evaluation?",
            ),
            "conversion_path": _dimension(
                label="Conversion Path",
                description="Path from pilot success to paid rollout or expansion.",
                extraction_hint=(
                    "Look for rollout plan, paid conversion trigger, procurement path, "
                    "budget step, expansion timeline, or post-pilot approval process."
                ),
                suggested_question="If the pilot works, what happens next commercially?",
            ),
        },
    },
    "enterprise_procurement": {
        "key": "enterprise_procurement",
        "display_name": "Enterprise Procurement",
        "dimensions": {
            "business_case": _dimension(
                label="Business Case",
                description="Executive-level ROI and reason to buy.",
                extraction_hint=(
                    "Look for executive value, ROI, financial impact, productivity gain, "
                    "risk reduction, budget justification, or strategic priority."
                ),
                suggested_question="What executive business case justifies this purchase?",
            ),
            "procurement_path": _dimension(
                label="Procurement Path",
                description="Vendor registration, legal, security, and purchasing steps.",
                extraction_hint=(
                    "Look for procurement steps, vendor onboarding, legal review, "
                    "security review, purchasing policy, contract route, or signer."
                ),
                suggested_question="What procurement steps must happen before signature?",
                cta_policy=CTA_POLICY_ALLOWED,
            ),
            "stakeholder_map": _dimension(
                label="Stakeholder Map",
                description="Known decision makers, blockers, users, and influencers.",
                extraction_hint=(
                    "Look for named stakeholders, roles, approvers, blockers, users, "
                    "influencers, executive sponsor, or cross-functional committee."
                ),
                suggested_question="Who influences, approves, blocks, and uses the solution?",
            ),
            "risk_clearance": _dimension(
                label="Risk Clearance",
                description="Security, compliance, legal, or operational risk acceptance.",
                extraction_hint=(
                    "Look for security requirements, compliance concerns, legal terms, "
                    "data governance, risk approval, or operational risk mitigation."
                ),
                suggested_question="What risk reviews must be cleared?",
            ),
        },
    },
    "product_led_sales": {
        "key": "product_led_sales",
        "display_name": "Product-Led Sales",
        "dimensions": {
            "usage_signal": _dimension(
                label="Usage Signal",
                description="Observed product usage or adoption signal.",
                extraction_hint=(
                    "Look for active users, feature usage, activation, frequency, "
                    "workspace growth, trial usage, or product engagement evidence."
                ),
                suggested_question="What usage signal shows real adoption?",
            ),
            "activation_pain": _dimension(
                label="Activation Pain",
                description="Pain or blocker that prevents broader adoption.",
                extraction_hint=(
                    "Look for onboarding friction, activation blocker, missing workflow, "
                    "team adoption issue, admin blocker, or user pain in the product."
                ),
                suggested_question="What is preventing wider adoption?",
            ),
            "expansion_path": _dimension(
                label="Expansion Path",
                description="Clear route from usage to paid expansion.",
                extraction_hint=(
                    "Look for team expansion, paid plan trigger, admin approval, "
                    "seat growth, workspace rollout, or upgrade path."
                ),
                suggested_question="What event would trigger paid expansion?",
            ),
        },
    },
}
