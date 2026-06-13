from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import NotFoundError

import deal_intel._env  # noqa: F401 - triggers dotenv load at import time
from deal_intel.errors import Stage, envelope_from_exception

app = FastMCP("deal-intel")
_MAX_EMBEDDING_WARMUP_SECONDS = 30


def _enabled_mcp_tool_names() -> set[str]:
    try:
        from deal_intel import _context
        from deal_intel.tool_surfaces import tool_names_for_config

        return set(tool_names_for_config(_context.config()))
    except Exception:
        # Keep safe setup tools visible so invalid config can explain itself.
        return {"config_doctor", "update_config"}


def _install_tool_surface_filter(server: FastMCP) -> None:
    original_list_tools = server.list_tools
    original_call_tool = server.call_tool

    async def list_tools(*, run_middleware: bool = True):
        enabled = _enabled_mcp_tool_names()
        tools = await original_list_tools(run_middleware=run_middleware)
        return [tool for tool in tools if tool.name in enabled]

    async def call_tool(
        name: str,
        arguments: dict | None = None,
        *,
        version=None,
        run_middleware: bool = True,
        task_meta=None,
    ):
        if name not in _enabled_mcp_tool_names():
            raise NotFoundError(f"Unknown tool: {name!r}")
        return await original_call_tool(
            name,
            arguments,
            version=version,
            run_middleware=run_middleware,
            task_meta=task_meta,
        )

    server.list_tools = list_tools
    server.call_tool = call_tool


_install_tool_surface_filter(app)


@app.tool()
def config_doctor(offline: bool = False) -> dict:
    """Diagnose profile, storage, vector search, and LLM readiness.

    Read-only. The default path performs a bounded storage ping but does not
    call LLM completion APIs, embeddings, or write to MongoDB. Set
    offline=true to skip storage ping and run static checks only.
    """
    try:
        from deal_intel import _context
        from deal_intel.config_doctor import build_config_doctor_report

        def _storage_ping() -> dict:
            return _context.mongo().ping()

        return build_config_doctor_report(
            _context.config(),
            offline=offline,
            storage_ping=_storage_ping,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.PREFLIGHT)


@app.tool()
def update_config(
    dry_run: bool = True,
    confirmed_by_user: bool = False,
    llm_provider: str = "",
    chatgpt_oauth_model: str = "",
    openai_api_model: str = "",
    reporting_output_dir: str = "",
    reporting_timezone: str = "",
    tools_surface: str = "",
) -> dict:
    """Preview or apply safe non-secret user-config changes.

    This tool writes only allowlisted, non-secret settings to
    ~/.deal-intel/config.yaml. It cannot set MongoDB URIs, API keys, OAuth
    tokens, or other secrets; keep those in MCPB sensitive fields, `.env`, or
    shell environment variables.

    Defaults to dry_run=true. Actual writes require confirmed_by_user=true.
    Supported fields:
    - llm_provider: chatgpt_oauth | anthropic | openai_api
    - chatgpt_oauth_model
    - openai_api_model
    - reporting_output_dir
    - reporting_timezone
    - tools_surface: auto | sample | standard | developer
    """
    try:
        from deal_intel.config_writer import update_config_settings

        return update_config_settings(
            dry_run=dry_run,
            confirmed_by_user=confirmed_by_user,
            llm_provider=llm_provider or None,
            chatgpt_oauth_model=chatgpt_oauth_model or None,
            openai_api_model=openai_api_model or None,
            reporting_output_dir=reporting_output_dir or None,
            reporting_timezone=reporting_timezone or None,
            tools_surface=tools_surface or None,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.PREFLIGHT)


