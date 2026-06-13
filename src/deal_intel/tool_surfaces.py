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
        name="export_report",
        category="local_artifact",
        surfaces=_SAMPLE,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        local_file_writes=True,
        notes="Writes local CSV/Markdown artifacts, not database records.",
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
        surfaces=_STANDARD,
        user_facing=True,
        db_writes=False,
        llm_calls=False,
        notes="Uses legacy Mongo aggregate path; sample mode uses breakdown/evidence.",
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
