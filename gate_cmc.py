"""Gate for the CMC RWA entry — checks 1–10 of DESIGN-CMC-RWA.md §5.3.

Usage:  python3 gate_cmc.py [--fixtures fixtures/cmc]
Prints PASS/FAIL per item; exit 0 only when ALL items pass.

Live items (they call the real CMC API — about 38 credits per full
run): 1 (backbone endpoints, ~6 cr), 4g (null-row check, 1 cr),
6 (budget measurement, 11 cr), 7 (dashboard, 5 cr: asset NVDA 3 +
board restore 2), 8 (demo run, ~15 cr). Items 2–5 are OFFLINE, from
the stored fixtures in fixtures/cmc/ — the live spread moves, so the
gate NEVER compares live data against fixture numbers with a tight
tolerance. Item 10 is OFFLINE (submission package on disk).

Reference numbers (hand-computed from the STORED fixtures, captured
2026-11-23 12:47 WITA / 04:47 UTC — see fixtures/cmc/MANIFEST.json):
  quotes-latest-nvda.json: 9 tokens, 8 priced, Dinari (NVDA.D) null;
    spread_abs = 0.9477485423615803, spread_pct = 0.7071902849691895
    (reported max-min spread — unchanged by the v0.2.0 recalibration);
    robust_spread_pct = 0.1789% (IQR/median — the decision metric;
    below the 0.5% flag threshold, so the fixture asset decides OK).
  historical-nvda-daily30.json: 30 daily-period observations (each
    the FIRST value in its period, not a close);
    chg_prev = 1.2315275663880885 (2026-11-21 to 2026-11-22),
    chg_8back = -19.581406622751192 (2026-11-15 to 2026-11-22).
NOTE: the design's 12:44 WITA observation was spread 0.576% — the live
spread moved to 0.707% by the 12:47 capture. The gate checks the pipeline
against the STORED fixture (recomputed independently in this file), not
against the 12:44 number. That is the honest, reproducible criterion.

Budget reference (measured in item 6, not assumed): per-call credits
for list (1), quotes/latest for 20 ids (1), historical 20 ids x30
(6 = 600 points / 100), historical 10 ids x30 (3). Startup cadence
(board 5 min, quotes 60 s, historical 15 min) projects to 96 credits
per hour scheduled and ~69,270 per month (69,120 scheduled + ~150
on-demand info/issuers); Basic fallback projects to ~6,840 per month
(under the 10,000 dashboard figure).
"""

import argparse
import io
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

import cmc_adapter as ad
import cmc_config as cfg
import cmc_pipeline as pl
import cmc_run as run

# Fixture capture time — items 2-3 evaluate the fixture AS OF its capture
# time, so the stale_quote flag does not depend on when the gate runs.
FIXTURE_NOW = datetime(2026, 11, 23, 4, 47, 0, tzinfo=timezone.utc)

# Recorded reference values (see module docstring).
REF_SPREAD_ABS = 0.9477485423615803
REF_SPREAD_PCT = 0.7071902849691895
REF_CHG_PREV = 1.2315275663880885
REF_CHG_8BACK = -19.581406622751192

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


def _check_box():
    """Return a (check, ok) pair: _check(cond, label, got, want) prints
    one line and accumulates the result."""
    state = {"ok": True}

    def _check(cond, label, got=None, want=None):
        print("    [%s] %s%s" % ("ok" if cond else "FAIL", label,
              "" if cond else " (got %r, want %r)" % (got, want)))
        state["ok"] = state["ok"] and bool(cond)
        return cond
    return _check, lambda: state["ok"]


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
    tokens[]), priced_count = 8, Dinari null excluded. The REPORTED
    max-min spread is unchanged by the v0.2.0 recalibration; the DECISION
    now uses the robust (IQR/median) spread — the fixture's cluster is
    tight (robust ~0.179% < 0.5% flag threshold), so the fixture asset decides
    OK with partial_prices_null listed as informational."""
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
    import statistics as _st
    _prices = sorted(t["price"] for t in priced)
    _q = _st.quantiles(_prices, n=4, method="inclusive")
    exp_robust = (_q[2] - _q[0]) / _q[1] * 100.0

    _check, ok = _check_box()
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
    _check(_close(spread["robust_spread_pct"], exp_robust),
           "robust_spread_pct matches independent recomputation "
           "(~0.1789%%)", spread["robust_spread_pct"], exp_robust)
    _check(spread["robust_spread_pct"] < 0.5,
           "robust spread below the 0.5% flag threshold (tight cluster)",
           spread["robust_spread_pct"], "< 0.5")

    # Full row assessment as of fixture capture time (no stale_quote).
    snap = pl.build_snapshot([asset], context="monitor", now=FIXTURE_NOW)
    row = snap["assets"][0]
    _check(row["decision"] == "OK",
           "decision == OK (robust metric, not max-min)",
           row["decision"], "OK")
    _check("issuer_spread_flag" not in row["reason_codes"],
           "reason codes do NOT include issuer_spread_flag",
           row["reason_codes"], "no issuer_spread_flag")
    _check("partial_prices_null" in row["reason_codes"],
           "reason codes still list partial_prices_null (informational)",
           row["reason_codes"], "partial_prices_null")
    # Token vs issuer counts: the fixture's 8 priced tokens come from
    # 7 distinct issuers (Backed has NVDAX + WNVDAX under one
    # issuer_id) — the metric is token-weighted, and the snapshot says
    # so. The projection retains the stable issuer_id / crypto_id.
    _check(spread.get("token_count") == 8,
           "spread token_count == 8", spread.get("token_count"), 8)
    _check(spread.get("issuer_count") == 7,
           "spread issuer_count == 7 (Backed shares one issuer_id)",
           spread.get("issuer_count"), 7)
    _check(len({t.get("issuer_id") for t in tokens
                if t.get("issuer_id")
                and pl._is_priced(t.get("price"))}) == 7,
           "priced tokens carry 7 distinct issuer_id values")
    _check(len({t.get("crypto_id") for t in tokens
                if t.get("crypto_id")
                and pl._is_priced(t.get("price"))}) == 8,
           "priced tokens carry 8 distinct crypto_id values")
    _check(all("issuer_id" in t and "crypto_id" in t
               for t in (row["spread"].get("tokens") or [])),
           "snapshot projection retains issuer_id + crypto_id per token")
    _check(snap.get("expected_cadence_seconds")
           == cfg.CADENCE[cfg.CREDIT_MODE]["quotes_seconds"],
           "snapshot carries expected_cadence_seconds (monitor = "
           "quotes cadence)",
           snap.get("expected_cadence_seconds"),
           cfg.CADENCE[cfg.CREDIT_MODE]["quotes_seconds"])
    return ok()


# ---------------------------------------------------------------------------
# Item 3 — % change from the STORED historical fixture
# ---------------------------------------------------------------------------

def item3_changes_fixture(fixture_dir):
    """% change from fixtures/cmc/historical-nvda-daily30.json matches
    hand computation from the fixture's own daily-period observations.
    Each observation is the FIRST value in its period, not a close, so
    the outputs are changes between the AVAILABLE daily-period
    observations, labelled with their actual dates (chg_prev:
    2026-11-21 to 2026-11-22; chg_8back: 2026-11-15 to 2026-11-22).
    The old chg_24h / chg_7d names are gone — the index arithmetic is
    the same, but two points dated 1 Jan and 4 Jan are not a "24h
    change"."""
    env = _load(fixture_dir, "historical-nvda-daily30.json")
    assets = pl.assets_from_envelope(env)
    if len(assets) != 1:
        print("    [FAIL] expected 1 asset in fixture, got %d"
              % len(assets))
        return False
    changes = pl.compute_changes(assets[0])

    values = [p["average_tokenized_price"]
              for p in assets[0].get("quotes") or []]
    exp_prev = (values[-1] - values[-2]) / values[-2] * 100.0
    exp_8back = (values[-1] - values[-8]) / values[-8] * 100.0

    _check, ok = _check_box()
    _check(changes["n_points"] == 30, "30 daily-period observations",
           changes["n_points"], 30)
    _check(not changes["history_short"], "not history_short")
    _check(_close(changes["chg_prev"], exp_prev),
           "chg_prev matches independent recomputation",
           changes["chg_prev"], exp_prev)
    _check(_close(changes["chg_8back"], exp_8back),
           "chg_8back matches independent recomputation",
           changes["chg_8back"], exp_8back)
    _check(_close(changes["chg_prev"], REF_CHG_PREV),
           "chg_prev == recorded reference 1.2315275663880885",
           changes["chg_prev"], REF_CHG_PREV)
    _check(_close(changes["chg_8back"], REF_CHG_8BACK),
           "chg_8back == recorded reference -19.581406622751192",
           changes["chg_8back"], REF_CHG_8BACK)
    _check(changes.get("chg_prev_from") == "2026-11-21"
           and changes.get("chg_prev_to") == "2026-11-22",
           "chg_prev labelled with its actual dates (2026-11-21 to "
           "2026-11-22)",
           (changes.get("chg_prev_from"), changes.get("chg_prev_to")),
           ("2026-11-21", "2026-11-22"))
    _check(changes.get("chg_8back_from") == "2026-11-15"
           and changes.get("chg_8back_to") == "2026-11-22",
           "chg_8back labelled with its actual dates (2026-11-15 to "
           "2026-11-22)",
           (changes.get("chg_8back_from"), changes.get("chg_8back_to")),
           ("2026-11-15", "2026-11-22"))
    _check(len(changes.get("obs_dates") or []) == 30
           and changes["obs_dates"][0] == "2026-10-24"
           and changes["obs_dates"][-1] == "2026-11-22",
           "timestamps kept: 30 obs_dates, 2026-10-24 to 2026-11-22",
           (len(changes.get("obs_dates") or []),
            (changes.get("obs_dates") or [None])[0],
            (changes.get("obs_dates") or [None])[-1]),
           (30, "2026-10-24", "2026-11-22"))
    _check("chg_24h" not in changes and "chg_7d" not in changes,
           "old chg_24h / chg_7d keys are gone")
    _check(len(changes["spark"]) == 30, "sparkline has 30 points")
    return ok()


