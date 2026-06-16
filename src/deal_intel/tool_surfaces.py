from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from deal_intel.config_profiles import infer_config_profile

ToolSurfaceName = Literal["sample", "standard", "developer"]
ToolCategory = Literal[
    "diagnostic",
    "core_read",
    "core_write",
    "admin",
    "local_artifact",
    "user_memory",
    "llm_agent",
    "semantic_search",
    "demo_seed",
]

TOOL_INTENT_GROUP_ORDER: tuple[str, ...] = (
    "setup_and_diagnostics",
    "intake_and_deal_updates",
    "deal_review_and_pipeline",
    "customer_theme_analysis",
    "reports_and_data_exports",
    "qualification_framework_admin",
    "usage_and_memory",
    "optional_llm_and_search",
    "sample_admin",
    "developer_compatibility",
)

TOOL_INTENT_GROUPS: dict[str, dict] = {
    "setup_and_diagnostics": {
        "label": "Setup and diagnostics",
        "purpose": (
            "Check configuration, discover the visible tool surface, and "
            "update safe non-secret settings."
        ),
        "tools": ("config_doctor", "get_tool_catalog", "update_config"),
    },
    "intake_and_deal_updates": {
        "label": "Intake and deal updates",
        "purpose": (
            "Create deals, add customer interactions, and apply user-confirmed "
            "lifecycle or metadata changes."
        ),
        "tools": (
            "create_deal",
            "add_interaction",
            "update_stage",
            "update_deal",
            "archive_deal",
            "restore_deal",
            "delete_deal",
            "migrate_local_data",
        ),
    },
    "deal_review_and_pipeline": {
        "label": "Deal review and pipeline reads",
        "purpose": (
            "Answer current status, risk, missing-info, and KPI questions "
            "without writing data."
        ),
        "tools": (
            "get_deal",
            "list_deals",
            "get_metrics",
            "get_deal_gaps",
            "get_deal_review",
            "get_insights",
        ),
    },
    "customer_theme_analysis": {
        "label": "Customer theme analysis",
        "purpose": (
            "Rank recurring customer concerns, compare them by segment/stage, "
            "and drill into safe evidence snippets."
        ),
        "tools": (
            "get_customer_themes",
            "get_customer_theme_breakdown",
            "get_customer_theme_evidence",
        ),
    },
    "reports_and_data_exports": {
        "label": "Reports and data exports",
        "purpose": (
            "Generate human-facing reports or spreadsheet-ready ledgers from "
            "curated structured data."
        ),
        "tools": ("export_report", "export_data"),
    },
    "qualification_framework_admin": {
        "label": "Qualification framework admin",
        "purpose": "Inspect, validate, switch, and backfill custom deal-qualification frameworks.",
        "tools": (
            "get_qualification_templates",
            "validate_qualification_framework",
            "update_qualification_framework",
            "list_qualification_frameworks",
            "set_active_qualification_framework",
            "delete_qualification_framework",
            "backfill_qualification",
            "backfill_qualification_reextract",
        ),
    },
    "usage_and_memory": {
        "label": "Usage and user memory",
        "purpose": (
            "Review safe LLM usage/cost summaries and read or record durable "
            "user preferences."
        ),
        "tools": ("get_usage", "get_user_memory", "record_user_memory"),
    },
    "optional_llm_and_search": {
        "label": "Optional LLM and semantic search",
        "purpose": (
            "Run semantic similarity search or optional server-side strategy "
            "generation when the user asks for it."
        ),
        "tools": ("search_deals", "analyze_deal"),
    },
    "sample_admin": {
        "label": "Sample data admin",
        "purpose": (
            "Create or delete Atlas demo seed data. Hidden from normal "
            "user-facing surfaces."
        ),
        "tools": ("create_sample_data", "delete_sample_data"),
    },
    "developer_compatibility": {
        "label": "Developer compatibility",
        "purpose": (
            "Temporary compatibility aliases kept for old integrations and "
            "regression tests."
        ),
        "tools": ("add_meeting",),
    },
}

