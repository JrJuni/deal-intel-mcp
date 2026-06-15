from __future__ import annotations

import json

import yaml

from deal_intel import _context, _env, mcp_server
from deal_intel.qualification_config import (
    build_qualification_templates_payload,
    delete_qualification_framework_config,
    list_qualification_frameworks_config,
    resolve_active_qualification_framework,
    set_active_qualification_framework_config,
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


def test_resolve_active_qualification_framework_defaults_to_meddpicc() -> None:
    framework = resolve_active_qualification_framework({})

    assert framework.key == "meddpicc"
    assert framework.display_name == "MEDDPICC"


def test_resolve_active_meddpicc_ignores_legacy_weight_overrides_for_preset() -> None:
    framework = resolve_active_qualification_framework(
        {
            "meddpicc": {
                "weights": {"champion": 3.0},
                "gap_threshold": 1,
            }
        }
    )

    assert framework.key == "meddpicc"
    assert framework.dimensions["champion"].weight == 2.0
    assert framework.dimensions["metrics"].weight == 1.0
    assert {dimension.gap_threshold for dimension in framework.dimensions.values()} == {2}


def test_resolve_active_qualification_framework_uses_built_in_active_template() -> None:
    framework = resolve_active_qualification_framework(
        {"qualification": {"active_framework": "simple_b2b"}}
    )

    assert framework.key == "simple_b2b"
    assert sorted(framework.dimensions) == [
        "business_need",
        "buyer_owner",
        "next_step",
    ]


def test_resolve_active_qualification_framework_uses_configured_framework() -> None:
    payload = validate_framework_input(template_key="simple_b2b")["framework"]
    payload["key"] = "custom_simple"
    payload["display_name"] = "Custom Simple"

    framework = resolve_active_qualification_framework(
        {
            "qualification": {
                "active_framework": "custom_simple",
                "frameworks": {"custom_simple": payload},
            }
        }
    )

    assert framework.key == "custom_simple"
    assert framework.display_name == "Custom Simple"


def test_resolve_active_qualification_framework_ignores_preset_key_override() -> None:
    payload = validate_framework_input(template_key="meddpicc")["framework"]
    payload["dimensions"]["champion"]["weight"] = 4.0

    framework = resolve_active_qualification_framework(
        {
            "meddpicc": {"weights": {"champion": 1.0}},
            "qualification": {
                "active_framework": "meddpicc",
                "frameworks": {"meddpicc": payload},
            },
        }
    )

    assert framework.key == "meddpicc"
    assert framework.dimensions["champion"].weight == 2.0


def test_resolve_active_qualification_framework_rejects_missing_active_framework() -> None:
    try:
        resolve_active_qualification_framework(
            {"qualification": {"active_framework": "missing_framework"}}
        )
    except ValueError as exc:
        assert "missing_framework" in str(exc)
    else:
        raise AssertionError("missing active framework should fail")


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
        "qualification.active_framework",
    ]
    assert result["preset_immutable"] is True
    assert result["stores_framework"] is False
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
    assert data["qualification"]["frameworks"] == {}
    assert result["preset_immutable"] is True
    assert result["stores_framework"] is False


def test_update_qualification_framework_can_copy_template_to_custom_framework(
    tmp_path,
) -> None:
    result = update_qualification_framework_config(
        config_path=tmp_path / "config.yaml",
        template_key="enterprise_procurement",
        copy_as_key="custom_enterprise_procurement",
        copy_display_name="Custom Enterprise Procurement",
        dry_run=False,
        confirmed_by_user=True,
    )

    data = _load(tmp_path / "config.yaml")
    assert result["ok"] is True
    assert result["changed_fields"] == [
        {
            "field": "qualification.frameworks.custom_enterprise_procurement",
            "changed": True,
        },
        {"field": "qualification.active_framework", "changed": True},
    ]
    assert result["source"] == "template_copy"
    assert result["template_key"] == "enterprise_procurement"
    assert result["copy_as_key"] == "custom_enterprise_procurement"
    assert data["qualification"]["active_framework"] == "custom_enterprise_procurement"
    assert data["qualification"]["frameworks"]["custom_enterprise_procurement"][
        "display_name"
    ] == "Custom Enterprise Procurement"


def test_update_qualification_framework_noops_when_template_not_activated(
    tmp_path,
) -> None:
    result = update_qualification_framework_config(
        config_path=tmp_path / "config.yaml",
        template_key="enterprise_procurement",
        set_active=False,
        dry_run=False,
        confirmed_by_user=True,
    )

    assert result["ok"] is True
    assert result["changed_fields"] == []
    assert result["stores_framework"] is False
    assert (tmp_path / "config.yaml").exists() is False