# ---------------------------------------------------------------------------
# Item 4 — edge cases (synthetic fixtures + one live null-row check)
# ---------------------------------------------------------------------------

def item4_edge_cases():
    """(a) has_tokens=false -> NO_SIGNAL + no_tokens; (b) all-null ->
    all_prices_null + NO_SIGNAL; (c) duplicate symbol across asset
    types resolves only via asset_type + rwa_id (never guessed);
    (d) thin token count (1 priced token) -> NO_SIGNAL +
    thin_token_count; (e) mixed underlying (SPCX-like: 10 tokens
    ~$131 + 2 tokens ~$512/$531) -> WATCH + mixed_underlying, spread
    UNCHANGED (nothing silently dropped), outliers listed with
    issuer_name + price + stable issuer_id/crypto_id — and NO
    issuer_spread_flag: the extreme max-min spread is explained by
    the mixed_underlying flag, not double-flagged (the robust spread
    of the main cluster is ~0.17%);
    (f) partition_list_rows drops rwa_id=null rows; (g) LIVE:
    assets/list top-20 partitioned the same way — null rows (if any)
    are dropped and reported, never counted as covered;
    (h) robust just above the line: a wide cluster (robust ~0.69%) ->
    WATCH + issuer_spread_flag; (i) robust well above the line: a
    wider cluster (robust ~1.38%) -> the SAME issuer_spread_flag (one
    binary flag — no second level);
    (j) a single token 60% from the median does NOT flag
    mixed_underlying (the 100% line) and decides OK — the outlier is
    shown in the tokens table, not hidden; (k) tokens[] empty ->
    empty_tokens + NO_SIGNAL; (l) bool / NaN / None prices are not
    priced (priced_count counts only real finite numbers);
    (m) TSM-like: moving the HIGHEST quote 359.66 -> 400 leaves the
    robust spread EXACTLY unchanged (the max-min spread moves) —
    the central-dispersion metric does not follow the extreme quote;
    (n) the review's counterexample: [100, 100, 110] -> robust 5.0%
    WATCH (one stray token CAN move it), while 8x100 + 160 -> robust
    0.0% OK; (o) has_tokens=true but tokens[] MISSING ->
    missing_tokens + NO_SIGNAL (never a silent OK); (p) a zero price
    is not a valid price: excluded from priced, no ZeroDivisionError
    in spread or in % change; (q) >= 2 priced tokens from ONE issuer
    -> single_issuer + NO_SIGNAL (numbers shown, not a cross-issuer
    comparison); (r) the snapshot projection carries token_count +
    distinct issuer_count (NVDA fixture: 8 priced / 7 issuers)."""
    _check, ok = _check_box()

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

    # (d) thin token count: exactly 1 priced token
    thin = {"rwa_id": 9003, "symbol": "ONE", "name": "One Token",
            "asset_type": "stock", "rwa_rank": 9997, "has_tokens": True,
            "average_tokenized_price": 42.0,
            "last_updated": "2026-11-23T04:47:00.000Z",
            "tokens": [{"symbol": "ONEA", "issuer_name": "Issuer A",
                        "price": 42.0}]}
    snap = pl.build_snapshot([thin], context="board", now=FIXTURE_NOW)
    row = snap["assets"][0]
    _check(row["decision"] == "NO_SIGNAL", "thin (1 priced) -> NO_SIGNAL",
           row["decision"], "NO_SIGNAL")
    _check("thin_token_count" in row["reason_codes"],
           "thin -> code thin_token_count",
           row["reason_codes"], "thin_token_count")
    _check(row["spread"]["status"] == "thin_token_count",
           "thin -> spread status thin_token_count",
           row["spread"]["status"], "thin_token_count")

    # (e) mixed underlying, SPCX-like: 10 tokens ~131 + 2 at ~512/531
    spcx = {"rwa_id": 9004, "symbol": "SPCX", "name": "SpaceX (fake)",
            "asset_type": "stock", "rwa_rank": 9, "has_tokens": True,
            "average_tokenized_price": 131.4,
            "last_updated": "2026-11-23T04:47:00.000Z",
            "tokens": [{"symbol": "SPCX", "issuer_name": "Derivatives",
                        "price": 131.35}]
            + [{"symbol": "T%d" % i, "issuer_name": "Issuer %d" % i,
                "price": 131.0 + i * 0.05} for i in range(9)]
            + [{"symbol": "SPACEX", "issuer_name": "PreStocks",
                "issuer_id": "iss-prestocks", "crypto_id": 91001,
                "price": 530.83},
               {"symbol": "tSpaceX", "issuer_name": "Tessera",
                "issuer_id": "iss-tessera", "crypto_id": 91002,
                "price": 511.93}]}
    spread = pl.compute_spread(spcx)
    _check([o["symbol"] for o in spread["outlier_tokens"]]
           == ["SPACEX", "tSpaceX"],
           "SPCX-like outliers listed: SPACEX + tSpaceX",
           [o["symbol"] for o in spread["outlier_tokens"]],
           ["SPACEX", "tSpaceX"])
    _check(spread["outlier_tokens"][0].get("issuer_name") == "PreStocks"
           and spread["outlier_tokens"][0].get("price") == 530.83,
           "outliers carry issuer_name + price",
           spread["outlier_tokens"][0],
           {"symbol": "SPACEX", "issuer_name": "PreStocks",
            "price": 530.83})
    _check(spread["outlier_tokens"][0].get("issuer_id") == "iss-prestocks"
           and spread["outlier_tokens"][0].get("crypto_id") == 91001,
           "outliers carry stable issuer_id + crypto_id",
           (spread["outlier_tokens"][0].get("issuer_id"),
            spread["outlier_tokens"][0].get("crypto_id")),
           ("iss-prestocks", 91001))
    _check(_close(spread["spread_pct"],
                  (530.83 - 131.0) / 131.4 * 100.0),
           "SPCX-like spread UNCHANGED (still max-min over all priced)",
           spread["spread_pct"], (530.83 - 131.0) / 131.4 * 100.0)
    snap = pl.build_snapshot([spcx], context="board", now=FIXTURE_NOW)
    row = snap["assets"][0]
    _check(row["decision"] == "WATCH",
           "mixed underlying -> WATCH (non-blocking)",
           row["decision"], "WATCH")
    _check("mixed_underlying" in row["reason_codes"],
           "mixed underlying -> code mixed_underlying",
           row["reason_codes"], "mixed_underlying")
    _check("issuer_spread_flag" not in row["reason_codes"],
           "mixed underlying does NOT double-flag issuer_spread_flag "
           "(robust spread of the main cluster is ~0.17%)",
           row["reason_codes"], "no issuer_spread_flag")

    # (e2) ordinary single-token outlier (AMZN-like, -20% from median)
    # stays BELOW the 100% line: no mixed_underlying, only the single
    # spread flag (the robust spread of the wide cluster is ~1.17%).
    amzn = {"rwa_id": 9005, "symbol": "AMZN", "name": "Amazon (fake)",
            "asset_type": "stock", "rwa_rank": 6, "has_tokens": True,
            "average_tokenized_price": 250.0,
            "last_updated": "2026-11-23T04:47:00.000Z",
            "tokens": [{"symbol": "AMZ%d" % i, "issuer_name": "I%d" % i,
                        "price": 254.0 + i} for i in range(8)]
            + [{"symbol": "AMZHL", "issuer_name": "Hyperliquid",
                "price": 202.95}]}
    snap = pl.build_snapshot([amzn], context="board", now=FIXTURE_NOW)
    row = snap["assets"][0]
    _check("mixed_underlying" not in row["reason_codes"],
           "AMZN-like -20% outlier -> NO mixed_underlying",
           row["reason_codes"], "no mixed_underlying")
    _check("issuer_spread_flag" in row["reason_codes"],
           "AMZN-like -> issuer_spread_flag",
           row["reason_codes"], "issuer_spread_flag")

    # (h) robust just above the line: a wide cluster (IQR 0.70 over
    # median 100.8 -> robust ~0.69%) flags with the single binary flag.
    wide = {"rwa_id": 9006, "symbol": "WIDE", "name": "Wide cluster",
            "asset_type": "stock", "rwa_rank": 9996, "has_tokens": True,
            "average_tokenized_price": 100.8,
            "last_updated": "2026-11-23T04:47:00.000Z",
            "tokens": [{"symbol": "W%d" % i, "issuer_name": "I%d" % i,
                        "price": 100.0 + i * 0.2} for i in range(8)]}
    snap = pl.build_snapshot([wide], context="board", now=FIXTURE_NOW)
    row = snap["assets"][0]
    _check("issuer_spread_flag" in row["reason_codes"],
           "wide cluster (robust ~0.69%) -> issuer_spread_flag",
           row["reason_codes"], "issuer_spread_flag")
    _check(row["decision"] == "WATCH", "wide cluster -> WATCH",
           row["decision"], "WATCH")

    # (i) robust well above the line: a wider cluster (IQR 1.40 over
    # median 101.8 -> robust ~1.38%) flags with the SAME single flag —
    # there is no second level to distinguish it from (h).
    wider = {"rwa_id": 9007, "symbol": "WIDER", "name": "Wider cluster",
             "asset_type": "stock", "rwa_rank": 9995, "has_tokens": True,
             "average_tokenized_price": 101.8,
             "last_updated": "2026-11-23T04:47:00.000Z",
             "tokens": [{"symbol": "X%d" % i, "issuer_name": "I%d" % i,
                         "price": 100.0 + i * 0.4} for i in range(8)]}
    snap = pl.build_snapshot([wider], context="board", now=FIXTURE_NOW)
    row = snap["assets"][0]
    _check("issuer_spread_flag" in row["reason_codes"],
           "wider cluster (robust ~1.38%) -> issuer_spread_flag "
           "(same single flag as the 0.69% case)",
           row["reason_codes"], "issuer_spread_flag")

    # (j) a single token 60% from the median does NOT flag
    # mixed_underlying (the 100% line) — the outlier is shown in the
    # tokens table, the tight cluster decides OK.
    sixty = {"rwa_id": 9008, "symbol": "SIXTY", "name": "Sixty pct",
             "asset_type": "stock", "rwa_rank": 9994, "has_tokens": True,
             "average_tokenized_price": 100.0,
             "last_updated": "2026-11-23T04:47:00.000Z",
             "tokens": [{"symbol": "S%d" % i, "issuer_name": "I%d" % i,
                         "price": 100.0} for i in range(8)]
             + [{"symbol": "SOUT", "issuer_name": "Outlier",
                 "price": 160.0}]}
    snap = pl.build_snapshot([sixty], context="board", now=FIXTURE_NOW)
    row = snap["assets"][0]
    _check("mixed_underlying" not in row["reason_codes"],
           "60% single-token deviation -> NO mixed_underlying",
           row["reason_codes"], "no mixed_underlying")
    _check(row["decision"] == "OK",
           "60% single token, tight cluster -> OK",
           row["decision"], "OK")

    # (k) tokens[] present but empty -> empty_tokens + NO_SIGNAL.
    empty = {"rwa_id": 9009, "symbol": "EMPTY", "name": "Empty tokens",
             "asset_type": "stock", "rwa_rank": 9993, "has_tokens": True,
             "average_tokenized_price": 10.0,
             "last_updated": "2026-11-23T04:47:00.000Z", "tokens": []}
    snap = pl.build_snapshot([empty], context="board", now=FIXTURE_NOW)
    row = snap["assets"][0]
    _check(row["spread"]["status"] == "empty_tokens",
           "empty tokens[] -> status empty_tokens",
           row["spread"]["status"], "empty_tokens")
    _check(row["decision"] == "NO_SIGNAL", "empty tokens -> NO_SIGNAL",
           row["decision"], "NO_SIGNAL")
    _check("empty_tokens" in row["reason_codes"],
           "empty tokens -> code empty_tokens",
           row["reason_codes"], "empty_tokens")

    # (l) bool / NaN / None prices are not priced.
    weird = {"rwa_id": 9010, "symbol": "WEIRD", "name": "Weird prices",
             "asset_type": "stock", "rwa_rank": 9992, "has_tokens": True,
             "average_tokenized_price": 100.0,
             "last_updated": "2026-11-23T04:47:00.000Z",
             "tokens": [{"symbol": "B", "issuer_name": "Bool",
                         "price": True},
                        {"symbol": "N", "issuer_name": "NaN",
                         "price": float("nan")},
                        {"symbol": "U", "issuer_name": "Null",
                         "price": None},
                        {"symbol": "A", "issuer_name": "A",
                         "price": 100.0},
                        {"symbol": "C", "issuer_name": "C",
                         "price": 101.0}]}
    spread = pl.compute_spread(weird)
    _check(spread["priced_count"] == 2 and spread["null_count"] == 3,
           "bool/NaN/None excluded (priced 2, null 3)",
           (spread["priced_count"], spread["null_count"]), (2, 3))

    # (m) TSM-like: moving the HIGHEST quote 359.66 -> 400 leaves the
    # robust spread EXACTLY unchanged (the IQR does not follow the
    # extreme quote); the reported max-min spread DOES move.
    tsm_prices = [350.0, 352.0, 354.0, 355.0, 356.0, 357.0, 358.0,
                  359.0, 359.66]

    def _mk_asset(rid, symbol, prices):
        return {"rwa_id": rid, "symbol": symbol, "name": symbol,
                "asset_type": "stock", "rwa_rank": 9990,
                "has_tokens": True,
                "average_tokenized_price": sum(prices) / len(prices),
                "last_updated": "2026-11-23T04:47:00.000Z",
                "tokens": [{"symbol": "%s%d" % (symbol, i),
                            "issuer_name": "I%d" % i, "price": p}
                           for i, p in enumerate(prices)]}

    tsm = _mk_asset(9011, "TSM", tsm_prices)
    tsm_moved = _mk_asset(9011, "TSM",
                          [400.0 if p == 359.66 else p
                           for p in tsm_prices])
    r_before = pl.compute_spread(tsm)["robust_spread_pct"]
    r_after = pl.compute_spread(tsm_moved)["robust_spread_pct"]
    _check(r_before == r_after,
           "TSM-like: highest quote 359.66 -> 400, robust spread "
           "unchanged (%.4f%%)" % r_before,
           (r_before, r_after), "identical")
    _check(pl.compute_spread(tsm)["spread_pct"]
           < pl.compute_spread(tsm_moved)["spread_pct"],
           "TSM-like: reported max-min spread DOES move (robust does "
           "not follow the extreme quote)")

    # (n) The review's counterexample: [100, 100, 110] -> robust 5.0%
    # (one stray token CAN move it — the old "cannot move it" claim is
    # false), while 8x100 + 160 -> robust 0.0% OK.
    three = _mk_asset(9012, "THREE", [100.0, 100.0, 110.0])
    snap = pl.build_snapshot([three], context="board", now=FIXTURE_NOW)
    row = snap["assets"][0]
    _check(_close(row["spread"]["robust_spread_pct"], 5.0),
           "[100,100,110] -> robust spread exactly 5.0%",
           row["spread"]["robust_spread_pct"], 5.0)
    _check(row["decision"] == "WATCH"
           and "issuer_spread_flag" in row["reason_codes"],
           "[100,100,110] -> WATCH + issuer_spread_flag",
           row["decision"], "WATCH")
    nine = _mk_asset(9013, "NINE", [100.0] * 8 + [160.0])
    snap = pl.build_snapshot([nine], context="board", now=FIXTURE_NOW)
    row = snap["assets"][0]
    _check(_close(row["spread"]["robust_spread_pct"], 0.0),
           "8x100 + 160 -> robust spread exactly 0.0%",
           row["spread"]["robust_spread_pct"], 0.0)
    _check(row["decision"] == "OK",
           "8x100 + 160 -> OK (one stray token does not flag a tight "
           "cluster)", row["decision"], "OK")

    # (o) has_tokens=true but tokens[] MISSING -> missing_tokens +
    # NO_SIGNAL, never a silent OK.
    missing = {"rwa_id": 9014, "symbol": "MISS", "name": "Missing tokens",
               "asset_type": "stock", "rwa_rank": 9989,
               "has_tokens": True, "average_tokenized_price": 10.0,
               "last_updated": "2026-11-23T04:47:00.000Z"}
    snap = pl.build_snapshot([missing], context="board", now=FIXTURE_NOW)
    row = snap["assets"][0]
    _check(row["spread"]["status"] == "missing_tokens",
           "tokens[] missing -> status missing_tokens",
           row["spread"]["status"], "missing_tokens")
    _check(row["decision"] == "NO_SIGNAL",
           "tokens[] missing -> NO_SIGNAL (not OK)",
           row["decision"], "NO_SIGNAL")
    _check("missing_tokens" in row["reason_codes"],
           "tokens[] missing -> code missing_tokens",
           row["reason_codes"], "missing_tokens")

    # (p) A zero price is not a valid price: excluded from priced, no
    # ZeroDivisionError in the spread or in % change.
    zero = _mk_asset(9015, "ZERO", [100.0, 0, 101.0])
    spread = pl.compute_spread(zero)
    _check(spread["priced_count"] == 2 and spread["null_count"] == 1,
           "zero price excluded (priced 2, null 1)",
           (spread["priced_count"], spread["null_count"]), (2, 1))
    snap = pl.build_snapshot([zero], context="board", now=FIXTURE_NOW)
    _check(snap["assets"][0]["decision"] == "OK",
           "zero price does not crash the spread (OK, 2 priced)",
           snap["assets"][0]["decision"], "OK")
    zero_hist = {"rwa_id": 9015, "quotes": [
        {"timestamp": "2026-11-21T05:00:00Z",
         "average_tokenized_price": 100.0},
        {"timestamp": "2026-11-22T05:00:00Z",
         "average_tokenized_price": 0}]}
    changes = pl.compute_changes(zero_hist)
    _check(changes["n_points"] == 1 and changes["history_short"]
           and changes["chg_prev"] is None,
           "zero historical price excluded (1 point, history_short, "
           "no % change, no ZeroDivisionError)",
           (changes["n_points"], changes["history_short"],
            changes["chg_prev"]), (1, True, None))

    # (q) >= 2 priced tokens from ONE issuer -> single_issuer +
    # NO_SIGNAL; the numbers are still shown.
    solo = {"rwa_id": 9016, "symbol": "SOLO", "name": "One issuer",
            "asset_type": "stock", "rwa_rank": 9988,
            "has_tokens": True, "average_tokenized_price": 100.5,
            "last_updated": "2026-11-23T04:47:00.000Z",
            "tokens": [{"symbol": "A1", "issuer_name": "Solo",
                        "issuer_id": "iss-solo", "price": 100.0},
                       {"symbol": "A2", "issuer_name": "Solo",
                        "issuer_id": "iss-solo", "price": 101.0}]}
    snap = pl.build_snapshot([solo], context="board", now=FIXTURE_NOW)
    row = snap["assets"][0]
    _check(row["spread"]["status"] == "single_issuer",
           "2 priced tokens, 1 issuer -> status single_issuer",
           row["spread"]["status"], "single_issuer")
    _check(row["decision"] == "NO_SIGNAL",
           "single issuer -> NO_SIGNAL (not a cross-issuer comparison)",
           row["decision"], "NO_SIGNAL")
    _check("single_issuer" in row["reason_codes"],
           "single issuer -> code single_issuer",
           row["reason_codes"], "single_issuer")
    _check(row["spread"]["spread_pct"] is not None
           and row["spread"]["issuer_count"] == 1,
           "single issuer still shows the spread numbers "
           "(issuer_count 1)",
           row["spread"]["issuer_count"], 1)

    # (r) The snapshot projection carries token_count + distinct
    # issuer_count: the SPCX-like asset has 12 priced tokens from 12
    # distinct issuers; the NVDA fixture (item 2) has 8 / 7.
    snap = pl.build_snapshot([spcx], context="board", now=FIXTURE_NOW)
    row = snap["assets"][0]
    _check(row["spread"]["token_count"] == 12
           and row["spread"]["issuer_count"] == 12,
           "SPCX-like projection: 12 priced tokens / 12 issuers",
           (row["spread"]["token_count"],
            row["spread"]["issuer_count"]), (12, 12))

    # (f) partition_list_rows on synthetic rows
    ids, dropped = pl.partition_list_rows([
        {"rwa_id": 2, "symbol": "NVDA"},
        {"rwa_id": None, "symbol": "GOOG"},
        {"rwa_id": 15, "symbol": "BRK.B"},
        {"rwa_id": None, "symbol": "BRK.B"}])
    _check(ids == ["2", "15"], "partition keeps quotable ids",
           ids, ["2", "15"])
    _check(dropped == ["GOOG", "BRK.B"],
           "partition drops null rows and names them",
           dropped, ["GOOG", "BRK.B"])

    # (g) LIVE: assets/list top-20, partitioned the same way
    try:
        env = ad.fetch_list(asset_type="stock", sort="rwa_rank", limit=20)
        assets = pl.assets_from_envelope(env)
        ids, dropped = pl.partition_list_rows(assets)
        _check(len(ids) + len(dropped) == len(assets),
               "live top-20: ids + dropped == rows (%d rows, %d dropped: %s)"
               % (len(assets), len(dropped), ", ".join(dropped) or "none"),
               (len(ids), len(dropped)), (len(assets) - len(dropped),
                                          len(dropped)))
        _check(all(i.isdigit() for i in ids),
               "live top-20: every kept id is a number")
    except Exception as exc:  # noqa: BLE001
        _check(False, "live top-20 list fetch (error: %s)" % exc)
    return ok()


