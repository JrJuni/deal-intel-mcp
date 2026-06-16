from __future__ import annotations


def customer_theme_workflow_step(step: str) -> dict:
    """Return stable tool-selection guidance for customer-theme analysis."""
    if step == "ranking":
        return {
            "workflow_id": "customer_theme_analysis",
            "current_step": "ranking",
            "current_tool": "get_customer_themes",
            "use_for": (
                "Rank recurring customer concerns, pains, metrics, or decision "
                "criteria by unique deal count."
            ),
            "next_tools": [
                {
                    "tool": "get_customer_theme_breakdown",
                    "when": (
                        "Compare the ranked themes by stage, industry, "
                        "industry_tag, or dimension."
                    ),
                },
                {
                    "tool": "get_customer_theme_evidence",
                    "when": (
                        "Show source-backed examples for a specific theme_key "
                        "from the ranking."
                    ),
                },
            ],
        }
    if step == "comparison":
        return {
            "workflow_id": "customer_theme_analysis",
            "current_step": "comparison",
            "current_tool": "get_customer_theme_breakdown",
            "use_for": (
                "Compare customer theme patterns across stage, primary "
                "industry, industry tags, or theme dimensions."
            ),
            "previous_tools": ["get_customer_themes"],
            "next_tools": [
                {
                    "tool": "get_customer_theme_evidence",
                    "when": "Show examples for one theme_key that appears in a group.",
                }
            ],
        }
    if step == "evidence":
        return {
            "workflow_id": "customer_theme_analysis",
            "current_step": "evidence_drilldown",
            "current_tool": "get_customer_theme_evidence",
            "use_for": (
                "Return curated evidence snippets and safe source metadata for "
                "one known theme_key."
            ),
            "previous_tools": [
                "get_customer_themes",
                "get_customer_theme_breakdown",
            ],
            "next_tools": [],
        }
    raise ValueError(f"unknown customer theme workflow step: {step}")
