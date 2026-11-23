"""Gate v1 for the CMC RWA entry — checks 1–5 of DESIGN-CMC-RWA.md §5.3.

Usage:  python3 gate_cmc.py [--fixtures fixtures/cmc]
Prints PASS/FAIL per item; exit 0 only when ALL items pass.

Item 1 is the ONLY live check (it calls the real CMC API — about
6 credits per run): every backbone endpoint must answer 200 with the
expected shape. Items 2–5 are OFFLINE, from the stored fixtures in
fixtures/cmc/ — the live spread moves, so the gate NEVER compares live
data against fixture numbers with a tight tolerance.

Reference numbers (hand-computed from the STORED fixtures, captured
2026-11-23 12:47 WITA / 04:47 UTC — see fixtures/cmc/MANIFEST.json):
  quotes-latest-nvda.json: 9 tokens, 8 priced, Dinari (NVDA.D) null;
    spread_abs = 0.9477485423615803, spread_pct = 0.7071902849691895
    (0.5% watch threshold crossed -> issuer_spread_watch).
  historical-nvda-daily30.json: 30 closes;
    chg_24h = 1.2315275663880885, chg_7d = -19.581406622751192.
NOTE: the design's 12:44 WITA observation was spread 0.576% — the live
spread moved to 0.707% by the 12:47 capture. The gate checks the pipeline
against the STORED fixture (recomputed independently in this file), not
against the 12:44 number. That is the honest, reproducible criterion.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

import cmc_adapter as ad
import cmc_pipeline as pl

# Fixture capture time — items 2-3 evaluate the fixture AS OF its capture
# time, so the stale_quote flag does not depend on when the gate runs.
FIXTURE_NOW = datetime(2026, 11, 23, 4, 47, 0, tzinfo=timezone.utc)

# Recorded reference values (see module docstring).
REF_SPREAD_ABS = 0.9477485423615803
REF_SPREAD_PCT = 0.7071902849691895
REF_CHG_24H = 1.2315275663880885
REF_CHG_7D = -19.581406622751192

TOL = 1e-9  # relative tolerance for float comparisons


def _close(a, b):
    if a is None or b is None:
        return a is b
    return abs(a - b) <= TOL * max(1.0, abs(b))


def _load(fixture_dir, name):
    path = fixture_dir / name
    if not path.is_file():
        raise FileNotFoundError("missing fixture: %s" % path)
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Item 1 — all backbone endpoints live (200 + expected shape)
# ---------------------------------------------------------------------------

def item1_live_endpoints():
    """Each backbone endpoint answers 200 and returns the expected shape."""
    checks = []
    try:
        env = ad.fetch_map(symbol="NVDA", asset_type="stock")
        assets = pl.assets_from_envelope(env)
        checks.append(("map NVDA -> rwa_id 2",
                       bool(assets) and assets[0].get("rwa_id") == 2))
    except Exception as exc:  # noqa: BLE001 - gate reports, never crashes
        checks.append(("map NVDA -> rwa_id 2 (error: %s)" % exc, False))
    try:
        env = ad.fetch_list(asset_type="stock", sort="rwa_rank", limit=5)
        total = (env.get("data") or {}).get("total_size")
        checks.append(("assets/list stock total_size > 0",
                       isinstance(total, int) and total > 0))
    except Exception as exc:  # noqa: BLE001
        checks.append(("assets/list stock (error: %s)" % exc, False))
    try:
        env = ad.fetch_quotes_latest(rwa_id=2)
        assets = pl.assets_from_envelope(env)
        checks.append(("quotes/latest rwa_id 2 has tokens[]",
                       bool(assets) and isinstance(
                           assets[0].get("tokens"), list)))
    except Exception as exc:  # noqa: BLE001
        checks.append(("quotes/latest (error: %s)" % exc, False))
    try:
        env = ad.fetch_historical(rwa_id=2, interval="daily", count=30)
        assets = pl.assets_from_envelope(env)
        pts = (assets[0].get("quotes") if assets else None) or []
        checks.append(("quotes/historical rwa_id 2 daily x30",
                       len(pts) == 30))
    except Exception as exc:  # noqa: BLE001
        checks.append(("quotes/historical (error: %s)" % exc, False))
    try:
        env = ad.fetch_info(rwa_id=2)
        assets = pl.assets_from_envelope(env)
        checks.append(("info rwa_id 2 has name",
                       bool(assets) and bool(assets[0].get("name"))))
    except Exception as exc:  # noqa: BLE001
        checks.append(("info (error: %s)" % exc, False))
    try:
        env = ad.fetch_issuers_list(limit=5)
        issuers = (env.get("data") or {}).get("issuers") or []
        first_id = issuers[0].get("issuer_id") if issuers else None
        checks.append(("issuers/list non-empty", bool(issuers)))
        if first_id:
            env2 = ad.fetch_issuer(first_id)
            toks = (env2.get("data") or {}).get("tokens")
            checks.append(("issuers <id> has tokens[]",
                           isinstance(toks, list)))
        else:
            checks.append(("issuers <id> has tokens[] (no id)", False))
    except Exception as exc:  # noqa: BLE001
        checks.append(("issuers (error: %s)" % exc, False))
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print("    [%s] %s" % ("ok" if ok else "FAIL", name))
    return not failed


# ---------------------------------------------------------------------------
# Item 2 — spread from the STORED quotes fixture (not live)
# ---------------------------------------------------------------------------

def item2_spread_fixture(fixture_dir):
    """Pipeline over fixtures/cmc/quotes-latest-nvda.json reproduces the
    stored spread exactly (independently recomputed here from the raw
    tokens[]), priced_count = 8, Dinari null excluded."""
    env = _load(fixture_dir, "quotes-latest-nvda.json")
    assets = pl.assets_from_envelope(env)
    if len(assets) != 1:
        print("    [FAIL] expected 1 asset in fixture, got %d"
              % len(assets))
        return False
    asset = assets[0]
    spread = pl.compute_spread(asset)
    if spread is None:
        print("    [FAIL] compute_spread returned None")
        return False

    # Independent recomputation from the raw fixture (no pipeline code).
    tokens = asset.get("tokens") or []
    priced = [t for t in tokens
              if isinstance(t.get("price"), (int, float))]
    nulls = [t for t in tokens
             if not isinstance(t.get("price"), (int, float))]
    avg = asset.get("average_tokenized_price")
    exp_abs = max(t["price"] for t in priced) - min(t["price"] for t in priced)
    exp_pct = exp_abs / avg * 100.0

    ok = True
    def _check(cond, label, got=None, want=None):
        nonlocal ok
        print("    [%s] %s%s" % ("ok" if cond else "FAIL", label,
              "" if cond else " (got %r, want %r)" % (got, want)))
        ok = ok and cond

    _check(len(tokens) == 9, "tokens[] has 9 entries", len(tokens), 9)
    _check(len(priced) == 8, "priced_count == 8", len(priced), 8)
    _check(len(nulls) == 1 and nulls[0].get("symbol") == "NVDA.D"
           and "Dinari" in (nulls[0].get("issuer_name") or ""),
           "the one null token is NVDA.D (Dinari Assets)",
           [(t.get("symbol"), t.get("issuer_name")) for t in nulls],
           [("NVDA.D", "Dinari Assets")])
    _check(_close(spread["spread_abs"], exp_abs),
           "spread_abs matches independent recomputation",
           spread["spread_abs"], exp_abs)
    _check(_close(spread["spread_pct"], exp_pct),
           "spread_pct matches independent recomputation",
           spread["spread_pct"], exp_pct)
    _check(_close(spread["spread_abs"], REF_SPREAD_ABS),
           "spread_abs == recorded reference 0.9477485423615803",
           spread["spread_abs"], REF_SPREAD_ABS)
    _check(_close(spread["spread_pct"], REF_SPREAD_PCT),
           "spread_pct == recorded reference 0.7071902849691895",
           spread["spread_pct"], REF_SPREAD_PCT)
    _check(spread["spread_pct"] > 0.5,
           "spread above 0.5% watch threshold (flag expected)",
           spread["spread_pct"], "> 0.5")

    # Full row assessment as of fixture capture time (no stale_quote).
    snap = pl.build_snapshot([asset], context="monitor", now=FIXTURE_NOW)
    row = snap["assets"][0]
    _check(row["decision"] == "WATCH", "decision == WATCH",
           row["decision"], "WATCH")
    _check("issuer_spread_watch" in row["reason_codes"],
           "reason codes include issuer_spread_watch",
           row["reason_codes"], "issuer_spread_watch")
    _check("partial_prices_null" in row["reason_codes"],
           "reason codes include partial_prices_null",
           row["reason_codes"], "partial_prices_null")
    return ok


# ---------------------------------------------------------------------------
# Item 3 — % change from the STORED historical fixture
# ---------------------------------------------------------------------------

def item3_changes_fixture(fixture_dir):
    """% change from fixtures/cmc/historical-nvda-daily30.json matches
    hand computation from the fixture's own closes."""
    env = _load(fixture_dir, "historical-nvda-daily30.json")
    assets = pl.assets_from_envelope(env)
    if len(assets) != 1:
        print("    [FAIL] expected 1 asset in fixture, got %d"
              % len(assets))
        return False
    changes = pl.compute_changes(assets[0])

    closes = [p["average_tokenized_price"]
              for p in assets[0].get("quotes") or []]
    exp_24h = (closes[-1] - closes[-2]) / closes[-2] * 100.0
    exp_7d = (closes[-1] - closes[-8]) / closes[-8] * 100.0

    ok = True
    def _check(cond, label, got=None, want=None):
        nonlocal ok
        print("    [%s] %s%s" % ("ok" if cond else "FAIL", label,
              "" if cond else " (got %r, want %r)" % (got, want)))
        ok = ok and cond

    _check(changes["n_points"] == 30, "30 daily points", changes["n_points"], 30)
    _check(not changes["history_short"], "not history_short")
    _check(_close(changes["chg_24h"], exp_24h),
           "chg_24h matches independent recomputation",
           changes["chg_24h"], exp_24h)
    _check(_close(changes["chg_7d"], exp_7d),
           "chg_7d matches independent recomputation",
           changes["chg_7d"], exp_7d)
    _check(_close(changes["chg_24h"], REF_CHG_24H),
           "chg_24h == recorded reference 1.2315275663880885",
           changes["chg_24h"], REF_CHG_24H)
    _check(_close(changes["chg_7d"], REF_CHG_7D),
           "chg_7d == recorded reference -19.581406622751192",
           changes["chg_7d"], REF_CHG_7D)
    _check(len(changes["spark"]) == 30, "sparkline has 30 points")
    return ok