@app.tool()
def create_deal(
    company: str,
    industry: str = "",
    industry_tags: str = "",
    customer_segment: str = "",
    deal_size_amount: int | None = None,
    deal_size_status: str = "",
    deal_size_low_amount: int | None = None,
    deal_size_high_amount: int | None = None,
    deal_size_currency: str = "",
    deal_size_note: str = "",
    expected_close_date: str = "",
) -> dict:
    """Create a new deal for a prospect company.

    deal_size_status can be: unknown, rough_estimate, customer_budget,
    quoted, or strategic_zero. A zero amount is valid only with
    strategic_zero; omit deal_size_amount when the amount is unknown.

    Keep industry as the actual business vertical. Use customer_segment for
    maturity/market/ownership labels such as startup, enterprise, public_sector,
    Series B, or Pre-IPO. Use industry_tags for additional verticals when a
    customer is cross-industry; the primary industry is always included.

    When expected_close_date is omitted, config supplies a default date with
    optional exact customer segment overrides before industry overrides.
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import create_deal as _t

        return _t.handle(
            mongo=_context.mongo(),
            cfg=_context.config(),
            company=company,
            industry=industry or None,
            industry_tags=industry_tags or None,
            customer_segment=customer_segment or None,
            deal_size_amount=deal_size_amount,
            deal_size_status=deal_size_status or None,
            deal_size_low_amount=deal_size_low_amount,
            deal_size_high_amount=deal_size_high_amount,
            deal_size_currency=deal_size_currency or None,
            deal_size_note=deal_size_note or None,
            expected_close_date=expected_close_date or None,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def add_meeting(deal_id: str, date: str, raw_notes: str) -> dict:
    """Deprecated alias for add_interaction with interaction_type=meeting.

    New clients should call add_interaction instead. This wrapper is kept for
    developer-surface compatibility during the transition and still updates
    meddpicc_latest through the canonical interaction path.

    Does NOT change the pipeline stage. When the notes clearly imply a stage
    transition (e.g. contract signed -> won, deal lost -> lost), the response
    includes a non-null `stage_suggestion`. Surface it to the user and call
    update_stage only after they confirm; never auto-apply it.
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import add_meeting as _t

        embedding_provider = (
            _context.embedding_provider()
            if _context.storage_backend_name() == "mongo"
            else None
        )
        return _t.handle(
            mongo=_context.mongo(),
            llm=_context.llm_provider(),
            cfg=_context.config(),
            embedding_provider=embedding_provider,
            deal_id=deal_id,
            date=date,
            raw_notes=raw_notes,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.LLM)


