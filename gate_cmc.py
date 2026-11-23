"""Gate for the CMC RWA entry — checks 1–9 of DESIGN-CMC-RWA.md §5.3.

Usage:  python3 gate_cmc.py [--fixtures fixtures/cmc]
Prints PASS/FAIL per item; exit 0 only when ALL items pass.

Live items (they call the real CMC API — about 38 credits per full
run): 1 (backbone endpoints, ~6 cr), 4g (null-row check, 1 cr),
6 (budget measurement, 11 cr), 7 (dashboard, 5 cr: asset NVDA 3 +
board restore 2), 8 (demo run, ~15 cr). Items 2–5 are OFFLINE, from
the stored fixtures in fixtures/cmc/ — the live spread moves, so the
gate NEVER compares live data against fixture numbers with a tight
tolerance.

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

Budget reference (measured in item 6, not assumed): per-call credits
for list (1), quotes/latest for 20 ids (1), historical 20 ids x30
(6 = 600 points / 100), historical 10 ids x30 (3). Startup cadence
(board 5 min, quotes 60 s, historical 15 min) projects to 96 credits
per hour and ~69,270 per month (~15% of 450,000); Basic fallback
projects to ~6,840 per month (under the 10,000 dashboard figure).
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
    return ok()


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

    _check, ok = _check_box()
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
    return ok()


# ---------------------------------------------------------------------------
# Item 4 — edge cases (synthetic fixtures + one live null-row check)
# ---------------------------------------------------------------------------

def item4_edge_cases():
    """(a) has_tokens=false -> NO_SIGNAL + no_tokens; (b) all-null ->
    all_prices_null + NO_SIGNAL; (c) duplicate symbol across asset
    types resolves only via asset_type + rwa_id (never guessed);
    (d) thin issuer count (1 priced token) -> NO_SIGNAL +
    thin_issuer_count; (e) mixed underlying (SPCX-like: 10 tokens
    ~$131 + 2 tokens ~$512/$531) -> WATCH + mixed_underlying, spread
    UNCHANGED (nothing silently dropped), outliers listed;
    (f) partition_list_rows drops rwa_id=null rows; (g) LIVE:
    assets/list top-20 partitioned the same way — null rows (if any)
    are dropped and reported, never counted as covered."""
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

    # (d) thin issuer count: exactly 1 priced token
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
    _check("thin_issuer_count" in row["reason_codes"],
           "thin -> code thin_issuer_count",
           row["reason_codes"], "thin_issuer_count")
    _check(row["spread"]["status"] == "thin_issuer_count",
           "thin -> spread status thin_issuer_count",
           row["spread"]["status"], "thin_issuer_count")

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
                "price": 530.83},
               {"symbol": "tSpaceX", "issuer_name": "Tessera",
                "price": 511.93}]}
    spread = pl.compute_spread(spcx)
    _check(spread["outlier_tokens"] == ["SPACEX", "tSpaceX"],
           "SPCX-like outliers listed: SPACEX + tSpaceX",
           spread["outlier_tokens"], ["SPACEX", "tSpaceX"])
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
    _check("issuer_spread_extreme" in row["reason_codes"],
           "mixed underlying still flags issuer_spread_extreme",
           row["reason_codes"], "issuer_spread_extreme")

    # (e2) ordinary single-token outlier (AMZN-like, -20% from median)
    # stays BELOW the 50% line: no mixed_underlying, only extreme.
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
    _check("issuer_spread_extreme" in row["reason_codes"],
           "AMZN-like -> issuer_spread_extreme",
           row["reason_codes"], "issuer_spread_extreme")

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
    return ok()


# ---------------------------------------------------------------------------
# Item 6 — credit budget, MEASURED live (not assumed)
# ---------------------------------------------------------------------------

def _credit(env):
    return int((env.get("status") or {}).get("credit_count") or 0)


def item6_credit_budget():
    """Measure the real per-call credit cost of each cadence step, then
    project the hourly / monthly budget from the MEASURED numbers and
    the configured cadence (DESIGN-CMC-RWA.md §3.4). PASS: 1-hour
    monitor projection <= 100 credits; Startup monthly <= 450,000;
    Basic fallback monthly <= 10,000 (the conservative dashboard
    figure). Costs ~11 credits to measure."""
    _check, ok = _check_box()
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
    tokens table AND a rendered sparkline SVG. Afterwards the board
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
            _check("24h:" in detail,
                   "detail pane shows % change (24h/7d)")
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

# Paths the 29–30 Nov milestone is allowed to have changed (everything
# else in `git status` fails the item).
ALLOWED_CHANGED = {
    "cmc_config.py", "cmc_pipeline.py", "cmc_run.py", "gate_cmc.py",
    "capture_cmc_evidence.py", "README.md", "CMC_INTEGRATION.md",
    "DESIGN-CMC-RWA.md", "dashboard/index.html", "demo/capture.py",
    "demo/shot-list.md",
}
ALLOWED_PREFIXES = ("evidence/cmc/", "demo/shots/")


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
    print("gate_cmc — checks 1-9 (DESIGN-CMC-RWA.md §5.3)")
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