# ---------------------------------------------------------------------------
# Item 4 — edge cases from synthetic fixtures
# ---------------------------------------------------------------------------

def item4_edge_cases():
    """has_tokens=false -> NO_SIGNAL + no_tokens; all-null -> all_prices_
    null + NO_SIGNAL; duplicate symbol across asset types resolves only
    via asset_type + rwa_id (never guessed)."""
    ok = True
    def _check(cond, label, got=None, want=None):
        nonlocal ok
        print("    [%s] %s%s" % ("ok" if cond else "FAIL", label,
              "" if cond else " (got %r, want %r)" % (got, want)))
        ok = ok and cond

    # (a) has_tokens = false
    no_tok = {"rwa_id": 9001, "symbol": "FAKE", "name": "Fake No-Token",
              "asset_type": "stock", "rwa_rank": 9999, "has_tokens": False,
              "average_tokenized_price": None,
              "last_updated": "2026-11-23T04:47:00.000Z"}
    snap = pl.build_snapshot([no_tok], context="board", now=FIXTURE_NOW)
    row = snap["assets"][0]
    _check(row["decision"] == "NO_SIGNAL", "no_tokens -> NO_SIGNAL",
           row["decision"], "NO_SIGNAL")
    _check("no_tokens" in row["reason_codes"],
           "no_tokens -> code no_tokens", row["reason_codes"], "no_tokens")

    # (b) all token prices null
    all_null = {"rwa_id": 9002, "symbol": "NULL", "name": "Fake All-Null",
                "asset_type": "stock", "rwa_rank": 9998, "has_tokens": True,
                "average_tokenized_price": 10.0,
                "last_updated": "2026-11-23T04:47:00.000Z",
                "tokens": [
                    {"symbol": "NULLA", "issuer_name": "Issuer A",
                     "price": None},
                    {"symbol": "NULLB", "issuer_name": "Issuer B",
                     "price": None}]}
    snap = pl.build_snapshot([all_null], context="board", now=FIXTURE_NOW)
    row = snap["assets"][0]
    _check(row["decision"] == "NO_SIGNAL", "all-null -> NO_SIGNAL",
           row["decision"], "NO_SIGNAL")
    _check("all_prices_null" in row["reason_codes"],
           "all-null -> code all_prices_null",
           row["reason_codes"], "all_prices_null")

    # (c) duplicate symbol across asset types
    map_env = {"data": {"rwa_assets": [
        {"rwa_id": 9101, "symbol": "SPCX", "name": "SPCX Equity",
         "asset_type": "stock", "has_tokens": True},
        {"rwa_id": 9102, "symbol": "SPCX", "name": "SPCX Other",
         "asset_type": "etf", "has_tokens": True}]}}
    got = pl.resolve_asset(map_env, "SPCX")
    _check(got is None, "SPCX without asset_type -> ambiguous (None)",
           got, None)
    got = pl.resolve_asset(map_env, "SPCX", asset_type="stock")
    _check(got is not None and got["rwa_id"] == 9101,
           "SPCX + asset_type=stock -> rwa_id 9101",
           got and got.get("rwa_id"), 9101)
    got = pl.resolve_asset(map_env, "NOPE", asset_type="stock")
    _check(got is None, "unknown symbol -> None", got, None)
    return ok