# ---------------------------------------------------------------------------
# Item 5 — fail-closed (simulated API error + adapter retry behaviour)
# ---------------------------------------------------------------------------

def item5_fail_closed(fixture_dir):
    """(a) A simulated API error keeps the last good snapshot and marks
    it stale — no invented data. With no previous snapshot, the result
    is an empty stale snapshot. (b) Adapter behaviour, mocked offline:
    HTTP 429 retries once then succeeds; 429 twice raises CmcApiError;
    a 403 envelope with error_code 1014 (historical out-of-window)
    surfaces as CmcApiError with error_code '1014' — the caller can
    degrade to quotes-only instead of retrying the same call."""
    env = _load(fixture_dir, "quotes-latest-nvda.json")
    assets = pl.assets_from_envelope(env)
    good = pl.build_snapshot(assets, context="monitor", now=FIXTURE_NOW)
    err = ad.CmcApiError("simulated failure (gate item 5)")

    _check, ok = _check_box()
    stale = pl.apply_error(good, err)
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

    # --- adapter mocks (no network) ---
    def _fake_200(payload):
        class FakeResp:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def read(self):
                return json.dumps(payload).encode("utf-8")
        return FakeResp()

    def _fake_raw(body):
        class FakeResp:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def read(self):
                return body
        return FakeResp()

    def _fake_http_error(code, payload):
        body = json.dumps(payload).encode("utf-8")
        return urllib.error.HTTPError(
            "https://example.invalid/x", code, "error", {},
            io.BytesIO(body))

    ok200 = {"data": {"rwa_assets": []},
             "status": {"error_code": "0", "credit_count": 1}}
    err1014 = {"status": {"error_code": "1014",
                          "error_message": "out of window"}}
    err429 = {"status": {"error_code": "429",
                         "error_message": "rate limit"}}

    with mock.patch.object(ad.time, "sleep", lambda s: None):
        # (i) 429 once, then 200 -> retry succeeds
        with mock.patch.object(
                urllib.request, "urlopen",
                side_effect=[_fake_http_error(429, err429),
                             _fake_200(ok200)]) as m:
            try:
                out = ad._get_json("/v5/real-world-assets/map", {})
                _check(out == ok200, "429 once -> retry succeeds",
                       out, ok200)
            except Exception as exc:  # noqa: BLE001
                _check(False, "429 once -> retry succeeds (%s)" % exc)
        # (ii) 429 twice -> raises after the one allowed retry
        with mock.patch.object(
                urllib.request, "urlopen",
                side_effect=[_fake_http_error(429, err429),
                             _fake_http_error(429, err429)]):
            try:
                ad._get_json("/v5/real-world-assets/map", {})
                _check(False, "429 twice -> raises CmcApiError",
                       "no exception", "CmcApiError")
            except ad.CmcApiError as exc:
                _check(exc.http_status == 429,
                       "429 twice -> CmcApiError http 429",
                       exc.http_status, 429)
            except Exception as exc:  # noqa: BLE001
                _check(False, "429 twice -> CmcApiError (%s)" % exc)
        # (iii) 403 envelope with error_code 1014 -> surfaced as-is
        with mock.patch.object(
                urllib.request, "urlopen",
                side_effect=[_fake_http_error(403, err1014)]):
            try:
                ad._get_json("/v5/real-world-assets/quotes/historical",
                             {})
                _check(False, "403/1014 -> raises CmcApiError",
                       "no exception", "CmcApiError")
            except ad.CmcApiError as exc:
                _check(exc.error_code == "1014",
                       "403/1014 -> error_code '1014' surfaced",
                       exc.error_code, "1014")
            except Exception as exc:  # noqa: BLE001
                _check(False, "403/1014 -> CmcApiError (%s)" % exc)
        # (iv) 200 with an error envelope -> raises too
        with mock.patch.object(
                urllib.request, "urlopen",
                return_value=_fake_200(err1014)):
            try:
                ad._get_json("/v5/real-world-assets/quotes/historical",
                             {})
                _check(False, "200 + error envelope -> raises CmcApiError",
                       "no exception", "CmcApiError")
            except ad.CmcApiError as exc:
                _check(exc.error_code == "1014",
                       "200 + error envelope -> error_code '1014'",
                       exc.error_code, "1014")
            except Exception as exc:  # noqa: BLE001
                _check(False, "200 + error envelope -> CmcApiError (%s)"
                       % exc)
        # (v) 200 with MALFORMED JSON -> CmcApiError, not a raw
        # JSONDecodeError escaping the CmcError path the monitor
        # catches (a 200 whose body is not JSON is an unavailable
        # result, not a crash).
        with mock.patch.object(
                urllib.request, "urlopen",
                return_value=_fake_raw(b"not json{")):
            try:
                ad._get_json("/v5/real-world-assets/map", {})
                _check(False, "200 + malformed JSON -> raises CmcApiError",
                       "no exception", "CmcApiError")
            except ad.CmcApiError:
                _check(True, "200 + malformed JSON -> CmcApiError")
            except Exception as exc:  # noqa: BLE001
                _check(False, "200 + malformed JSON -> CmcApiError "
                       "(got %s: %s)" % (type(exc).__name__, exc))
        # (vi) 200 with a non-object JSON envelope -> CmcApiError.
        with mock.patch.object(
                urllib.request, "urlopen",
                return_value=_fake_raw(b"[1, 2]")):
            try:
                ad._get_json("/v5/real-world-assets/map", {})
                _check(False, "200 + non-object JSON -> raises CmcApiError",
                       "no exception", "CmcApiError")
            except ad.CmcApiError:
                _check(True, "200 + non-object JSON -> CmcApiError")
            except Exception as exc:  # noqa: BLE001
                _check(False, "200 + non-object JSON -> CmcApiError "
                       "(got %s: %s)" % (type(exc).__name__, exc))
    return ok()