TOOL_SELECTION_GUIDE: tuple[dict, ...] = (
    {
        "intent": "setup_health_check",
        "when_user_asks": "Is this installed correctly? Which tools are loaded?",
        "primary_tool": "config_doctor",
        "then": ["get_tool_catalog if the host only shows a truncated subset"],
    },
    {
        "intent": "one_deal_status",
        "when_user_asks": "What is happening with this deal? What is risky or uncertain?",
        "primary_tool": "get_deal_review",
        "then": [
            "get_deal for raw structured fields",
            "analyze_deal only for optional LLM strategy",
        ],
    },
    {
        "intent": "pipeline_health",
        "when_user_asks": "How healthy is the current pipeline?",
        "primary_tool": "get_metrics",
        "then": ["list_deals for a quick table", "export_report for a meeting-ready report"],
    },
    {
        "intent": "customer_theme_ranking",
        "when_user_asks": (
            "What do customers worry about most? Which decision criteria "
            "appear most often?"
        ),
        "primary_tool": "get_customer_themes",
        "then": [
            "get_customer_theme_breakdown for stage/industry/tag comparison",
            "get_customer_theme_evidence for examples of one theme",
        ],
    },
    {
        "intent": "customer_theme_comparison",
        "when_user_asks": "How do themes differ by stage, industry, industry tag, or dimension?",
        "primary_tool": "get_customer_theme_breakdown",
        "then": ["get_customer_theme_evidence for representative snippets"],
    },
    {
        "intent": "customer_theme_evidence",
        "when_user_asks": (
            "Show examples, evidence, snippets, or source-backed rows for a "
            "known theme."
        ),
        "primary_tool": "get_customer_theme_evidence",
        "then": ["get_customer_themes first if the theme_key is unknown"],
    },
    {
        "intent": "report_or_ledger",
        "when_user_asks": "Make a weekly report, executive summary, CSV, or Excel-ready file.",
        "primary_tool": "export_report",
        "then": ["export_data for spreadsheet ledgers instead of narrative reports"],
    },
)

TOOL_INTENT_ALIASES: dict[str, tuple[str, str]] = {
    "config_doctor": ("config", "config.doctor"),
    "get_tool_catalog": ("catalog", "catalog.tools"),
    "update_config": ("config", "config.update"),
    "get_qualification_templates": ("framework", "framework.templates"),
    "validate_qualification_framework": ("framework", "framework.validate"),
    "update_qualification_framework": ("framework", "framework.update"),
    "list_qualification_frameworks": ("framework", "framework.list"),
    "set_active_qualification_framework": ("framework", "framework.activate"),
    "delete_qualification_framework": ("framework", "framework.delete"),
    "backfill_qualification": ("framework", "framework.backfill"),
    "backfill_qualification_reextract": ("framework", "framework.reextract"),
    "create_deal": ("deal", "deal.create"),
    "add_meeting": ("compat", "compat.add_meeting"),
    "add_interaction": ("interaction", "interaction.add"),
    "update_stage": ("deal", "deal.stage.update"),
    "update_deal": ("deal", "deal.update"),
    "archive_deal": ("deal", "deal.archive"),
    "restore_deal": ("deal", "deal.restore"),
    "delete_deal": ("deal", "deal.delete"),
    "migrate_local_data": ("data", "data.migrate"),
    "create_sample_data": ("sample", "sample.create"),
    "delete_sample_data": ("sample", "sample.delete"),
    "get_deal": ("deal", "deal.get"),
    "list_deals": ("deal", "deal.list"),
    "get_insights": ("pipeline", "pipeline.insights"),
    "get_metrics": ("pipeline", "pipeline.metrics"),
    "get_deal_gaps": ("deal", "deal.gaps"),
    "get_deal_review": ("deal", "deal.review"),
    "get_usage": ("usage", "usage.cost"),
    "export_report": ("report", "report.export"),
    "export_data": ("data", "data.export"),
    "get_user_memory": ("memory", "memory.get"),
    "record_user_memory": ("memory", "memory.record"),
    "get_customer_themes": ("theme", "theme.rank"),
    "get_customer_theme_breakdown": ("theme", "theme.compare"),
    "get_customer_theme_evidence": ("theme", "theme.evidence"),
    "search_deals": ("search", "search.deals"),
    "analyze_deal": ("strategy", "strategy.analyze"),
}


@dataclass(frozen=True)
class MCPToolSurfaceContract:
    name: str
    category: ToolCategory
    surfaces: tuple[ToolSurfaceName, ...]
    user_facing: bool
    db_writes: bool
    llm_calls: bool
    local_file_writes: bool = False
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "surfaces": list(self.surfaces),
            "user_facing": self.user_facing,
            "db_writes": self.db_writes,
            "llm_calls": self.llm_calls,
            "local_file_writes": self.local_file_writes,
            "notes": self.notes,
        }


