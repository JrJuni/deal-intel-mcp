from __future__ import annotations

from copy import deepcopy

import pytest

from deal_intel.schema.qualification_framework import (
    MEDDPICC_DEFAULT_GAP_THRESHOLD,
    MEDDPICC_DEFAULT_WEIGHTS,
    built_in_qualification_templates,
    get_qualification_template,
    validate_qualification_framework,
)


def _valid_payload() -> dict:
    return get_qualification_template("simple_b2b").model_dump(mode="json")


def _error_text(result: dict) -> str:
    return " ".join(error["message"] for error in result["errors"])


def test_built_in_templates_are_valid() -> None:
    templates = built_in_qualification_templates()

    assert set(templates) == {
        "meddpicc",
        "simple_b2b",
        "pilot_poc",
        "enterprise_procurement",
        "product_led_sales",
    }
    for framework in templates.values():
        result = validate_qualification_framework(framework.model_dump(mode="json"))
        assert result["ok"], result
        assert result["errors"] == []


def test_meddpicc_template_matches_v1_default_weights_and_thresholds() -> None:
    framework = get_qualification_template("meddpicc")

    assert set(framework.dimensions) == set(MEDDPICC_DEFAULT_WEIGHTS)
    for key, expected_weight in MEDDPICC_DEFAULT_WEIGHTS.items():
        dimension = framework.dimensions[key]
        assert dimension.weight == expected_weight
        assert dimension.gap_threshold == MEDDPICC_DEFAULT_GAP_THRESHOLD


@pytest.mark.parametrize(
    ("path", "bad_value"),
    [
        (("key",), "MEDDPICC!"),
        (("dimensions", "business_need", "label"), ""),
        (("dimensions", "business_need", "description"), ""),
        (("dimensions", "business_need", "extraction_hint"), ""),
        (("dimensions", "business_need", "weight"), 0),
        (("dimensions", "business_need", "weight"), -1),
        (("dimensions", "business_need", "weight"), True),
        (("dimensions", "business_need", "weight"), "heavy"),
        (("dimensions", "business_need", "gap_threshold"), -1),
        (("dimensions", "business_need", "gap_threshold"), 6),
        (("dimensions", "business_need", "gap_threshold"), False),
        (("dimensions", "business_need", "cta_policy"), "make_cta"),
    ],
)
def test_validator_rejects_invalid_framework_fields(
    path: tuple[str, ...],
    bad_value: object,
) -> None:
    payload = _valid_payload()
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = bad_value

    result = validate_qualification_framework(payload)

    assert not result["ok"]
    assert result["errors"]


def test_validator_rejects_invalid_dimension_key() -> None:
    payload = _valid_payload()
    payload["dimensions"]["Champion!"] = payload["dimensions"].pop("buyer_owner")

    result = validate_qualification_framework(payload)

    assert not result["ok"]
    assert "snake_case" in _error_text(result)


def test_validator_rejects_framework_with_fewer_than_two_enabled_dimensions() -> None:
    payload = _valid_payload()
    for dimension in payload["dimensions"].values():
        dimension["enabled"] = False
    payload["dimensions"]["business_need"]["enabled"] = True

    result = validate_qualification_framework(payload)

    assert not result["ok"]
    assert "at least two enabled dimensions" in _error_text(result)


def test_validator_rejects_secret_like_strings_without_echoing_secret() -> None:
    payload = _valid_payload()
    secret = "mongodb+srv://user:pass@example.mongodb.net/deal_intel"
    payload["dimensions"]["business_need"]["description"] = secret

    result = validate_qualification_framework(payload)

    assert not result["ok"]
    assert "secret" in _error_text(result)
    assert secret not in _error_text(result)


@pytest.mark.parametrize("hint", ["score this well", "good fit", "assess this"])
def test_validator_rejects_obviously_unscorable_extraction_hints(hint: str) -> None:
    payload = _valid_payload()
    payload["dimensions"]["business_need"]["extraction_hint"] = hint

    result = validate_qualification_framework(payload)

    assert not result["ok"]
    assert "observable evidence" in _error_text(result)


def test_validator_rejects_non_default_score_scale_for_v2() -> None:
    payload = _valid_payload()
    payload["score_scale"] = {"min": 1, "max": 10}

    result = validate_qualification_framework(payload)

    assert not result["ok"]
    assert "0-5" in _error_text(result)


def test_validator_normalizes_observation_by_default_alias() -> None:
    payload = _valid_payload()
    payload["dimensions"]["business_need"]["cta_policy"] = "observation_by_default"

    result = validate_qualification_framework(payload)

    assert result["ok"], result
    dimension = result["framework"]["dimensions"]["business_need"]
    assert dimension["cta_policy"] == "observation_only"


def test_validator_rejects_invalid_stage_rules() -> None:
    payload = _valid_payload()
    payload["dimensions"]["business_need"]["stage_rules"] = [
        {"stages": ["not_a_stage"], "gap_threshold": 2}
    ]

    result = validate_qualification_framework(payload)

    assert not result["ok"]
    assert "invalid stages" in _error_text(result)


def test_validator_warns_when_suggested_question_is_missing() -> None:
    payload = deepcopy(_valid_payload())
    payload["dimensions"]["business_need"]["suggested_question"] = ""

    result = validate_qualification_framework(payload)

    assert result["ok"], result
    assert result["warnings"]
    assert result["warnings"][0]["code"] == "missing_suggested_question"
