from __future__ import annotations

import json

import yaml

from deal_intel import _env, mcp_server
from deal_intel.qualification_config import (
    build_qualification_templates_payload,
    update_qualification_framework_config,
    validate_framework_input,
)


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_get_qualification_templates_lists_safe_built_ins() -> None:
    result = build_qualification_templates_payload()

    assert result["ok"] is True
    assert result["available_templates"] == [
        "enterprise_procurement",
        "meddpicc",
        "pilot_poc",
        "product_led_sales",
        "simple_b2b",
    ]
    assert result["template_count"] == 5
    assert all("dimensions" in template for template in result["templates"])
    assert "validate_qualification_framework" in result["usage_hint"]


def test_get_qualification_templates_can_return_summary_only() -> None:
    result = build_qualification_templates_payload(
        template_key="meddpicc",
        include_dimensions=False,
    )

    assert result["ok"] is True
    assert result["template_count"] == 1
    assert result["templates"][0]["key"] == "meddpicc"
    assert "dimensions" not in result["templates"][0]


def test_validate_framework_input_accepts_template_or_json() -> None:
    template = validate_framework_input(template_key="simple_b2b")
    framework_json = json.dumps(template["framework"])
    custom = validate_framework_input(framework_json=framework_json)

    assert template["ok"] is True
    assert template["source"] == "template"
    assert custom["ok"] is True
    assert custom["source"] == "framework_json"
    assert custom["framework"]["key"] == "simple_b2b"


def test_validate_framework_input_rejects_ambiguous_or_missing_input() -> None:
    both = validate_framework_input(
        template_key="simple_b2b",
        framework_json='{"key":"custom"}',
    )
    missing = validate_framework_input()

    assert both["ok"] is False
    assert both["error_code"] == "INVALID_INPUT"
    assert missing["ok"] is False
    assert missing["error_code"] == "INVALID_INPUT"


def test_update_qualification_framework_dry_run_does_not_write(tmp_path) -> None:
    user_config = tmp_path / "config.yaml"

    result = update_qualification_framework_config(
        config_path=user_config,
        template_key="simple_b2b",
    )

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["storage_written"] is False
    assert result["restart_required"] is True
    assert [change["field"] for change in result["changed_fields"]] == [
        "qualification.frameworks.simple_b2b",
        "qualification.active_framework",
    ]
    assert user_config.exists() is False


def test_update_qualification_framework_requires_confirmation(tmp_path) -> None:
    user_config = tmp_path / "config.yaml"

    result = update_qualification_framework_config(
        config_path=user_config,
        template_key="simple_b2b",
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["error_code"] == "REQUIRES_CONFIRMATION"
    assert result["storage_written"] is False
    assert user_config.exists() is False


def test_update_qualification_framework_writes_and_backs_up_existing_config(tmp_path) -> None:
    user_config = tmp_path / "config.yaml"
    user_config.write_text(
        "llm:\n"
        "  provider: chatgpt_oauth\n"
        "custom:\n"
        "  keep: true\n",
        encoding="utf-8",
    )

    result = update_qualification_framework_config(
        config_path=user_config,
        template_key="pilot_poc",
        dry_run=False,
        confirmed_by_user=True,
        timestamp="20260615-010203",
    )

    backup = tmp_path / "config.yaml.bak.20260615-010203"
    data = _load(user_config)
    assert result["ok"] is True
    assert result["storage_written"] is True
    assert result["backup_written"] is True
    assert result["backup_path"] == str(backup)
    assert backup.exists()
    assert data["custom"]["keep"] is True
    assert data["qualification"]["active_framework"] == "pilot_poc"
    assert data["qualification"]["frameworks"]["pilot_poc"]["display_name"] == (
        "Pilot / PoC Qualification"
    )


def test_update_qualification_framework_can_store_without_setting_active(tmp_path) -> None:
    result = update_qualification_framework_config(
        config_path=tmp_path / "config.yaml",
        template_key="enterprise_procurement",
        set_active=False,
        dry_run=False,
        confirmed_by_user=True,
    )

    data = _load(tmp_path / "config.yaml")
    assert result["ok"] is True
    assert result["changed_fields"] == [
        {"field": "qualification.frameworks.enterprise_procurement", "changed": True}
    ]
    assert "active_framework" not in data["qualification"]


def test_update_qualification_framework_rejects_invalid_payload_without_echoing_secret(
    tmp_path,
) -> None:
    framework = validate_framework_input(template_key="simple_b2b")["framework"]
    secret = "mongodb+srv://user:pass@example.mongodb.net/deal_intel"
    framework["dimensions"]["business_need"]["description"] = secret

    result = update_qualification_framework_config(
        config_path=tmp_path / "config.yaml",
        framework_json=json.dumps(framework),
    )

    serialized = json.dumps(result, ensure_ascii=False)
    assert result["ok"] is False
    assert result["error_code"] == "INVALID_FRAMEWORK"
    assert "secret" in serialized
    assert secret not in serialized
    assert (tmp_path / "config.yaml").exists() is False


def test_update_qualification_framework_rejects_invalid_existing_config(tmp_path) -> None:
    user_config = tmp_path / "config.yaml"
    user_config.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    result = update_qualification_framework_config(
        config_path=user_config,
        template_key="simple_b2b",
    )

    assert result["ok"] is False
    assert result["error_code"] == "CONFIG_INVALID"


def test_mcp_qualification_framework_wrappers_use_shared_helpers(
    monkeypatch,
    tmp_path,
) -> None:
    user_config = tmp_path / "config.yaml"
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", user_config)

    templates = mcp_server.get_qualification_templates(template_key="meddpicc")
    validation = mcp_server.validate_qualification_framework(template_key="meddpicc")
    update = mcp_server.update_qualification_framework(template_key="meddpicc")

    assert templates["ok"] is True
    assert templates["templates"][0]["key"] == "meddpicc"
    assert validation["ok"] is True
    assert validation["framework"]["key"] == "meddpicc"
    assert update["ok"] is True
    assert update["dry_run"] is True
    assert user_config.exists() is False