# ---------------------------------------------------------------------------
# Item 6 — credit budget, MEASURED live (not assumed)
# ---------------------------------------------------------------------------

def _credit(env):
    return int((env.get("status") or {}).get("credit_count") or 0)


def item6_credit_budget():
    """(OFFLINE first) The monitor's request-building path, mocked:
    the historical request is sliced to the active mode's cap with
    the explicitly requested ticker first, and a board refresh
    preserves that ticker. (LIVE) Measure the real per-call credit
    cost of each cadence step, then project the hourly / monthly
    budget from the MEASURED numbers and the configured cadence
    (DESIGN-CMC-RWA.md §3.4). PASS: 1-hour monitor projection <= 100
    credits; Startup monthly <= 450,000; Basic fallback monthly <=
    10,000 (the conservative dashboard figure). Costs ~11 credits to
    measure."""
    _check, ok = _check_box()

    # --- offline: the monitor request path (no network) ---
    ids21 = [str(i) for i in range(1, 22)]  # 20 ranked + 1 ticker
    extra = "21"
    for mode in ("startup", "basic"):
        cap = cfg.CADENCE[mode]["historical_assets"]
        got = run.historical_ids(ids21, extra, cap)
        _check(len(got) == cap,
               "monitor historical request (%s): %d ids, capped at %d"
               % (mode, len(got), cap), len(got), cap)
        _check(got[0] == extra,
               "monitor historical request (%s): ticker first"
               % mode, got[0], extra)
    _check(run.historical_ids(ids21, None, 10) == ids21[:10],
           "monitor historical request (no ticker): first 10 ranked")
    # refresh_watchlist: the ticker survives a board refresh.
    with mock.patch.object(
            run, "fetch_board_ids",
            return_value=([], [str(i) for i in range(1, 21)])):
        refreshed = run.refresh_watchlist(run.CreditMeter(), "21")
        _check(refreshed == [str(i) for i in range(1, 21)] + ["21"],
               "board refresh preserves the explicitly requested "
               "ticker", refreshed[-1], "21")
    # fetch_historical_map sends exactly the capped id list.
    seen = {}

    def _capture(rwa_id, interval, count):
        seen["rwa_id"] = rwa_id
        return {"data": {"rwa_assets": []}, "status": {"credit_count": 0}}

    with mock.patch.object(ad, "fetch_historical",
                           side_effect=_capture):
        run.fetch_historical_map(run.CreditMeter(),
                                 run.historical_ids(ids21, extra, 10))
    _check(seen.get("rwa_id") == "21,1,2,3,4,5,6,7,8,9",
           "fetch_historical_map receives the capped id list "
           "(ticker first, 10 ids)",
           seen.get("rwa_id"), "21,1,2,3,4,5,6,7,8,9")

    try:
        env = ad.fetch_list(asset_type="stock", sort="rwa_rank",
                            limit=100)
        list_cr = _credit(env)
        ids = [str(a["rwa_id"]) for a in pl.assets_from_envelope(env)
               if a.get("rwa_id") is not None][:20]
        _check(len(ids) == 20, "top-20 ids resolved for measurement",
               len(ids), 20)
        env = ad.fetch_quotes_latest(rwa_id=",".join(ids))
        quotes_cr = _credit(env)
        env = ad.fetch_historical(rwa_id=",".join(ids),
                                  interval="daily", count=30)
        hist20_cr = _credit(env)
        env = ad.fetch_historical(rwa_id=",".join(ids[:10]),
                                  interval="daily", count=30)
        hist10_cr = _credit(env)
    except Exception as exc:  # noqa: BLE001
        _check(False, "budget measurement calls (error: %s)" % exc)
        return ok()

    _check(list_cr == 1, "assets/list top-100 = 1 credit",
           list_cr, 1)
    _check(quotes_cr == 1, "quotes/latest 20 ids = 1 credit",
           quotes_cr, 1)
    _check(hist20_cr == 6, "historical 20 ids x30 = 6 credits "
           "(600 points / 100)", hist20_cr, 6)
    _check(hist10_cr == 3, "historical 10 ids x30 = 3 credits "
           "(300 points / 100)", hist10_cr, 3)

    # Startup: board every 5 min (12/h) + quotes every 60 s (60/h) +
    # historical every 15 min (4/h, 20 assets) — cadence from config.
    hourly = 12 * list_cr + 60 * quotes_cr + 4 * hist20_cr
    monthly = hourly * 24 * 30 + 150  # + ~150 on-demand info/issuers
    print("    measured: list=%d quotes20=%d hist20=%d hist10=%d"
          % (list_cr, quotes_cr, hist20_cr, hist10_cr))
    print("    projected Startup: %d credits/hour, %d/month"
          % (hourly, monthly))
    _check(hourly <= 100, "1-hour monitor projection <= 100 credits",
           hourly, "<= 100")
    _check(monthly <= 450000, "Startup monthly <= 450,000 (%.1f%%)"
           % (monthly / 4500.0), monthly, "<= 450000")
    # Basic fallback: board every 30 min (48/day) + quotes every 10 min
    # (144/day) + historical 10 assets every 2 h (12/day).
    basic_day = 48 * list_cr + 144 * quotes_cr + 12 * hist10_cr
    basic_month = basic_day * 30
    print("    projected Basic fallback: %d credits/day, %d/month"
          % (basic_day, basic_month))
    _check(basic_month <= 10000,
           "Basic monthly <= 10,000 (dashboard figure)",
           basic_month, "<= 10000")
    return ok()