# ---------------------------------------------------------------------------
# Item 5 — fail-closed (simulated API error)
# ---------------------------------------------------------------------------

def item5_fail_closed(fixture_dir):
    """A simulated API error keeps the last good snapshot and marks it
    stale — no invented data. With no previous snapshot, the result is an
    empty stale snapshot."""
    env = _load(fixture_dir, "quotes-latest-nvda.json")
    assets = pl.assets_from_envelope(env)
    good = pl.build_snapshot(assets, context="monitor", now=FIXTURE_NOW)
    err = ad.CmcApiError("simulated failure (gate item 5)")

    stale = pl.apply_error(good, err)
    ok = True
    def _check(cond, label, got=None, want=None):
        nonlocal ok
        print("    [%s] %s%s" % ("ok" if cond else "FAIL", label,
              "" if cond else " (got %r, want %r)" % (got, want)))
        ok = ok and cond

    _check(stale.get("status") == "stale", "status == stale",
           stale.get("status"), "stale")
    _check(stale.get("snapshot_id") == good.get("snapshot_id"),
           "same snapshot_id as the last good snapshot")
    _check(stale.get("assets") == good.get("assets"),
           "rows identical to the last good snapshot (nothing invented)")
    _check("simulated failure" in (stale.get("stale_reason") or ""),
           "stale_reason recorded", stale.get("stale_reason"), "simulated")

    empty = pl.apply_error(None, err)
    _check(empty.get("status") == "stale", "no previous -> stale",
           empty.get("status"), "stale")
    _check(empty.get("assets") == [], "no previous -> empty assets",
           empty.get("assets"), [])
    _check(empty.get("snapshot_id") is None,
           "no previous -> no snapshot_id", empty.get("snapshot_id"), None)
    return ok


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

