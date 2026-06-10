from __future__ import annotations

from fastmcp import FastMCP

import deal_intel._env  # noqa: F401 — triggers dotenv load at import time
from deal_intel.errors import Stage, envelope_from_exception

app = FastMCP("deal-intel")
_MAX_EMBEDDING_WARMUP_SECONDS = 30


@app.tool()
def create_deal(
    company: str,
    industry: str = "",
    deal_size_krw: int | None = None,
    deal_size_status: str = "",
    deal_size_low_krw: int | None = None,
    deal_size_high_krw: int | None = None,
    deal_size_note: str = "",
    expected_close_date: str = "",
) -> dict:
    """Create a new deal for a prospect company.

    deal_size_status can be: unknown, rough_estimate, customer_budget,
    quoted, or strategic_zero. A zero amount is valid only with
    strategic_zero; omit deal_size_krw when the amount is unknown.

    When expected_close_date is omitted, config supplies a default date with
    optional exact industry overrides.
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import create_deal as _t

        return _t.handle(
            mongo=_context.mongo(),
            cfg=_context.config(),
            company=company,
            industry=industry or None,
            deal_size_krw=deal_size_krw,
            deal_size_status=deal_size_status or None,
            deal_size_low_krw=deal_size_low_krw,
            deal_size_high_krw=deal_size_high_krw,
            deal_size_note=deal_size_note or None,
            expected_close_date=expected_close_date or None,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def add_meeting(deal_id: str, date: str, raw_notes: str) -> dict:
    """Add meeting notes and extract MEDDPICC signals. Updates meddpicc_latest.

    Does NOT change the pipeline stage. When the notes clearly imply a stage
    transition (e.g. contract signed → won, deal lost → lost), the response
    includes a non-null `stage_suggestion`. Surface it to the user and call
    update_stage only after they confirm — never auto-apply it.
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import add_meeting as _t

        return _t.handle(
            mongo=_context.mongo(),
            llm=_context.llm_provider(),
            cfg=_context.config(),
            embedding_provider=_context.embedding_provider(),
            deal_id=deal_id,
            date=date,
            raw_notes=raw_notes,
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
    deal_size_krw: int | None = None,
    deal_size_low_krw: int | None = None,
    deal_size_high_krw: int | None = None,
    company: str = "",
    industry: str = "",
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
            deal_size_krw=deal_size_krw,
            deal_size_low_krw=deal_size_low_krw,
            deal_size_high_krw=deal_size_high_krw,
            company=company or None,
            industry=industry or None,
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
    - pipeline_overview   : stage별 딜 수·평균 health·총 딜 사이즈
    - win_patterns        : won 딜들의 MEDDPICC 차원별 평균 점수
    - loss_patterns       : lost 딜들의 MEDDPICC 차원별 평균 점수
    - compare_won_lost    : win vs loss 차원별 점수 차이 비교
    - gap_frequency       : 활성 딜에서 가장 자주 등장하는 gap dimension
    - industry_benchmark  : 업종별 평균 health_pct·승률·딜 규모
    - stage_velocity      : 스테이지별 평균 체류 일수 (stage_history 기반)
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
    - output_dir: local output directory; defaults to reporting.output_dir or outputs/reports
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
def get_customer_themes(
    dimension: str = "all",
    stage: str = "active",
    industry: str = "",
    top_k: int = 5,
) -> dict:
    """Rank recurring customer concerns by unique deal count with evidence.

    dimension: all | identify_pain | decision_criteria | metrics
    stage: active | all | discovery | qualification | proposal | negotiation | won | lost | stalled
    industry: exact industry filter, or empty for all industries
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
    """Compare recurring customer themes by stage, industry, or dimension.

    Read-only. Uses curated customer_themes only; does not return raw meeting
    notes, contacts, or embeddings.

    dimension: all | identify_pain | decision_criteria | metrics
    stage: active | all | discovery | qualification | proposal | negotiation | won | lost | stalled
    industry: exact industry filter, or empty for all industries
    group_by: stage | industry | dimension
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
) -> dict:
    """Return curated evidence examples for one customer theme.

    Read-only. Evidence is the structured snippet already extracted into
    customer_themes; raw meeting notes, contacts, and embeddings are excluded.

    theme_key: controlled taxonomy key, e.g. compliance_security
    dimension: all | identify_pain | decision_criteria | metrics
    stage: active | all | discovery | qualification | proposal | negotiation | won | lost | stalled
    industry: exact industry filter, or empty for all industries
    limit: 1..50
    min_importance: 1..5
    """
    try:
        from deal_intel import _context
        from deal_intel.tools import get_customer_theme_evidence as _t

        return _t.handle(
            mongo=_context.mongo(),
            theme_key=theme_key,
            dimension=dimension,
            stage=stage,
            industry=industry or None,
            limit=limit,
            min_importance=min_importance,
        )
    except Exception as exc:
        return envelope_from_exception(exc, stage=Stage.STORAGE)


@app.tool()
def search_deals(query: str, limit: int = 5) -> dict:
    """Find deals semantically similar to the query.

    Examples:
    - "고객이 비용 절감에 어려움을 겪고 있는 딜"
    - "champion이 강하고 의사결정 구조가 명확한 딜"
    - "현대정밀과 유사한 패턴의 딜"

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