# ---------------------------------------------------------------------------
# Item 7 — dashboard renders from a live snapshot (Playwright)
# ---------------------------------------------------------------------------

def item7_dashboard():
    """Live check: `cmc_run.py asset NVDA` writes a snapshot WITH
    historical data; serve.py serves it; Playwright loads the page,
    finds board rows, clicks NVDA, and the detail pane opens with the
    tokens table AND a rendered sparkline SVG. The detail pane shows
    % change between the available daily-period observations, labelled
    with their actual dates (not "24h/7d"). The client-side age
    warning is checked too: the same snapshot, aged 2 h, must show
    the age banner even though its status is OK. Afterwards the board
    snapshot is restored (`board --limit 10`). Costs 5 credits."""
    _check, ok = _check_box()
    port = 8123
    server = None
    try:
        r = subprocess.run(
            [sys.executable, "cmc_run.py", "asset", "NVDA"],
            cwd=str(REPO), capture_output=True, text=True, timeout=120)
        _check(r.returncode == 0,
               "asset NVDA writes a snapshot with historical data",
               r.returncode, 0)
        if r.returncode != 0:
            print("    " + (r.stderr or r.stdout)[-500:])
            return ok()
        server = subprocess.Popen(
            [sys.executable, "serve.py", "--port", str(port)],
            cwd=str(REPO), stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        up = False
        for _ in range(15):
            try:
                with urllib.request.urlopen(
                        "http://127.0.0.1:%d/" % port,
                        timeout=2) as resp:
                    up = resp.status == 200
            except Exception:  # noqa: BLE001
                time.sleep(1)
            if up:
                break
        _check(up, "serve.py answers 200 on :%d" % port, up, True)
        if not up:
            return ok()

        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280,
                                              "height": 800})
            page.goto("http://127.0.0.1:%d/" % port,
                      wait_until="domcontentloaded")
            page.wait_for_selector("#board-body tr", timeout=10000)
            rows = page.locator("#board-body tr").count()
            _check(rows >= 1, "board has >= 1 row", rows, ">= 1")
            row = page.locator("#board-body tr", has_text="NVDA").first
            _check(row.count() == 1, "NVDA row found on the board",
                   row.count(), 1)
            row.click()
            page.wait_for_selector("#detail:not([hidden])", timeout=10000)
            detail = page.locator("#detail").inner_text()
            _check("NVDA" in detail and "rwa_id 2" in detail,
                   "detail pane opens for NVDA (rwa_id 2)",
                   detail[:80], "NVDA · rwa_id 2")
            _check("Issuer spread" in detail,
                   "detail pane shows the issuer-spread section")
            _check(page.locator("#detail svg.spark").count() == 1,
                   "sparkline SVG rendered (snapshot has historical)",
                   page.locator("#detail svg.spark").count(), 1)
            _check("change vs previous daily-period observation"
                   in detail,
                   "detail pane shows % change between daily-period "
                   "observations, labelled with dates")
            _check("24h:" not in detail and "7d:" not in detail,
                   "detail pane has no stale 24h/7d labels",
                   detail[:120], "no 24h:/7d:")
            # Age warning: the same snapshot, aged 2 h, must show the
            # age banner even though its status is OK (a stopped
            # producer leaves a green OK on old data); restoring the
            # fresh snapshot hides it again.
            snap_path = REPO / "out" / "cmc_snapshot.json"
            fresh_text = snap_path.read_text(encoding="utf-8")
            fresh = json.loads(fresh_text)
            old = dict(fresh)
            old["generated_at"] = "2026-11-23T00:00:00Z"
            snap_path.write_text(json.dumps(old), encoding="utf-8")
            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector("#board-body tr", timeout=10000)
            age_banner = page.locator("#age-banner")
            _check(age_banner.is_visible(),
                   "age banner visible for a 2h-old snapshot",
                   age_banner.is_visible(), True)
            _check("older than the expected refresh cadence"
                   in (age_banner.inner_text() or ""),
                   "age banner explains the cadence",
                   (age_banner.inner_text() or "")[:80], "cadence")
            snap_path.write_text(fresh_text, encoding="utf-8")
            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector("#board-body tr", timeout=10000)
            _check(not page.locator("#age-banner").is_visible(),
                   "age banner hidden again for the fresh snapshot",
                   page.locator("#age-banner").is_visible(), False)
            browser.close()
    except Exception as exc:  # noqa: BLE001
        _check(False, "dashboard check (error: %s)" % exc)
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
        # Restore the board snapshot for the next steps / the user.
        subprocess.run([sys.executable, "cmc_run.py", "board",
                        "--limit", "10"], cwd=str(REPO),
                       capture_output=True, text=True, timeout=120)
    return ok()