def test_update_qualification_framework_rejects_preset_key_framework_json(
    tmp_path,
) -> None:
    framework = validate_framework_input(template_key="meddpicc")["framework"]
    framework["display_name"] = "Mutated MEDDPICC"

    result = update_qualification_framework_config(
        config_path=tmp_path / "config.yaml",
        framework_json=json.dumps(framework),
    )

    assert result["ok"] is False
    assert result["error_code"] == "PRESET_FRAMEWORK_IMMUTABLE"
    assert result["framework_key"] == "meddpicc"
    assert "copy_as_key" in result["copy_hint"]
    assert (tmp_path / "config.yaml").exists() is False


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


def test_list_qualification_frameworks_reports_built_ins_and_active_default() -> None:
    result = list_qualification_frameworks_config(cfg={})

    assert result["ok"] is True
    assert result["active_framework"] == "meddpicc"
    assert result["active_framework_defined"] is True
    assert result["available_frameworks"] == [
        "enterprise_procurement",
        "meddpicc",
        "pilot_poc",
        "product_led_sales",
        "simple_b2b",
    ]
    meddpicc = next(
        framework for framework in result["frameworks"] if framework["key"] == "meddpicc"
    )
    assert meddpicc["source"] == "built_in"
    assert meddpicc["active"] is True
    assert "dimensions" not in meddpicc


def test_list_qualification_frameworks_includes_saved_custom_framework() -> None:
    custom = validate_framework_input(template_key="simple_b2b")["framework"]
    custom["key"] = "custom_simple"
    custom["display_name"] = "Custom Simple"

    result = list_qualification_frameworks_config(
        cfg={
            "qualification": {
                "active_framework": "custom_simple",
                "frameworks": {"custom_simple": custom},
            }
        },
        include_dimensions=True,
    )

    saved = next(
        framework
        for framework in result["frameworks"]
        if framework["key"] == "custom_simple"
    )
    assert result["active_framework"] == "custom_simple"
    assert saved["source"] == "user_config"
    assert saved["active"] is True
    assert saved["valid"] is True
    assert "dimensions" in saved


def test_list_qualification_frameworks_marks_preset_overrides_as_ignored() -> None:
    override = validate_framework_input(template_key="meddpicc")["framework"]
    override["display_name"] = "Mutated MEDDPICC"

    result = list_qualification_frameworks_config(
        cfg={
            "qualification": {
                "active_framework": "meddpicc",
                "frameworks": {"meddpicc": override},
            }
        },
    )

    meddpicc = next(
        framework for framework in result["frameworks"] if framework["key"] == "meddpicc"
    )
    assert meddpicc["source"] == "built_in"
    assert meddpicc["display_name"] == "MEDDPICC"
    assert meddpicc["stored_override_ignored"] is True
    assert {
        warning["code"] for warning in result["warnings"]
    } == {"preset_overrides_ignored"}


def test_set_active_qualification_framework_dry_run_and_apply(tmp_path) -> None:
    user_config = tmp_path / "config.yaml"
    user_config.write_text(
        "qualification:\n"
        "  active_framework: meddpicc\n",
        encoding="utf-8",
    )

    dry_run = set_active_qualification_framework_config(
        config_path=user_config,
        framework_key="simple_b2b",
    )
    assert dry_run["ok"] is True
    assert dry_run["dry_run"] is True
    assert dry_run["storage_written"] is False
    assert dry_run["changed_fields"][0]["before"] == "meddpicc"
    assert _load(user_config)["qualification"]["active_framework"] == "meddpicc"

    result = set_active_qualification_framework_config(
        config_path=user_config,
        framework_key="simple_b2b",
        dry_run=False,
        confirmed_by_user=True,
        timestamp="20260615-020304",
    )

    data = _load(user_config)
    backup = tmp_path / "config.yaml.bak.20260615-020304"
    assert result["ok"] is True
    assert result["storage_written"] is True
    assert result["backup_written"] is True
    assert backup.exists()
    assert data["qualification"]["active_framework"] == "simple_b2b"


def test_set_active_qualification_framework_rejects_unknown_key(tmp_path) -> None:
    result = set_active_qualification_framework_config(
        config_path=tmp_path / "config.yaml",
        framework_key="missing",
    )

    assert result["ok"] is False
    assert result["error_code"] == "UNKNOWN_FRAMEWORK"
    assert "meddpicc" in result["available_frameworks"]