ITEMS = [
    ("1", "all backbone endpoints live (200 + shape)", item1_live_endpoints),
    ("2", "spread from stored quotes fixture", item2_spread_fixture),
    ("3", "% change from stored historical fixture", item3_changes_fixture),
    ("4", "edge cases (synthetic fixtures)", item4_edge_cases),
    ("5", "fail-closed on simulated API error", item5_fail_closed),
]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", default=str(REPO / "fixtures" / "cmc"),
                        help="fixture directory (default: fixtures/cmc)")
    args = parser.parse_args(argv)
    fixture_dir = Path(args.fixtures)
    print("gate_cmc v1 — checks 1-5 (DESIGN-CMC-RWA.md §5.3)")
    print("fixtures: %s" % fixture_dir)
    results = {}
    for num, label, fn in ITEMS:
        print("[%s] %s" % (num, label))
        try:
            if num == "1":
                results[num] = fn()
            elif num in ("2", "3", "5"):
                results[num] = fn(fixture_dir)
            else:
                results[num] = fn()
        except Exception as exc:  # noqa: BLE001 - gate reports, never crashes
            print("    [FAIL] exception: %s" % exc)
            results[num] = False
        print("  -> %s" % ("PASS" if results[num] else "FAIL"))
    passed = sum(1 for v in results.values() if v)
    print("gate_cmc v1: %d/%d PASS" % (passed, len(ITEMS)))
    return 0 if passed == len(ITEMS) else 1


if __name__ == "__main__":
    sys.exit(main())