# ---------------------------------------------------------------------------
# Item 8 — demo end-to-end (run_demo.sh exit 0)
# ---------------------------------------------------------------------------

def item8_demo():
    """`demo/run_demo.sh` exits 0 (CLI live + serve + capture all 7
    shots). Costs ~15 credits. The script itself verifies every shot
    is a real PNG."""
    _check, ok = _check_box()
    try:
        r = subprocess.run(
            ["./demo/run_demo.sh"], cwd=str(REPO),
            capture_output=True, text=True, timeout=1200)
        tail = "\n".join((r.stdout or "").splitlines()[-8:])
        print("    demo output (last lines):\n" + "\n".join(
            "      " + line for line in tail.splitlines()))
        _check(r.returncode == 0, "demo/run_demo.sh exit 0",
               r.returncode, 0)
        if r.returncode != 0:
            print("    demo stderr (last 500 chars):\n      "
                  + (r.stderr or "")[-500:])
    except Exception as exc:  # noqa: BLE001
        _check(False, "demo run (error: %s)" % exc)
    return ok()


# ---------------------------------------------------------------------------
# Item 9 — repo clean (no key, no Base files, only intended changes)
# ---------------------------------------------------------------------------

BASE_FILES = [
    "config.py", "adapter.py", "pipeline.py", "run.py", "gate.py",
    "capture_evidence.py", "capture_rpc_evidence.py",
    "verify_rpc_replay.py", "package_v6.py", "package_v7.py",
    "package_v8.py", "DESIGN.md", "DECISION_MEMO.md",
    "DECISION_MEMO-v0.3.2.md", "QUOTER-RESEARCH.md",
    "README-v0.3.2.md", "MUSE-BASE-V033-AUDIT-2026-11-23.md",
    "diff-v0.3.2-v0.3.3.txt", "audit-instinct-2026-11-22",
    "fixtures", "evidence",  # old Base dirs (ours: fixtures/cmc,
                             # evidence/cmc — checked separately below)
]