_SAMPLE: tuple[ToolSurfaceName, ...] = ("sample", "standard", "developer")
_STANDARD: tuple[ToolSurfaceName, ...] = ("standard", "developer")
_DEVELOPER: tuple[ToolSurfaceName, ...] = ("developer",)


MCP_TOOL_SURFACE_CONTRACTS: tuple[MCPToolSurfaceContract, ...] = (
    MCPToolSurfaceContract(
        name="config_doctor",
        category="diagnostic",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        notes="Safe setup diagnosis. May perform bounded storage ping.",
    ),
    MCPToolSurfaceContract(
        name="get_tool_catalog",
        category="diagnostic",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        notes=(
            "Lists the current MCP tool surface and guidance for each tool; "
            "use when host tool search only returns a truncated subset."
        ),
    ),
    MCPToolSurfaceContract(
        name="update_config",
        category="diagnostic",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        local_file_writes=True,
        notes=(
            "Dry-run-first updates for safe non-secret user-config fields; "
            "does not accept MongoDB URIs or API keys."
        ),
    ),
    MCPToolSurfaceContract(
        name="get_qualification_templates",
        category="diagnostic",
        surfaces=_STANDARD,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        notes=(
            "Lists built-in framework templates for MEDDPICC and custom deal "
            "qualification models. No config writes."
        ),
    ),
    MCPToolSurfaceContract(
        name="validate_qualification_framework",
        category="diagnostic",
        surfaces=_STANDARD,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        notes=(
            "Validates a template or JSON/YAML framework payload before config "
            "writes. Rejects secret-shaped strings."
        ),
    ),
    MCPToolSurfaceContract(
        name="update_qualification_framework",
        category="admin",
        surfaces=_STANDARD,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        local_file_writes=True,
        notes=(
            "Dry-run-first user-config write for custom qualification.frameworks "
            "and qualification.active_framework; built-in presets are immutable."
        ),
    ),
    MCPToolSurfaceContract(
        name="list_qualification_frameworks",
        category="diagnostic",
        surfaces=_STANDARD,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        notes=(
            "Lists built-in and user-configured qualification frameworks and "
            "the currently active framework. No config writes."
        ),
    ),
    MCPToolSurfaceContract(
        name="set_active_qualification_framework",
        category="admin",
        surfaces=_STANDARD,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        local_file_writes=True,
        notes=(
            "Dry-run-first user-config write for qualification.active_framework; "
            "does not recompute existing deals."
        ),
    ),
    MCPToolSurfaceContract(
        name="delete_qualification_framework",
        category="admin",
        surfaces=_STANDARD,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        local_file_writes=True,
        notes=(
            "Dry-run-first deletion for stored custom frameworks only; built-ins "
            "and active frameworks are protected."
        ),
    ),
    MCPToolSurfaceContract(
        name="backfill_qualification",
        category="admin",
        surfaces=_STANDARD,
        user_facing=True,
        db_writes=True,
        llm_calls=False,
        notes=(
            "Dry-run-first recompute of current qualification snapshots from "
            "stored evidence. Does not read raw content or call LLMs."
        ),
    ),
    MCPToolSurfaceContract(
        name="backfill_qualification_reextract",
        category="admin",
        surfaces=_STANDARD,
        user_facing=True,
        db_writes=True,
        llm_calls=True,
        notes=(
            "Dry-run-first maintenance path that may read historical raw "
            "interaction content and call LLMs in apply mode; responses never "
            "return raw content."
        ),
    ),
    MCPToolSurfaceContract(
        name="create_deal",
        category="core_write",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=True,
        llm_calls=False,
        notes="Safe in sample after local personal storage is active.",
    ),
    MCPToolSurfaceContract(
        name="add_meeting",
        category="core_write",
        surfaces=_DEVELOPER,
        user_facing=False,
        db_writes=True,
        llm_calls=True,
        notes=(
            "Deprecated compatibility alias for add_interaction with "
            "interaction_type='meeting'. Kept temporarily for developer "
            "compatibility tests; new integrations should not call it."
        ),
    ),
    MCPToolSurfaceContract(
        name="add_interaction",
        category="core_write",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=True,
        llm_calls=True,
        notes=(
            "Adds meeting/email/interview/call/internal interaction content "
            "with source metadata through canonical interaction storage."
        ),
    ),
    MCPToolSurfaceContract(
        name="update_stage",
        category="core_write",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=True,
        llm_calls=False,
        notes="Safe in sample after local personal storage is active.",
    ),
    MCPToolSurfaceContract(
        name="update_deal",
        category="admin",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=True,
        llm_calls=False,
        notes="Requires explicit user confirmation.",
    ),
    MCPToolSurfaceContract(
        name="archive_deal",
        category="admin",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=True,
        llm_calls=False,
        notes="Requires explicit user confirmation and exact company match.",
    ),
    MCPToolSurfaceContract(
        name="restore_deal",
        category="admin",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=True,
        llm_calls=False,
        notes="Requires explicit user confirmation and exact company match.",
    ),
    MCPToolSurfaceContract(
        name="delete_deal",
        category="admin",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=True,
        llm_calls=False,
        notes="Dry-run by default; actual delete requires archived deal.",
    ),
    MCPToolSurfaceContract(
        name="migrate_local_data",
        category="admin",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=True,
        llm_calls=False,
        notes="Dry-run-first local personal deals to MongoDB graduation path.",
    ),
    MCPToolSurfaceContract(
        name="create_sample_data",
        category="demo_seed",
        surfaces=_DEVELOPER,
        user_facing=False,
        db_writes=True,
        llm_calls=False,
        notes="Atlas demo-database seeding; not bundled local sample mode.",
    ),
    MCPToolSurfaceContract(
        name="delete_sample_data",
        category="demo_seed",
        surfaces=_DEVELOPER,
        user_facing=False,
        db_writes=True,
        llm_calls=False,
        notes="Atlas demo-database cleanup; dry-run by default.",
    ),
    MCPToolSurfaceContract(
        name="get_deal",
        category="core_read",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        notes="Sample mode reads bundled fictional data.",
    ),
    MCPToolSurfaceContract(
        name="list_deals",
        category="core_read",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
    ),
    MCPToolSurfaceContract(
        name="get_insights",
        category="core_read",
        surfaces=_STANDARD,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        notes="Legacy insight variants are Mongo aggregation oriented.",
    ),
    MCPToolSurfaceContract(
        name="get_metrics",
        category="core_read",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
    ),
    MCPToolSurfaceContract(
        name="get_deal_gaps",
        category="core_read",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
    ),
    MCPToolSurfaceContract(
        name="get_deal_review",
        category="core_read",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
    ),
    MCPToolSurfaceContract(
        name="get_usage",
        category="core_read",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        notes=(
            "Read-only summary of persisted server-side LLM token usage and "
            "safe cost estimates."
        ),
    ),
    MCPToolSurfaceContract(
        name="export_report",
        category="local_artifact",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        local_file_writes=True,
        notes=(
            "Writes local human-facing report artifacts; spreadsheet ledgers "
            "should use export_data."
        ),
    ),
    MCPToolSurfaceContract(
        name="export_data",
        category="local_artifact",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        local_file_writes=True,
        notes=(
            "Writes spreadsheet-ready CSV datasets without raw notes, emails, "
            "contacts, vectors, database writes, or LLM calls."
        ),
    ),
    MCPToolSurfaceContract(
        name="get_user_memory",
        category="user_memory",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        notes="Reads constrained user memory Markdown files for context loading.",
    ),
    MCPToolSurfaceContract(
        name="record_user_memory",
        category="user_memory",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        local_file_writes=True,
        notes=(
            "Appends durable user feedback to safe user memory Markdown files; "
            "rejects secret-shaped content."
        ),
    ),
    MCPToolSurfaceContract(
        name="get_customer_themes",
        category="core_read",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        notes=(
            "Ranking entry point for customer concerns and decision criteria; "
            "uses the restricted metrics projection."
        ),
    ),
    MCPToolSurfaceContract(
        name="get_customer_theme_breakdown",
        category="core_read",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
    ),
    MCPToolSurfaceContract(
        name="get_customer_theme_evidence",
        category="core_read",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
    ),
    MCPToolSurfaceContract(
        name="search_deals",
        category="semantic_search",
        surfaces=_STANDARD,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        notes="Requires Mongo-backed embeddings or Atlas Vector Search.",
    ),
    MCPToolSurfaceContract(
        name="analyze_deal",
        category="llm_agent",
        surfaces=_STANDARD,
        user_facing=True,
        db_writes=True,
        llm_calls=True,
        notes="LLM analysis may persist bd_strategy.",
    ),
)