@app.tool()
def add_interaction(
    deal_id: str,
    date: str,
    interaction_type: str,
    direction: str,
    content: str,
    participants: str = "",
    subject: str = "",
    source_confidence: str = "",
    custom_fields_json: str = "",
) -> dict:
    """Add a customer interaction and extract MEDDPICC signals.

    interaction_type: meeting, email_thread, user_interview, call_summary,
    internal_note, or a configured custom interaction type. direction:
    inbound, outbound, mixed, or internal.

    New records are stored as canonical interactions. Legacy meeting-based
    read paths are still supported as fallback. Stage changes are suggestions
    only and still require update_stage after user confirmation.
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import add_interaction as _t

        embedding_provider = (
            _context.embedding_provider()
            if _context.storage_backend_name() == "mongo"
            else None
        )
        return _t.handle(
            mongo=_context.mongo(),
            llm=_context.llm_provider(),
            cfg=_context.config(),
            embedding_provider=embedding_provider,
            deal_id=deal_id,
            date=date,
            interaction_type=interaction_type,
            direction=direction,
            content=content,
            participants=participants or None,
            subject=subject or None,
            source_confidence=source_confidence or None,
            custom_fields_json=custom_fields_json or None,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.LLM)


@app.tool()
def update_stage(
    deal_id: str,
    new_stage: str,
    actual_close_date: str = "",
) -> dict:
    """Move a deal to a new pipeline stage and log it to stage_history.

    Valid stages: discovery, qualification, proposal, negotiation, won, lost, stalled.
    For won/lost, actual_close_date is an optional ISO date (YYYY-MM-DD). It
    defaults to today when omitted. Non-terminal stages cannot receive one.
    Returns days spent in the previous stage and the stuck threshold for a new
    Active stage. Stalled and terminal stages return a null threshold.
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import update_stage as _t

        return _t.handle(
            mongo=_context.mongo(),
            cfg=_context.config(),
            deal_id=deal_id,
            new_stage=new_stage,
            actual_close_date=actual_close_date or None,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def update_deal(
    deal_id: str,
    deal_size_status: str = "",
    deal_size_note: str = "",
    confirmed_by_user: bool = False,
    deal_size_amount: int | None = None,
    deal_size_low_amount: int | None = None,
    deal_size_high_amount: int | None = None,
    deal_size_currency: str = "",
    company: str = "",
    industry: str = "",
    industry_tags: str = "",
    customer_segment: str = "",
    expected_close_date: str = "",
    actual_close_date: str = "",
    close_reason: str = "",
    update_note: str = "",
) -> dict:
    """Update confirmed value fields and selected metadata.

    Requires confirmed_by_user=true. Value updates require deal_size_status and
    deal_size_note. Metadata updates require update_note or deal_size_note.
    Does not change deal_stage; use update_stage for stage transitions.
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import update_deal as _t

        return _t.handle(
            mongo=_context.mongo(),
            deal_id=deal_id,
            deal_size_status=deal_size_status,
            deal_size_note=deal_size_note,
            confirmed_by_user=confirmed_by_user,
            deal_size_amount=deal_size_amount,
            deal_size_low_amount=deal_size_low_amount,
            deal_size_high_amount=deal_size_high_amount,
            deal_size_currency=deal_size_currency or None,
            company=company or None,
            industry=industry or None,
            industry_tags=industry_tags or None,
            customer_segment=customer_segment or None,
            expected_close_date=expected_close_date or None,
            actual_close_date=actual_close_date or None,
            close_reason=close_reason or None,
            update_note=update_note or None,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def archive_deal(
    deal_id: str,
    expected_company: str,
    archive_reason: str,
    confirmed_by_user: bool = False,
) -> dict:
    """Archive a deal so BI/read paths hide it without hard deletion.

    Requires confirmed_by_user=true, exact expected_company match, and a reason.
    Archived deals remain retrievable through get_deal with an archived warning.
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import archive_deal as _t

        return _t.handle(
            mongo=_context.mongo(),
            deal_id=deal_id,
            expected_company=expected_company,
            archive_reason=archive_reason,
            confirmed_by_user=confirmed_by_user,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def restore_deal(
    deal_id: str,
    expected_company: str,
    restore_reason: str,
    confirmed_by_user: bool = False,
) -> dict:
    """Restore an archived deal back into BI/read paths.

    Requires confirmed_by_user=true, exact expected_company match, and a reason.
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import restore_deal as _t

        return _t.handle(
            mongo=_context.mongo(),
            deal_id=deal_id,
            expected_company=expected_company,
            restore_reason=restore_reason,
            confirmed_by_user=confirmed_by_user,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def delete_deal(
    deal_id: str,
    expected_company: str,
    delete_reason: str,
    confirmed_by_user: bool = False,
    dry_run: bool = True,
) -> dict:
    """Hard-delete an archived deal after a dry-run preview.

    dry_run defaults to true and writes nothing. Actual deletion requires an
    already archived deal, confirmed_by_user=true, exact expected_company
    match, and a delete reason. A safe audit snapshot is stored before delete.
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import delete_deal as _t

        return _t.handle(
            mongo=_context.mongo(),
            deal_id=deal_id,
            expected_company=expected_company,
            delete_reason=delete_reason,
            confirmed_by_user=confirmed_by_user,
            dry_run=dry_run,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def create_sample_data(
    dataset: str = "weekly_pipeline_demo",
    demo_database: str = "",
    confirmed_by_user: bool = False,
    dry_run: bool = True,
    overwrite: bool = False,
) -> dict:
    """Create fictional onboarding sample deals in a separate demo database.

    Defaults to dry_run=true. Actual writes require confirmed_by_user=true.
    The demo database must differ from the primary configured database.
    """
    try:
        from deal_intel import _context
        from deal_intel.storage.mongodb import MongoDBClient
        from deal_intel.tools import create_sample_data as _t
        from deal_intel.tools.sample_data import resolve_demo_database

        cfg = _context.config()
        selection = resolve_demo_database(
            cfg,
            demo_database=demo_database or None,
        )
        return _t.handle(
            mongo=MongoDBClient(database=selection.demo_database),
            cfg=cfg,
            dataset=dataset,
            demo_database=selection.demo_database,
            confirmed_by_user=confirmed_by_user,
            dry_run=dry_run,
            overwrite=overwrite,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def delete_sample_data(
    dataset: str = "weekly_pipeline_demo",
    demo_database: str = "",
    confirmed_by_user: bool = False,
    dry_run: bool = True,
) -> dict:
    """Delete fictional onboarding sample deals from the separate demo database.

    Deletes only records with the known sample batch marker. Defaults to
    dry_run=true. Actual deletes require confirmed_by_user=true.
    """
    try:
        from deal_intel import _context
        from deal_intel.storage.mongodb import MongoDBClient
        from deal_intel.tools import delete_sample_data as _t
        from deal_intel.tools.sample_data import resolve_demo_database

        cfg = _context.config()
        selection = resolve_demo_database(
            cfg,
            demo_database=demo_database or None,
        )
        return _t.handle(
            mongo=MongoDBClient(database=selection.demo_database),
            cfg=cfg,
            dataset=dataset,
            demo_database=selection.demo_database,
            confirmed_by_user=confirmed_by_user,
            dry_run=dry_run,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def migrate_local_data(
    target_database: str = "",
    confirmed_by_user: bool = False,
    dry_run: bool = True,
    overwrite: bool = False,
) -> dict:
    """Migrate user-created local personal deals into MongoDB.

    Bundled zero-config fixture records are never migrated. Defaults to
    dry_run=true and writes nothing. Actual writes require
    confirmed_by_user=true. Existing target deals are skipped unless overwrite
    is true.
    """
    try:
        from deal_intel import _context
        from deal_intel.storage.local_personal import LocalPersonalStore
        from deal_intel.storage.mongodb import MongoDBClient
        from deal_intel.tools import migrate_local_data as _t

        cfg = _context.config()
        storage = cfg.get("storage", {})
        mongodb = cfg.get("mongodb", {})
        local_data_dir = (
            storage.get("local_data_dir") if isinstance(storage, dict) else None
        )
        database = (
            target_database.strip()
            if target_database.strip()
            else (
                mongodb.get("database", "deal_intel")
                if isinstance(mongodb, dict)
                else "deal_intel"
            )
        )
        return _t.handle(
            source_store=LocalPersonalStore(local_data_dir),
            target_mongo=MongoDBClient(database=database),
            dry_run=dry_run,
            overwrite=overwrite,
            confirmed_by_user=confirmed_by_user,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def get_deal(deal_id: str) -> dict:
    """Retrieve a deal with full meeting history and MEDDPICC scores."""
    try:
        from deal_intel import _context
        from deal_intel.tools import get_deal as _t

        return _t.handle(mongo=_context.mongo(), deal_id=deal_id)
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def list_deals(stage: str = "", limit: int = 20, as_of: str = "") -> dict:
    """List deals with health, stuck, overdue, and attention reasons.

    Optionally filter by stage (discovery/qualification/proposal/negotiation/won/lost/stalled).
    as_of accepts YYYY-MM-DD for reproducible date-based calculations.
    Results are sorted: stuck deals first, then by health_pct descending.
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import list_deals as _t

        return _t.handle(
            mongo=_context.mongo(),
            cfg=_context.config(),
            stage=stage or None,
            limit=limit,
            as_of=as_of or None,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def get_insights(query_type: str, as_of: str = "") -> dict:
    """Run a BI aggregation query across all deals.

    as_of accepts YYYY-MM-DD and is returned with the reporting timezone and
    generation timestamp. It labels the current collection snapshot rather
    than reconstructing historical database state.

    query_type options:
    - pipeline_overview   : deal count, average health, and value by stage
    - win_patterns        : average MEDDPICC scores across won deals
    - loss_patterns       : average MEDDPICC scores across lost deals
    - compare_won_lost    : compare win and loss MEDDPICC score patterns
    - gap_frequency       : most frequent MEDDPICC gap dimensions in active deals
    - industry_benchmark  : average health, win rate, and deal value by industry
    - stage_velocity      : average days in stage from stage_history
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import get_insights as _t

        return _t.handle(
            mongo=_context.mongo(),
            cfg=_context.config(),
            query_type=query_type,
            as_of=as_of or None,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def get_metrics(
    metric_type: str = "pipeline_health",
    stage: str = "",
    industry: str = "",
    as_of: str = "",
    lookback_days: int = 7,
) -> dict:
    """Return shared BI metrics for direct assistant answers.

    Supported metric_type values: pipeline_health, pipeline_trend.
    Optional filters:
    - stage: exact pipeline stage match
    - industry: exact stored industry match
    - as_of: YYYY-MM-DD business date for stuck/overdue calculations
    - lookback_days: trend window length, used only by pipeline_trend
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import get_metrics as _t

        return _t.handle(
            mongo=_context.mongo(),
            cfg=_context.config(),
            metric_type=metric_type,
            stage=stage or None,
            industry=industry or None,
            as_of=as_of or None,
            lookback_days=lookback_days,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def get_deal_gaps(
    as_of: str = "",
    stage: str = "",
    industry: str = "",
    deal_id: str = "",
    min_priority: str = "medium",
    limit: int = 10,
) -> dict:
    """Show customer-attack information gaps that need sales follow-up.

    Read-only. Uses the shared metric projection and does not call LLM,
    embeddings, or write to MongoDB.

    Optional filters:
    - as_of: YYYY-MM-DD business date for stuck/overdue calculations
    - stage: exact pipeline stage match
    - industry: exact stored industry match
    - deal_id: exact deal id; returns that deal regardless of priority
    - min_priority: low | medium | high, defaults to medium
    - limit: result limit, 1..50, defaults to 10
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import get_deal_gaps as _t

        return _t.handle(
            mongo=_context.mongo(),
            cfg=_context.config(),
            as_of=as_of or None,
            stage=stage or None,
            industry=industry or None,
            deal_id=deal_id or None,
            min_priority=min_priority,
            limit=limit,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def get_deal_review(deal_id: str, as_of: str = "") -> dict:
    """Review one deal with health quality separated from evidence coverage.

    Read-only. Uses restricted BI projection and does not call LLM, embeddings,
    or write to MongoDB. The response suppresses uncalibrated win-probability
    numbers and instead returns evidence coverage, uncertainty, missing
    information, confirmed risks, and recommended questions/actions.

    as_of accepts YYYY-MM-DD for reproducible stuck/overdue calculations.
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import get_deal_review as _t

        return _t.handle(
            mongo=_context.mongo(),
            cfg=_context.config(),
            deal_id=deal_id,
            as_of=as_of or None,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def export_report(
    report_type: str = "weekly_pipeline",
    output_dir: str = "",
    stage: str = "",
    industry: str = "",
    as_of: str = "",
    lookback_days: int = 7,
) -> dict:
    """Export BI reports to local files and return absolute artifact paths.

    Supported report_type values: weekly_pipeline, pipeline_trend.
    Creates a CSV and Markdown report using the shared BI/reporting contracts.
    Optional filters:
    - stage: exact pipeline stage match
    - industry: exact stored industry match
    - as_of: YYYY-MM-DD business date for stuck/overdue calculations
    - lookback_days: trend window length, used only by pipeline_trend
    - output_dir: local output directory; defaults to reporting.output_dir or ~/.deal-intel/reports
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import export_report as _t

        return _t.handle(
            mongo=_context.mongo(),
            cfg=_context.config(),
            report_type=report_type,
            output_dir=output_dir or None,
            stage=stage or None,
            industry=industry or None,
            as_of=as_of or None,
            lookback_days=lookback_days,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def get_user_memory(
    category: str = "",
    custom_doc_slug: str = "",
    limit: int = 5,
) -> dict:
    """Read user-memory Markdown docs for assistant context loading.

    This reads constrained files from user_docs/ or the configured
    user_memory.dir. It performs no DB reads, no DB writes, and no LLM calls.
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import get_user_memory as _t

        return _t.handle(
            cfg=_context.config(),
            category=category,
            custom_doc_slug=custom_doc_slug,
            limit=limit,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.PREFLIGHT)


@app.tool()
def record_user_memory(
    content: str,
    category: str = "general",
    custom_doc_slug: str = "",
    title: str = "",
    source: str = "",
    importance: str = "normal",
    tags: str = "",
) -> dict:
    """Append durable user feedback to a safe user-memory Markdown document.

    Use only when the user explicitly asks to remember, record, store, or
    update durable operating feedback. This rejects secret-shaped content and
    never writes outside user_docs/ or the configured user_memory.dir.
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import record_user_memory as _t

        return _t.handle(
            cfg=_context.config(),
            content=content,
            category=category,
            custom_doc_slug=custom_doc_slug,
            title=title,
            source=source,
            importance=importance,
            tags=tags,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.PREFLIGHT)


@app.tool()
def get_customer_themes(
    dimension: str = "all",
    stage: str = "active",
    industry: str = "",
    top_k: int = 5,
) -> dict:
    """Rank recurring customer concerns by unique deal count with evidence.

    dimension: all | identify_pain | decision_criteria | metrics
    stage: active | all | discovery | qualification | proposal | negotiation | won | lost | stalled
    industry: primary industry or industry_tags filter, or empty for all industries
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import get_customer_themes as _t

        return _t.handle(
            mongo=_context.mongo(),
            dimension=dimension,
            stage=stage,
            industry=industry or None,
            top_k=top_k,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def get_customer_theme_breakdown(
    dimension: str = "all",
    stage: str = "active",
    industry: str = "",
    group_by: str = "stage",
    top_k: int = 5,
) -> dict:
    """Compare recurring customer themes by stage, industry, industry tag, or dimension.

    Read-only. Uses curated customer_themes only; does not return raw meeting
    notes, contacts, or embeddings.

    dimension: all | identify_pain | decision_criteria | metrics
    stage: active | all | discovery | qualification | proposal | negotiation | won | lost | stalled
    industry: primary industry or industry_tags filter, or empty for all industries
    group_by: stage | industry | industry_tag | dimension
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import get_customer_theme_breakdown as _t

        return _t.handle(
            mongo=_context.mongo(),
            dimension=dimension,
            stage=stage,
            industry=industry or None,
            group_by=group_by,
            top_k=top_k,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def get_customer_theme_evidence(
    theme_key: str,
    dimension: str = "all",
    stage: str = "active",
    industry: str = "",
    limit: int = 10,
    min_importance: int = 1,
    interaction_type: str = "all",
    source_confidence: str = "all",
) -> dict:
    """Return curated evidence examples for one customer theme.

    Read-only. Evidence is the structured snippet already extracted into
    customer_themes; raw meeting notes, raw interaction content, contacts, and
    embeddings are excluded.

    theme_key: controlled taxonomy key, e.g. compliance_security
    dimension: all | identify_pain | decision_criteria | metrics
    stage: active | all | discovery | qualification | proposal | negotiation | won | lost | stalled
    industry: primary industry or industry_tags filter, or empty for all industries
    limit: 1..50
    min_importance: 1..5
    interaction_type: all | meeting | email_thread | user_interview |
      call_summary | internal_note | configured custom type
    source_confidence: all | customer_stated | mixed | internal | outbound_unconfirmed | unknown
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import get_customer_theme_evidence as _t

        return _t.handle(
            mongo=_context.mongo(),
            cfg=_context.config(),
            theme_key=theme_key,
            dimension=dimension,
            stage=stage,
            industry=industry or None,
            limit=limit,
            min_importance=min_importance,
            interaction_type=interaction_type,
            source_confidence=source_confidence,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def search_deals(query: str, limit: int = 5) -> dict:
    """Find deals semantically similar to the query.

    Examples:
    - "deals where the customer struggles with cost reduction"
    - "deals with a strong champion and clear decision process"
    - "deals similar to a named reference account"

    Returns deals ranked by semantic similarity with score (0–1, higher = more similar).
    While the local model loads, returns warming_up=true so the caller can retry.
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import search_deals as _t

        if _context.storage_backend_name() == "local_sample":
            return {
                "ok": False,
                "error_code": "CONFIG_ERROR",
                "stage": "preflight",
                "message": "search_deals is not supported in local_sample storage mode.",
                "hint": {
                    "fix": "Use storage.backend: mongo for semantic search, or use "
                    "get_metrics/get_deal_gaps/customer theme tools in sample mode."
                },
                "retryable": False,
                "warming_up": False,
            }

        embedding_provider = _context.embedding_provider()
        if embedding_provider is None:
            return {
                "ok": False,
                "error_code": "CONFIG_ERROR",
                "stage": "preflight",
                "message": "The local embedding provider is not installed.",
                "hint": {"fix": 'pip install -e ".[embedding]"'},
                "retryable": False,
                "warming_up": False,
            }
        if embedding_provider.load_error:
            return {
                "ok": False,
                "error_code": "UPSTREAM_ERROR",
                "stage": "preflight",
                "message": "The local embedding model failed to load.",
                "hint": {"detail": embedding_provider.load_error},
                "retryable": False,
                "warming_up": False,
            }
        if not embedding_provider.is_ready:
            warmup_status = embedding_provider.warmup_status
            if warmup_status["elapsed_seconds"] >= _MAX_EMBEDDING_WARMUP_SECONDS:
                return {
                    "ok": False,
                    "error_code": "UPSTREAM_ERROR",
                    "stage": "preflight",
                    "message": "The local embedding model warmup is stalled.",
                    "hint": {
                        **warmup_status,
                        "fix": "Restart the MCP server and check stderr for warmup errors.",
                    },
                    "retryable": False,
                    "warming_up": False,
                }
            return {
                "ok": False,
                "error_code": "UPSTREAM_ERROR",
                "stage": "preflight",
                "message": "The local embedding model is still loading. Retry shortly.",
                "hint": {
                    "retry_after_seconds": 5,
                    **warmup_status,
                },
                "retryable": True,
                "warming_up": True,
            }

        return _t.handle(
            mongo=_context.mongo(),
            embedding_provider=embedding_provider,
            cfg=_context.config(),
            query=query,
            limit=limit,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def analyze_deal(deal_id: str) -> dict:
    """Analyze a deal's MEDDPICC gaps and generate BD strategy recommendations."""
    try:
        from deal_intel import _context
        from deal_intel.tools import analyze_deal as _t

        return _t.handle(
            mongo=_context.mongo(),
            llm=_context.llm_provider(),
            deal_id=deal_id,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.ANALYSIS)


def main() -> None:
    from deal_intel import _context

    storage_backend = _context.storage_backend_name()

    # Pre-import native modules that can stall when first imported from a
    # background thread on Windows. Combined cold import stays within startup budget.
    if storage_backend == "mongo":
        from deal_intel.storage.mongodb import preload_driver

        preload_driver()

        try:
            import numpy  # noqa: F401
            import scipy  # noqa: F401
            import sklearn  # noqa: F401
            import torch  # noqa: F401
        except ImportError:
            pass

    # Warm the embedding model in a background thread so the first search_deals
    # call doesn't stall. all-MiniLM-L6-v2 takes ~10s to load cold; warming it
    # here means the model is ready by the time the user makes their first request.
    import threading

    def _warm_embedding() -> None:
        import sys
        import time
        try:
            # Let FastMCP finish importing and initialize stdio before PyTorch loads.
            # Concurrent startup can leave PyTorch initialization stalled on Windows.
            time.sleep(2)
            from deal_intel._context import embedding_provider
            ep = embedding_provider()
            if ep is not None:
                ep.warmup()
        except Exception as exc:
            print(f"[embed-warmup] FAILED: {exc}", file=sys.stderr, flush=True)

    if storage_backend == "mongo":
        threading.Thread(target=_warm_embedding, daemon=True, name="embed-warmup").start()

    def _ensure_mongo_indexes() -> None:
        import sys
        try:
            from deal_intel import _context
            _context.mongo().ensure_indexes()
        except Exception as exc:
            print(f"[mongo-indexes] FAILED: {exc}", file=sys.stderr, flush=True)

    if storage_backend == "mongo":
        threading.Thread(
            target=_ensure_mongo_indexes,
            daemon=True,
            name="mongo-indexes",
        ).start()

    app.run()


if __name__ == "__main__":
    main()