# Paths the v0.4.0 final-gate fix round (23 Nov 2026, Instinct 77/100
# HOLD) is allowed to have changed (everything else in `git status`
# fails the item). The video rebuild and its intermediates are intended
# changes of this round. Calibration inputs + their recomputation are
# new files this round.
ALLOWED_CHANGED = {
    "cmc_config.py", "cmc_pipeline.py", "cmc_run.py", "cmc_adapter.py",
    "gate_cmc.py", "capture_cmc_evidence.py", "README.md",
    "SUBMISSION.md", "CMC_INTEGRATION.md", "DESIGN-CMC-RWA.md",
    "dashboard/index.html", "fixtures/cmc/README.md",
    "demo/capture.py", "demo/shot-list.md", "demo/merge_history.py",
    "demo/run_demo.sh", "demo/video-final.mp4",
    "demo/video-final-x.mp4", "demo/build_final_video.sh",
    "demo/build_x_cut.sh", "demo/make_title_cards.py",
    # 23 Nov 2026 re-gate fix round: regression tests for must-fix #1.
    "test_cmc_failclosed.py",
    # 24 Nov 2026 fix round (DeepSeek final review): Drive backup
    # scripts + staging evidence for the submitted build, and the
    # logo source files. Working files of the submission round, not
    # stray changes.
    "backup-submission-evidence.py", "backup-submission-evidence-2.py",
    "backup-submission-evidence-3.py",
    "demo/media-generation-rwa-radar-logo-0-7342bc47-4a82-4d5b-9dca-bdc9ded8765f.webp",
    "demo/media-generation-rwa-radar-logo-1795447173.json",
    # 24 Nov 2026 post-submit close-out: the Cloudflare Pages deploy
    # script, the .gitignore that keeps the generated deploy dir and
    # wrangler cache out of the repo, and the one live snapshot that
    # backs the deployed dashboard (out/ stays ignored otherwise).
    "deploy_pages.py", ".gitignore", "out/cmc_snapshot.json",
}
ALLOWED_PREFIXES = ("evidence/cmc/", "demo/shots/", "demo/segments/",
                    "demo/segments-x/", "demo/qa-frames/",
                    "demo/qa-frames-x/", "demo/title-cards/",
                    "calibration/", "submission-evidence/")


def item9_repo_clean():
    """(a) .env.local is not tracked; (b) the actual API key value
    (read from .env.local in memory, never printed) appears in NO
    tracked file and in NO file on disk under the repo (exact-value
    scan — a random 3-byte match inside a .webm is not a match);
    (c) no JWT-looking token string in tracked text files;
    (d) no Base prototype file (DESIGN-CMC-RWA.md §4.2) remains;
    (e) `git status` shows only files this milestone intended to
    change."""
    _check, ok = _check_box()

    def _git(*args):
        return subprocess.run(["git"] + list(args), cwd=str(REPO),
                              capture_output=True, text=True)

    # (a) .env.local not tracked
    r = _git("ls-files")
    tracked = [line for line in r.stdout.splitlines() if line]
    _check(".env.local" not in tracked, ".env.local is not tracked",
           ".env.local" if ".env.local" in tracked else "absent",
           "absent")
    _check((REPO / ".env.local").is_file(),
           ".env.local exists locally (key available for live checks)")

    # (b) exact key value nowhere on disk (tracked or not, except .git
    # and __pycache__); the value is held in memory only, never printed.
    try:
        key = ad._load_api_key()
    except ad.CmcKeyError as exc:
        _check(False, "API key loads from .env.local (%s)" % exc)
        return ok()
    key_bytes = key.encode("utf-8")
    hits = []
    for path in REPO.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(REPO))
        if rel.startswith(".git/") or "__pycache__" in rel:
            continue
        if rel == ".env.local":
            continue
        if key_bytes in path.read_bytes():
            hits.append(rel)
    _check(not hits, "API key value appears in no file on disk",
           hits or "none", "none")

    # (c) no JWT-looking token string in tracked TEXT files (git grep
    # -I skips binaries). The pattern is built as "ey" + "J" so this
    # very file does not contain the literal it greps for.
    r = _git("grep", "-I", "-l", "ey" + "J", "--", ".")
    _check(r.returncode == 1, "no JWT-looking token string in tracked "
           "text files (git grep exit 1 = no match)",
           r.stdout.strip() or "none", "none")

    # (d) no Base prototype files remain
    leftovers = [name for name in BASE_FILES
                 if (REPO / name).exists()
                 and name not in ("fixtures", "evidence")]
    _check(not leftovers, "no Base prototype files remain",
           leftovers or "none", "none")
    _check((REPO / "fixtures").is_dir()
           and sorted(p.name for p in (REPO / "fixtures").iterdir())
           == ["cmc"], "fixtures/ holds only fixtures/cmc")
    _check((REPO / "evidence").is_dir()
           and sorted(p.name for p in (REPO / "evidence").iterdir())
           == ["cmc"], "evidence/ holds only evidence/cmc")

    # (e) git status: only intended changes. -uall lists untracked
    # files individually (without it, git collapses a whole new
    # directory to one "evidence/" line).
    r = _git("status", "--porcelain", "-uall")
    changed = []
    for line in r.stdout.splitlines():
        path = line[3:] if len(line) > 3 else line
        # Renames show as "old -> new"; take the new side.
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        changed.append(path.strip().strip('"'))
    unexpected = [p for p in changed
                  if p not in ALLOWED_CHANGED
                  and not p.startswith(ALLOWED_PREFIXES)]
    _check(not unexpected,
           "git status shows only intended changes (%d changed)"
           % len(changed), unexpected or "all intended", "all intended")
    if changed:
        print("    changed: %s" % ", ".join(sorted(changed)))
    return ok()


# ---------------------------------------------------------------------------
# Item 10 — submission package (SUBMISSION + README + video + post)
# ---------------------------------------------------------------------------