def surface_names() -> tuple[ToolSurfaceName, ...]:
    return ("sample", "standard", "developer")


def list_tool_surface_contracts() -> list[MCPToolSurfaceContract]:
    return list(MCP_TOOL_SURFACE_CONTRACTS)


def get_tool_surface_contract(tool_name: str) -> MCPToolSurfaceContract:
    for contract in MCP_TOOL_SURFACE_CONTRACTS:
        if contract.name == tool_name:
            return contract
    raise ValueError(f"unknown MCP tool: {tool_name}")


def tool_names_for_surface(surface: str) -> tuple[str, ...]:
    normalized = _normalize_surface(surface)
    return tuple(
        contract.name
        for contract in MCP_TOOL_SURFACE_CONTRACTS
        if normalized in contract.surfaces
    )


def resolve_tool_surface(cfg: dict) -> ToolSurfaceName:
    tools = _mapping(cfg.get("tools"))
    configured = tools.get("surface", "auto")
    if configured is None or configured == "":
        configured = "auto"
    if not isinstance(configured, str):
        raise ValueError("tools.surface must be auto, sample, standard, or developer")
    normalized = configured.strip().lower()
    if normalized == "auto":
        return default_surface_for_profile(infer_config_profile(cfg))
    return _normalize_surface(normalized)