def test_delete_qualification_framework_deletes_only_inactive_custom(tmp_path) -> None:
    user_config = tmp_path / "config.yaml"
    custom = validate_framework_input(template_key="simple_b2b")["framework"]
    custom["key"] = "custom_simple"
    custom["display_name"] = "Custom Simple"
    user_config.write_text(
        yaml.safe_dump(
            {
                "qualification": {
                    "active_framework": "meddpicc",
                    "frameworks": {"custom_simple": custom},
                }
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    dry_run = delete_qualification_framework_config(
        config_path=user_config,
        framework_key="custom_simple",
    )
    assert dry_run["ok"] is True
    assert dry_run["storage_written"] is False
    assert "custom_simple" in _load(user_config)["qualification"]["frameworks"]

    result = delete_qualification_framework_config(
        config_path=user_config,
        framework_key="custom_simple",
        dry_run=False,
        confirmed_by_user=True,
        timestamp="20260615-030405",
    )

    data = _load(user_config)
    assert result["ok"] is True
    assert result["storage_written"] is True
    assert result["backup_written"] is True
    assert "custom_simple" not in data["qualification"]["frameworks"]


def test_delete_qualification_framework_rejects_built_in_or_active_custom(tmp_path) -> None:
    custom = validate_framework_input(template_key="simple_b2b")["framework"]
    custom["key"] = "custom_simple"
    user_config = tmp_path / "config.yaml"
    user_config.write_text(
        yaml.safe_dump(
            {
                "qualification": {
                    "active_framework": "custom_simple",
                    "frameworks": {"custom_simple": custom},
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    built_in = delete_qualification_framework_config(
        config_path=user_config,
        framework_key="meddpicc",
    )
    active_custom = delete_qualification_framework_config(
        config_path=user_config,
        framework_key="custom_simple",
    )

    assert built_in["ok"] is False
    assert built_in["error_code"] == "BUILT_IN_FRAMEWORK_NOT_DELETABLE"
    assert active_custom["ok"] is False
    assert active_custom["error_code"] == "ACTIVE_FRAMEWORK_NOT_DELETABLE"


def test_delete_qualification_framework_can_remove_stored_preset_override(
    tmp_path,
) -> None:
    override = validate_framework_input(template_key="meddpicc")["framework"]
    override["display_name"] = "Mutated MEDDPICC"
    user_config = tmp_path / "config.yaml"
    user_config.write_text(
        yaml.safe_dump(
            {
                "qualification": {
                    "active_framework": "meddpicc",
                    "frameworks": {"meddpicc": override},
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = delete_qualification_framework_config(
        config_path=user_config,
        framework_key="meddpicc",
        dry_run=False,
        confirmed_by_user=True,
    )

    data = _load(user_config)
    assert result["ok"] is True
    assert result["active_framework_preserved"] is True
    assert result["deleted_framework"]["display_name"] == "Mutated MEDDPICC"
    assert "meddpicc" not in data["qualification"]["frameworks"]
    assert data["qualification"]["active_framework"] == "meddpicc"


def test_mcp_qualification_framework_wrappers_use_shared_helpers(
    monkeypatch,
    tmp_path,
) -> None:
    user_config = tmp_path / "config.yaml"
    monkeypatch.setattr(_env, "_USER_CONFIG_PATH", user_config)
    monkeypatch.setattr(_context, "config", lambda: {})

    templates = mcp_server.get_qualification_templates(template_key="meddpicc")
    validation = mcp_server.validate_qualification_framework(template_key="meddpicc")
    update = mcp_server.update_qualification_framework(template_key="meddpicc")
    frameworks = mcp_server.list_qualification_frameworks()
    set_active = mcp_server.set_active_qualification_framework(
        framework_key="simple_b2b"
    )
    delete = mcp_server.delete_qualification_framework(framework_key="meddpicc")

    assert templates["ok"] is True
    assert templates["templates"][0]["key"] == "meddpicc"
    assert validation["ok"] is True
    assert validation["framework"]["key"] == "meddpicc"
    assert update["ok"] is True
    assert update["dry_run"] is True
    assert frameworks["ok"] is True
    assert frameworks["active_framework"] == "meddpicc"
    assert set_active["ok"] is True
    assert set_active["dry_run"] is True
    assert delete["ok"] is False
    assert delete["error_code"] == "BUILT_IN_FRAMEWORK_NOT_DELETABLE"
    assert user_config.exists() is False