def _video_duration(path):
    """Duration in seconds via ffprobe, or None when unavailable."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=60)
        return float((r.stdout or "").strip())
    except Exception:  # noqa: BLE001
        return None


def item10_submission():
    """The submission package is complete and internally consistent:
    SUBMISSION.md names the repo, track, all seven endpoints, the
    evidence manifest and the X-post draft (<= 280 chars by X's count,
    URL = 23); README.md carries the API note, the universe wording and
    the robust method with no stale live numbers; both videos exist
    with the right durations; the evidence manifest's SHA-256 values
    all match the files on disk."""
    import hashlib
    import re

    _check, ok = _check_box()
    sub = (REPO / "SUBMISSION.md").read_text(encoding="utf-8")
    readme = (REPO / "README.md").read_text(encoding="utf-8")

    _check("https://github.com/rwnliwan/cmc-rwa-radar" in sub,
           "SUBMISSION names the public repo", "", "")
    _check("Real World Assets" in sub, "SUBMISSION names the track")
    for ep in ("/v5/real-world-assets/map",
               "/v5/real-world-assets/assets/list",
               "/v5/real-world-assets/quotes/latest",
               "/v5/real-world-assets/quotes/historical",
               "/v5/real-world-assets/info",
               "/v5/real-world-assets/issuers/list",
               "/v5/real-world-assets/issuers"):
        _check(ep in sub, "SUBMISSION names endpoint %s" % ep)
    _check("market-pairs/list" in sub and "NOT used" in sub,
           "SUBMISSION states market-pairs/list is NOT used")
    _check("evidence/cmc/manifest.json" in sub,
           "SUBMISSION references the evidence manifest")
    _check("https://dorahacks.io/hackathon/coinmarketcap-api-202611/detail"
           in sub, "SUBMISSION links the DoraHacks hackathon page")
    _check("#BuildwithCMC" in sub, "SUBMISSION draft has #BuildwithCMC")

    # X-post draft: the blockquote under "Draft post on X", counted
    # the way X counts (every URL = 23 characters). The draft links
    # the PROJECT submission page — the real Build URL since the
    # 23 Nov 2026 submission (was the placeholder
    # [DORAHACKS-PROJECT-URL] before submission; the hackathon
    # landing page is NOT a submission link, and the gate must not
    # accept it as one).
    section = sub.split("## Draft post on X", 1)[1]
    lines = [ln[2:].strip() for ln in section.splitlines()
             if ln.startswith("> ")]
    draft = " ".join(lines)
    counted = re.sub(r"https?://\S+", "x" * 23, draft)
    counted = counted.replace("[DORAHACKS-PROJECT-URL]", "x" * 23)
    _check(bool(draft) and len(counted) <= 280,
           "X-post draft is %d chars (URL=23), fits 280" % len(counted),
           len(counted), "<= 280")
    _check("#BuildwithCMC" in draft, "X-post draft carries #BuildwithCMC")
    _check("dorahacks.io/build/51722" in draft,
           "X-post draft links the project submission page "
           "(Build 51722, submitted 23 Nov 2026)")
    _check("dorahacks.io/hackathon/coinmarketcap-api-202611/detail"
           not in draft,
           "X-post draft does NOT link the hackathon landing page "
           "as the submission")
    _check("NVDA 0.99%" in draft and "suspected mixed underlying" in draft
           and "flags for dispersion & data quality" in draft,
           "X-post draft displays raw ranges (NVDA 0.99%, SPCX 304%) "
           "and flags dispersion/data quality separately — NVDA is "
           "not paired with flag language (it is not flagged)")

    _check("What the CMC API made possible" in readme,
           "README carries the explicit API note")
    _check("universe of 4,812" in readme,
           "README says universe of 4,812 (not 'screens 4,812')")
    _check("robust" in readme.lower(),
           "README documents the robust spread metric")
    # The 0.086% figure may appear ONLY in the historical correction
    # note ("first design draft ... truncated") — never as a live claim.
    stale_0086 = []
    for text, name in ((readme, "README.md"), (sub, "SUBMISSION.md")):
        for ln in text.splitlines():
            if "0.086" in ln and "truncated" not in ln \
                    and "first design draft" not in ln:
                stale_0086.append("%s: %s" % (name, ln.strip()))
    _check(not stale_0086,
           "0.086% appears only in the historical correction note",
           stale_0086 or "only in the correction note", "only there")
    _check("2.0% (EXTREME)" not in readme
           and "2.0% (EXTREME)" not in sub,
           "no stale 2.0% EXTREME threshold in README/SUBMISSION")
    _check("EXTREME > 1.0%" not in readme
           and "EXTREME > 1.0%" not in sub
           and "issuer_spread_extreme" not in readme
           and "issuer_spread_extreme" not in sub,
           "no second-level (EXTREME) threshold language in "
           "README/SUBMISSION — one binary flag only")
    # The empirical sentence may wrap across lines in the README, so
    # the check collapses whitespace before searching — the sentence
    # is what matters, not its line breaks.
    _readme_flat = " ".join(readme.split())
    _check("Thresholds are empirically derived from a single live "
           "snapshot" in _readme_flat,
           "README states the threshold is empirically derived from a "
           "single live snapshot (not 'calibrated')")
    _check("0.924%" in readme and "p83" in readme,
           "README quotes the corrected p90 (0.924%, linear "
           "interpolation) and the 0.5% line at ~p83",
           "", "")
    _check("0.597%" not in readme and "0.597%" not in sub,
           "the stale floor-index p90 (0.597%) is gone from "
           "README/SUBMISSION")
    _check("One stray token cannot move it" not in readme
           and "One stray token cannot move it" not in sub,
           "the false 'one stray token cannot move it' claim is gone")
    _check("exploratory heuristic" in readme,
           "README calls the 0.5% line an exploratory heuristic")
    # Deadline: 9 Dec 23:59 UTC = 10 Dec 07:59 WITA (not 08:00).
    design = (REPO / "DESIGN-CMC-RWA.md").read_text(encoding="utf-8")
    for text, name in ((readme, "README.md"), (sub, "SUBMISSION.md"),
                       (design, "DESIGN-CMC-RWA.md")):
        deadline_lines = [ln for ln in text.splitlines()
                          if "23:59 UTC" in ln and "WITA" in ln]
        _check(bool(deadline_lines)
               and all("07:59" in ln and "08:00" not in ln
                       for ln in deadline_lines),
               "%s deadline reads 10 Dec 07:59 WITA (not 08:00)"
               % name, deadline_lines, "07:59")
    _check("video-final-x.mp4" in readme,
           "README points at the X cut (not Premium)")

    full = REPO / "demo" / "video-final.mp4"
    xcut = REPO / "demo" / "video-final-x.mp4"
    _check(full.is_file(), "demo/video-final.mp4 exists")
    _check(xcut.is_file(), "demo/video-final-x.mp4 exists")
    dur = _video_duration(full)
    _check(dur is not None and 120.0 <= dur <= 180.0,
           "full video is 2-3 min (%.2fs)" % (dur or -1), dur, "120-180")
    dur_x = _video_duration(xcut)
    _check(dur_x is not None and dur_x <= 140.0,
           "X cut is <= 140s (%.2fs)" % (dur_x or -1), dur_x, "<= 140")

    manifest = json.loads(
        (REPO / "evidence" / "cmc" / "manifest.json")
        .read_text(encoding="utf-8"))
    files = manifest.get("files", {})
    _check(len(files) == 6, "evidence manifest lists 6 files",
           len(files), 6)
    bad = []
    for name, meta in files.items():
        blob = (REPO / "evidence" / "cmc" / name).read_bytes()
        if hashlib.sha256(blob).hexdigest() != meta.get("sha256"):
            bad.append(name)
    _check(not bad, "evidence manifest SHA-256 6/6 match",
           bad or "all match", "all match")
    return ok()


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

ITEMS = [
    ("1", "all backbone endpoints live (200 + shape)", item1_live_endpoints),
    ("2", "spread from stored quotes fixture", item2_spread_fixture),
    ("3", "% change from stored historical fixture", item3_changes_fixture),
    ("4", "edge cases (synthetic + live null-row check)", item4_edge_cases),
    ("5", "fail-closed (simulated error + adapter retry)", item5_fail_closed),
    ("6", "credit budget measured live (<= 100/hour)", item6_credit_budget),
    ("7", "dashboard renders from a live snapshot", item7_dashboard),
    ("8", "demo end-to-end (run_demo.sh exit 0)", item8_demo),
    ("9", "repo clean (no key, no Base files, intended changes only)", item9_repo_clean),
    ("10", "submission package (SUBMISSION + README + video + post)",
     item10_submission),
]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", default=str(REPO / "fixtures" / "cmc"),
                        help="fixture directory (default: fixtures/cmc)")
    parser.add_argument("--only", default=None,
                        help="run only item N (e.g. --only 6); "
                             "useful while debugging one item")
    args = parser.parse_args(argv)
    fixture_dir = Path(args.fixtures)
    print("gate_cmc — checks 1-10 (DESIGN-CMC-RWA.md §5.3)")
    print("fixtures: %s" % fixture_dir)
    results = {}
    for num, label, fn in ITEMS:
        if args.only and num != args.only:
            continue
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
    print("gate_cmc: %d/%d PASS" % (passed, len(results)))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
