"""E2E smoke test - runs against real MongoDB Atlas and real LLM.

Usage:
    python scripts/smoke_test.py                # uses config default LLM provider
    python scripts/smoke_test.py --anthropic    # force Anthropic (ANTHROPIC_API_KEY required)

Exercises the core write/read workflow end-to-end:
    create_deal -> add_meeting -> list_deals -> get_deal -> update_stage -> analyze_deal
"""
from __future__ import annotations

import json
import os
import sys

# Force Anthropic if --anthropic flag passed (useful when ChatGPT OAuth token absent).
if "--anthropic" in sys.argv:
    os.environ["DEAL_INTEL_USE_CHATGPT_OAUTH"] = "false"


def _ok(label: str, result: dict) -> dict:
    if result.get("ok") or result.get("status") == "ok":
        print(f"  [PASS] {label}")
    else:
        print(f"  [FAIL] {label}")
        print(f"         {json.dumps(result, ensure_ascii=False, indent=4)}")
        sys.exit(1)
    return result


def _header(title: str) -> None:
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")


def main() -> None:
    # ── imports after env override ────────────────────────────
    import deal_intel._env  # noqa: F401
    from deal_intel import _context
    from deal_intel.tools import (
        add_meeting,
        analyze_deal,
        create_deal,
        get_deal,
        list_deals,
        update_stage,
    )

    cfg = _context.config()
    mongo = _context.mongo()
    llm = _context.llm_provider()

    print(f"\nLLM provider : {cfg.get('llm', {}).get('provider')}")
    print(f"MongoDB DB   : {cfg.get('mongodb', {}).get('database')}")

    deal_id: str | None = None

    try:
        # ── 1. MongoDB connectivity ───────────────────────────
        _header("1. MongoDB connectivity")
        status = mongo.ping()
        _ok("ping", status)

        # ── 2. create_deal ────────────────────────────────────
        _header("2. create_deal")
        r = create_deal.handle(
            mongo,
            company="Acme Corp [smoke-test]",
            industry="SaaS",
            deal_size_amount=120_000_000,
            expected_close_date="2026-09-30",
        )
        _ok("create_deal", r)
        deal_id = r["deal_id"]
        print(f"         deal_id = {deal_id}")

        # ── 3. add_meeting (LLM) ──────────────────────────────
        _header("3. add_meeting  [LLM]")
        notes = (
            "CFO Park attended. She confirmed budget approval for Q3 - up to 150M KRW. "
            "Main pain: current ERP crashes every Monday morning, "
            "costing ~8M KRW/month in downtime. "
            "She said procurement requires 2-vendor shortlist and security review. "
            "VP Engineering Kim is our internal champion - he pushed for this evaluation. "
            "Competing against SAP and a homegrown solution the dev team built 3 years ago."
        )
        r = add_meeting.handle(
            mongo, llm, cfg,
            deal_id=deal_id,
            date="2026-06-08",
            raw_notes=notes,
        )
        _ok("add_meeting", r)
        print(f"         meeting_id  = {r['meeting_id']}")
        print(f"         meddpicc    = {list(r['meddpicc'].keys())}")
        print(f"         health_pct  = {r['meddpicc_latest'].get('health_pct')}%")
        print(f"         gaps        = {r['meddpicc_latest'].get('gaps')}")

        # ── 4. list_deals ─────────────────────────────────────
        _header("4. list_deals")
        r = list_deals.handle(mongo, cfg, stage=None, limit=10)
        _ok("list_deals", r)
        match = next((d for d in r["deals"] if d["deal_id"] == deal_id), None)
        if not match:
            print("  [FAIL] created deal not found in list")
            sys.exit(1)
        print(f"         health_pct    = {match['health_pct']}%")
        print(f"         days_in_stage = {match['days_in_stage']}")
        print(f"         is_stuck      = {match['is_stuck']}")
        print(f"         gaps          = {match['gaps']}")

        # ── 5. get_deal ───────────────────────────────────────
        _header("5. get_deal")
        r = get_deal.handle(mongo, deal_id=deal_id)
        _ok("get_deal", r)
        d = r["deal"]
        print(f"         meetings       = {len(d.get('meetings', []))}")
        print(f"         stage_history  = {d.get('stage_history')}")
        print(f"         health_pct     = {d.get('meddpicc_latest', {}).get('health_pct')}%")

        # ── 6. update_stage ───────────────────────────────────
        _header("6. update_stage")
        r = update_stage.handle(mongo, cfg, deal_id=deal_id, new_stage="qualification")
        _ok("update_stage", r)
        print(f"         {r['old_stage']} → {r['new_stage']}")
        print(f"         days in prev stage  = {r['days_in_previous_stage']}")
        print(f"         stuck threshold     = {r['stuck_threshold_days']} days")

        # verify stage_history appended
        r2 = get_deal.handle(mongo, deal_id=deal_id)
        history = r2["deal"].get("stage_history", [])
        assert len(history) == 2, f"Expected 2 history entries, got {len(history)}"
        print(f"         stage_history entries = {len(history)}  [OK]")

        # ── 7. analyze_deal (LLM) ─────────────────────────────
        _header("7. analyze_deal  [LLM]")
        r = analyze_deal.handle(mongo, llm, deal_id=deal_id)
        _ok("analyze_deal", r)
        preview = (
            r["analysis"][:300]
            .replace("\n", " ")
            .encode("cp949", errors="replace")
            .decode("cp949")
        )
        print(f"         analysis preview: {preview}...")

        print("\n" + "="*55)
        print("  ALL CHECKS PASSED")
        print("="*55)

    finally:
        # Always clean up test deal regardless of pass/fail.
        if deal_id:
            _header("Cleanup")
            try:
                mongo._get_db().deals.delete_one({"deal_id": deal_id})
                print(f"  [OK]  test deal {deal_id} deleted")
            except Exception as e:
                print(f"  [WARN] cleanup failed: {e}")
        print()


if __name__ == "__main__":
    main()