def tool_names_for_config(cfg: dict) -> tuple[str, ...]:
    return tool_names_for_surface(resolve_tool_surface(cfg))


def default_surface_for_profile(profile: str) -> ToolSurfaceName:
    normalized = profile.strip().lower()
    if normalized == "sample":
        return "sample"
    if normalized in {"full", "pro", "custom"}:
        return "standard"
    raise ValueError("profile must be one of: sample, full, pro, custom")


def build_tool_surface_matrix() -> dict:
    contracts = [contract.to_dict() for contract in MCP_TOOL_SURFACE_CONTRACTS]
    return {
        "surfaces": {
            surface: list(tool_names_for_surface(surface))
            for surface in surface_names()
        },
        "sample_local_personal_target": list(
            sample_local_personal_target_tool_names()
        ),
        "tools": contracts,
        "default_surface_by_profile": {
            "sample": default_surface_for_profile("sample"),
            "full": default_surface_for_profile("full"),
            "pro": default_surface_for_profile("pro"),
            "custom": default_surface_for_profile("custom"),
        },
    }


def build_tool_intent_groups(tool_names: set[str] | frozenset[str]) -> dict:
    visible = set(tool_names)
    groups: dict[str, dict] = {}
    for group_name in TOOL_INTENT_GROUP_ORDER:
        group = TOOL_INTENT_GROUPS[group_name]
        tools = [tool for tool in group["tools"] if tool in visible]
        if not tools:
            continue
        groups[group_name] = {
            "label": group["label"],
            "purpose": group["purpose"],
            "tools": tools,
        }
    return groups


def build_tool_selection_guide(tool_names: set[str] | frozenset[str]) -> list[dict]:
    visible = set(tool_names)
    guide = []
    for entry in TOOL_SELECTION_GUIDE:
        primary_tool = entry["primary_tool"]
        if primary_tool not in visible:
            continue
        guide.append(
            {
                **entry,
                "intent_alias": tool_intent_metadata(primary_tool)["intent_alias"],
                "primary_tool_visible": True,
                "related_visible_tools": [
                    tool_name for tool_name in _tools_mentioned(entry) if tool_name in visible
                ],
            }
        )
    return guide


def tool_intent_metadata(tool_name: str) -> dict:
    namespace, intent_alias = TOOL_INTENT_ALIASES.get(
        tool_name, ("uncategorized", tool_name)
    )
    return {
        "canonical_tool": tool_name,
        "namespace": namespace,
        "intent_alias": intent_alias,
    }


def build_tool_alias_map(tool_names: set[str] | frozenset[str]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for tool_name in sorted(tool_names):
        metadata = tool_intent_metadata(tool_name)
        aliases[metadata["intent_alias"]] = metadata["canonical_tool"]
    return aliases


def sample_local_personal_target_tool_names() -> tuple[str, ...]:
    """Backward-compatible alias for the now-current sample tool set."""
    return tool_names_for_surface("sample")


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _normalize_surface(surface: str) -> ToolSurfaceName:
    normalized = surface.strip().lower()
    if normalized not in surface_names():
        raise ValueError("surface must be one of: sample, standard, developer")
    return cast(ToolSurfaceName, normalized)


def _tools_mentioned(entry: dict) -> list[str]:
    names = []
    for value in entry.get("then", []):
        if not isinstance(value, str):
            continue
        for contract in MCP_TOOL_SURFACE_CONTRACTS:
            if contract.name in value:
                names.append(contract.name)
    return names
