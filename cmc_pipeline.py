"""RWA Radar — pipeline: issuer spread, % change, reason codes, snapshot.

Written for the "Build with CMC: API Hackathon, Round 2" (Real World Assets
track). Python 3.10+ standard library only.

This module NEVER talks to the network and NEVER reads the API key: it
works on parsed CMC envelopes (as returned by cmc_adapter, or loaded from
fixtures/cmc/). The CLI (cmc_run.py, milestone 26) wires adapter -> pipeline.

Formulas (DESIGN-CMC-RWA.md §3.3, binary flag 23 Nov 2026 — method
v0.4.0):
- Issuer spread (REPORTED, from `tokens[]` ONLY, priced tokens only,
  nulls excluded):
      spread_abs = max(priced) - min(priced)
      spread_pct = spread_abs / average_tokenized_price * 100
      dev_i      = (price_i - average_tokenized_price)
                   / average_tokenized_price * 100
      dev_med_i  = (price_i - median(priced)) / median(priced) * 100
  The numerator is tokens[]; the denominator IS the aggregate
  `average_tokenized_price` (or the mean of priced tokens when the
  aggregate is missing, recorded as such — never silently swapped).
  The aggregate is an INDEPENDENT reference for dev_i, never assumed
  to equal the mean of tokens[] (live data shows it is not: 23 Nov
  12:26 it was BELOW the cheapest priced token). dev_med_i — each
  token's deviation from the MEDIAN priced token — is the per-token
  breakdown shown next to every flagged asset (board + detail pane).
  The metric is CROSS-TOKEN DISPERSION grouped by CMC RWA ID:
  token-weighted, NOT issuer-balanced — one issuer can contribute
  several tokens (live: Backed contributes both NVDAX and WNVDAX to
  NVDA), so the token count and the distinct-issuer count are
  reported separately and more tokens from one issuer change its
  influence. Token deviations are sorted to aid inspection; that
  order is NOT a causal attribution of the IQR flag.
- Robust spread (DECISION metric, from `tokens[]` ONLY):
      robust_spread_pct = (Q3 - Q1) / median * 100
  where Q1/median/Q3 are the inclusive quartiles of the priced token
  prices. The decision metric measures CENTRAL DISPERSION across
  priced token observations using inclusive IQR/median. It is less
  sensitive than max-min to isolated extreme quotes, but is NOT
  immune to them, especially in small token sets: with three priced
  tokens [100, 100, 110] the robust spread is 5.0% (flagged), and
  eight tokens at 100 plus one at 160 give 0.0% (a 60% isolated
  discrepancy reads OK). Large individual deviations remain visible
  separately, in the tokens table. On the live 23 Nov board the raw
  max-min spread flagged 23/23 assets WATCH, while the robust spread
  separates a tight bulk (median 0.265%) from a real tail.
  The 0.5% threshold is an EXPLORATORY HEURISTIC, chosen after
  inspecting one top-25 snapshot with 23 covered assets (23 Nov
  2026; robust median 0.265%, p75 0.440%, p90 0.924% by linear
  interpolation — reproduced from the stored snapshot by
  calibration/recompute_calibration.py). It is NOT a statistically
  validated anomaly threshold, risk score or trading signal. v0.3.0
  removed the second cut point (EXTREME 1.0%) — a sample of n=23
  from one snapshot cannot defend two cut points, so the decision
  is binary: flagged or not flagged. The raw spread_pct is still
  reported as-is and the extreme tokens are still listed; nothing
  is hidden.
- Mixed underlying (config, line 100% since 23 Nov 2026): a priced
  token deviating from the MEDIAN priced token by more than 100%
  gets reason code `mixed_underlying` (non-blocking) — a SUSPECTED
  COMPARABILITY ISSUE, not a proven different underlying. Extreme
  price deviation: investigate possible mapping, unit, freshness or
  instrument differences. Price alone does not establish a different
  underlying. The token is NEVER dropped from the spread — the
  extreme spread is shown, not hidden. Live case: SPCX, 10 tokens
  ~$131 plus SPACEX PreStocks ~$531 and tSpaceX ~$512 (spread
  305%).
- Decisions: OK / WATCH / NO_SIGNAL. Blocking codes (no_tokens,
  all_prices_null, thin_token_count, empty_tokens, missing_tokens,
  single_issuer) -> NO_SIGNAL.
  Flag codes (mixed_underlying, issuer_spread_flag, stale_quote) ->
  WATCH. The spread flag is BINARY (v0.3.0): robust spread above the
  single 0.5% line flags the asset, below it does not — there is no
  second level. partial_prices_null and history_short are
  INFORMATIONAL: listed in reason_codes and shown in the UI, but they
  do not by themselves force WATCH — a missing price is a completeness
  note, not a price signal.

Decisions are honest monitor states, never investment advice:
OK / WATCH / NO_SIGNAL (design §3.3). WATCH means "flagged" — the
asset's robust spread crossed the single empirical line, or a
non-blocking flag (mixed underlying / stale quote) applies.
"""

import copy
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone

import cmc_config as cfg

BLOCKING_CODES = {"no_tokens", "all_prices_null", "thin_token_count",
                  "empty_tokens", "missing_tokens", "single_issuer"}
# Codes that by themselves force a WATCH decision. partial_prices_null
# and history_short are deliberately NOT here (see module docstring).
# issuer_spread_flag is the single binary spread flag (v0.3.0) — the
# old issuer_spread_watch / issuer_spread_extreme pair is gone.
WATCH_CODES = {"mixed_underlying", "issuer_spread_flag", "stale_quote"}

DECISION_OK = "OK"
DECISION_WATCH = "WATCH"
DECISION_NO_SIGNAL = "NO_SIGNAL"


# ---------------------------------------------------------------------------
# Envelope helpers
# ---------------------------------------------------------------------------

def assets_from_envelope(envelope):
    """Return the list of assets in a CMC RWA envelope (map/list/quotes/
    historical all nest them under data.rwa_assets)."""
    if not isinstance(envelope, dict):
        return []
    data = envelope.get("data") or {}
    return data.get("rwa_assets") or []


def resolve_asset(map_envelope, symbol, asset_type=None):
    """Resolve a ticker to ONE asset via the map envelope.

    A symbol is NOT unique across asset types (e.g. SPCX exists as both an
    equity and another type), so the caller should pass asset_type
    (usually "stock"). Returns the single matching asset, or None when
    there is no match — or when the symbol is ambiguous and no
    asset_type was given (never guess).
    """
    matches = [a for a in assets_from_envelope(map_envelope)
               if a.get("symbol") == symbol]
    if asset_type is not None:
        matches = [a for a in matches if a.get("asset_type") == asset_type]
    if len(matches) == 1:
        return matches[0]
    return None


# ---------------------------------------------------------------------------
# Issuer spread (from quotes/latest tokens[])
# ---------------------------------------------------------------------------

def _is_priced(price):
    """A usable token price: a real finite number STRICTLY GREATER
    THAN ZERO. Booleans are ints in Python (True == 1) and NaN/inf
    are floats — neither is a price — and zero is not a valid price
    either (it would divide by zero in the change math and means
    "no price" in the data, not a free token). All three are rejected
    here and counted as null, never priced."""
    return (isinstance(price, (int, float))
            and not isinstance(price, bool)
            and math.isfinite(price)
            and price > 0)


def _issuer_key(token):
    """Stable identity of the token's issuer: issuer_id when the
    response carries it, else the issuer_name. Two tokens sharing
    one key are one issuer's tokens, not two independent issuers
    (live: Backed's NVDAX and WNVDAX share one issuer_id)."""
    return token.get("issuer_id") or token.get("issuer_name")


def _token_entry(token, denominator, median=None):
    """One token row: symbol + issuer + stable issuer ids + price +
    deviation from the aggregate (dev_pct) + deviation from the
    MEDIAN priced token (dev_median_pct). The median deviation is
    the per-token breakdown shown next to flagged assets — token
    deviations are sorted to aid inspection; that order is NOT a
    causal attribution of the IQR flag. Either deviation is None
    when its reference is unavailable."""
    price = token.get("price")
    dev = None
    if _is_priced(price) and denominator and math.isfinite(denominator):
        dev = (price - denominator) / denominator * 100.0
    dev_med = None
    if _is_priced(price) and median and math.isfinite(median):
        dev_med = (price - median) / median * 100.0
    return {
        "symbol": token.get("symbol"),
        "issuer_name": token.get("issuer_name"),
        "issuer_id": token.get("issuer_id"),
        "crypto_id": token.get("crypto_id"),
        "price": price,
        "dev_pct": dev,
        "dev_median_pct": dev_med,
    }


def _robust_spread_pct(prices):
    """Interquartile spread of the priced token prices, relative to the
    median: (Q3 - Q1) / median * 100. Inclusive quartiles (linear
    interpolation, statistics.quantiles method="inclusive"). Requires
    >= 2 prices; returns None otherwise. The IQR measures the middle
    50% of the priced tokens, so it is LESS sensitive than max-min to
    one extreme quote — not immune to it (see the module docstring
    for the thin-set counterexamples)."""
    if len(prices) < 2:
        return None
    q1, median, q3 = statistics.quantiles(prices, n=4, method="inclusive")
    if not median:
        return None
    return (q3 - q1) / median * 100.0


def compute_spread(quote):
    """Compute the issuer spread for one quote asset.

    NEVER returns None: every outcome is a dict with a status, so a
    caller can never mistake "no per-token data" for "no problem".
    Statuses: "ok" | "no_tokens" | "all_prices_null" |
    "thin_token_count" | "empty_tokens" | "missing_tokens" |
    "single_issuer".
    "missing_tokens" means has_tokens is true but the `tokens` field
    is ABSENT — the required per-token data is missing, so the asset
    is NO_SIGNAL, never OK with no spread. "empty_tokens" means
    tokens[] exists but is EMPTY (has_tokens says True, yet no token
    objects came back) — distinct from "all_prices_null" (tokens
    exist, every price is null) and from "no_tokens" (has_tokens is
    False). "thin_token_count" means fewer than 2 PRICED TOKENS
    (renamed 23 Nov 2026 — the old name `thin_issuer_count` counted
    tokens, not issuers). "single_issuer" means >= 2 priced tokens
    but from ONE distinct issuer — a spread across one issuer's own
    tokens is not a cross-issuer comparison, so it is NO_SIGNAL too;
    the spread numbers are still filled in (the data is real, just
    not a cross-issuer signal). The reported spread_pct is the raw
    max-min spread; robust_spread_pct is the IQR/median decision
    metric. Every token entry carries issuer_id + crypto_id (stable
    ids) and dev_median_pct — its deviation from the MEDIAN priced
    token — the per-token breakdown shown next to flagged assets
    (board + detail pane). token_count is the PRICED-token count
    (= priced_count); issuer_count is the DISTINCT-issuer count among
    priced tokens; null_count counts the unpriced tokens separately.
    """
    if quote.get("has_tokens") is False:
        return {"status": "no_tokens", "priced_count": 0, "null_count": 0,
                "token_count": 0, "issuer_count": 0,
                "spread_abs": None, "spread_pct": None,
                "robust_spread_pct": None, "tokens": []}
    tokens = quote.get("tokens")
    if tokens is None:
        # has_tokens is true (or unstated) but the tokens field is
        # missing: required per-token data absent -> NO_SIGNAL, never
        # a silent OK with no spread.
        return {"status": "missing_tokens", "priced_count": 0,
                "null_count": 0, "token_count": 0, "issuer_count": 0,
                "spread_abs": None, "spread_pct": None,
                "robust_spread_pct": None, "tokens": []}
    if len(tokens) == 0:
        return {"status": "empty_tokens", "priced_count": 0,
                "null_count": 0, "token_count": 0, "issuer_count": 0,
                "spread_abs": None, "spread_pct": None,
                "robust_spread_pct": None, "tokens": []}
    priced = [t for t in tokens if _is_priced(t.get("price"))]
    null_count = len(tokens) - len(priced)
    if not priced:
        return {"status": "all_prices_null", "priced_count": 0,
                "null_count": null_count,
                "token_count": 0, "issuer_count": 0,
                "spread_abs": None, "spread_pct": None,
                "robust_spread_pct": None, "tokens": []}
    avg = quote.get("average_tokenized_price")
    if _is_priced(avg) and avg:
        denominator, denom_source = avg, "average_tokenized_price"
    else:
        denominator = sum(t["price"] for t in priced) / len(priced)
        denom_source = "mean_priced"
    prices = [t["price"] for t in priced]
    median = statistics.median(prices)
    q1, _, q3 = statistics.quantiles(prices, n=4, method="inclusive") \
        if len(prices) >= 2 else (None, median, None)
    issuer_count = len({_issuer_key(t) for t in priced})
    token_rows = [_token_entry(t, denominator, median) for t in priced]
    if len(priced) < 2:
        return {"status": "thin_token_count",
                "priced_count": len(priced),
                "null_count": null_count,
                "token_count": len(priced), "issuer_count": issuer_count,
                "spread_abs": None, "spread_pct": None,
                "robust_spread_pct": None,
                "spread_denominator": denom_source,
                "average_tokenized_price": avg,
                "tokens": token_rows}
    lo, hi = min(prices), max(prices)
    spread_abs = hi - lo
    # Mixed-underlying detection: a token priced far from the MEDIAN
    # priced token is a SUSPECTED comparability issue (mapping, unit,
    # freshness or instrument differences are all possible — price
    # alone does not establish a different underlying). Live: SPCX
    # ~$131 vs SPACEX ~$531 / tSpaceX ~$512. The spread is still
    # computed over ALL priced tokens — nothing is silently dropped —
    # but the outliers are listed and the reason code
    # `mixed_underlying` marks the suspicion. Each outlier carries
    # symbol + issuer + stable ids + price (symbols alone are not
    # unique — NVDA appears under several issuers).
    outliers = [{"symbol": t.get("symbol"),
                 "issuer_name": t.get("issuer_name"),
                 "issuer_id": t.get("issuer_id"),
                 "crypto_id": t.get("crypto_id"),
                 "price": t.get("price")} for t in priced
                if median and abs(t["price"] - median) / median * 100.0
                > cfg.MIXED_UNDERLYING_MEDIAN_DEVIATION_PCT]
    result = {
        "status": "ok",
        "priced_count": len(priced),
        "null_count": null_count,
        "token_count": len(priced),
        "issuer_count": issuer_count,
        "spread_abs": spread_abs,
        "spread_pct": spread_abs / denominator * 100.0,
        "robust_spread_pct": _robust_spread_pct(prices),
        "spread_denominator": denom_source,
        "average_tokenized_price": avg,
        "median_price": median,
        "q1_price": q1,
        "q3_price": q3,
        "outlier_tokens": outliers,
        "min_price": lo,
        "max_price": hi,
        "tokens": token_rows,
    }
    if issuer_count < 2:
        # >= 2 priced tokens, one issuer: the numbers are real, but
        # they are not a cross-issuer comparison. Status (not "ok")
        # so the decision is NO_SIGNAL with code `single_issuer`.
        result["status"] = "single_issuer"
    return result


def partition_list_rows(assets):
    """Split an assets/list page into quotable ids and dropped rows.

    Live quirk (observed 23 Nov 2026): some list rows carry rwa_id=null
    (GOOG and a duplicate BRK.B row in the top-20). Those rows cannot be
    quoted by id at all — they are dropped here and reported by the
    caller, never silently counted as covered.
    Returns (ids, dropped_symbols): ids = [str(rwa_id), ...];
    dropped_symbols = [symbol or "?", ...] for rows with rwa_id None.
    """
    ids = [str(a["rwa_id"]) for a in assets
           if a.get("rwa_id") is not None]
    dropped = [a.get("symbol") or "?" for a in assets
               if a.get("rwa_id") is None]
    return ids, dropped


# ---------------------------------------------------------------------------
# % change + sparkline (from quotes/historical daily-period observations)
# ---------------------------------------------------------------------------

def compute_changes(hist_asset):
    """Compute % change + sparkline from one historical asset.

    `hist_asset` is one entry of a quotes/historical envelope's
    data.rwa_assets — its `quotes` list holds the daily-period points
    (timestamp + average_tokenized_price). Per the API reference each
    observation is the FIRST VALUE in its period, stamped at the
    period start — NOT a closing price — and periods without data are
    skipped. So the outputs are changes between the AVAILABLE
    daily-period observations, labelled with their ACTUAL dates:
      chg_prev   = (last - previous) / previous * 100, with
                    chg_prev_from / chg_prev_to = their period dates
      chg_8back  = (last - 8th-back) / 8th-back * 100, with dates
    A point is accepted only if it has a positive finite price AND a
    parseable timestamp (a zero price is not a valid price — it would
    divide by zero — and an undated point cannot be anchored).
    Fewer than 2 accepted points means history_short and % change is
    None (never 0%). The old names chg_24h / chg_7d are gone: the
    index arithmetic is the same, but two points dated 1 Jan and
    4 Jan are not a "24h change", and daily New York boundaries need
    not be exactly 24 elapsed hours across DST changes.
    """
    points = (hist_asset or {}).get("quotes") or []
    accepted = []
    for point in points:
        price = point.get("average_tokenized_price")
        if not _is_priced(price):
            continue
        stamp = _parse_ts(point.get("timestamp"))
        if stamp is None:
            continue
        accepted.append((stamp.date().isoformat(), price))
    values = [price for _, price in accepted]
    dates = [date for date, _ in accepted]
    out = {
        "n_points": len(values),
        "spark": values,
        "obs_dates": dates,
        "day_start": cfg.HISTORICAL_DAY_START,
        "chg_prev": None,
        "chg_prev_from": None,
        "chg_prev_to": None,
        "chg_8back": None,
        "chg_8back_from": None,
        "chg_8back_to": None,
        "history_short": len(values) < 2,
    }
    if len(values) >= 2:
        out["chg_prev"] = (values[-1] - values[-2]) / values[-2] * 100.0
        out["chg_prev_from"] = dates[-2]
        out["chg_prev_to"] = dates[-1]
    if len(values) >= 8:
        out["chg_8back"] = (values[-1] - values[-8]) / values[-8] * 100.0
        out["chg_8back_from"] = dates[-8]
        out["chg_8back_to"] = dates[-1]
    return out


# ---------------------------------------------------------------------------
# Reason codes + decision (design §3.3)
# ---------------------------------------------------------------------------

def _parse_ts(value):
    """Parse an ISO-8601 timestamp (with trailing Z) to an aware datetime."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def assess_asset(quote, spread, changes, context="board", now=None):
    """Return the list of reason codes for one asset.

    context "board" uses the 15-minute stale limit, "monitor" the 5-minute
    one (config). `now` is injectable for tests; defaults to UTC now.
    """
    codes = []
    if quote.get("has_tokens") is False:
        codes.append("no_tokens")
    elif spread is not None:
        status = spread.get("status")
        if status == "all_prices_null":
            codes.append("all_prices_null")
        elif status == "thin_token_count":
            codes.append("thin_token_count")
        elif status == "empty_tokens":
            codes.append("empty_tokens")
        elif status == "missing_tokens":
            codes.append("missing_tokens")
        elif status == "single_issuer":
            codes.append("single_issuer")
        elif status == "ok":
            if spread["null_count"] > 0:
                # Informational only (see module docstring): a missing
                # price is a completeness note, not a price signal.
                codes.append("partial_prices_null")
            if spread.get("outlier_tokens"):
                codes.append("mixed_underlying")
            # Spread decisions use the ROBUST metric, not the raw
            # max-min spread_pct (which is reported as-is). The flag
            # is BINARY (v0.3.0): one line at 0.5% robust — above it
            # the asset is flagged, below it is not.
            pct = spread.get("robust_spread_pct")
            if pct is not None and pct > cfg.ROBUST_SPREAD_FLAG_PCT:
                codes.append("issuer_spread_flag")
    else:
        # compute_spread never returns None; reaching here means the
        # caller passed no spread at all — treat as missing data.
        codes.append("missing_tokens")
    if changes is not None and changes.get("history_short"):
        codes.append("history_short")
    last = _parse_ts(quote.get("last_updated"))
    if last is not None:
        now = now or datetime.now(timezone.utc)
        limit = (cfg.STALE_QUOTE_BOARD_SECONDS if context == "board"
                 else cfg.STALE_QUOTE_MONITOR_SECONDS)
        if (now - last).total_seconds() > limit:
            codes.append("stale_quote")
    return codes


def decide(codes):
    """OK / WATCH / NO_SIGNAL from reason codes. Blocking codes first
    (-> NO_SIGNAL); then watch codes (-> WATCH); informational codes
    (partial_prices_null, history_short) alone mean OK — they are listed
    in reason_codes and shown in the UI, but they do not by themselves
    force a WATCH (see module docstring)."""
    if any(c in BLOCKING_CODES for c in codes):
        return DECISION_NO_SIGNAL
    if any(c in WATCH_CODES for c in codes):
        return DECISION_WATCH
    return DECISION_OK


def explain(row):
    """One human-readable paragraph for a snapshot row (for CLI/UI)."""
    parts = ["%s · %s · rwa_id %s — %s" % (
        row.get("name"), row.get("symbol"), row.get("rwa_id"),
        row.get("decision"))]
    spread = row.get("spread") or {}
    if spread.get("status") in ("ok", "single_issuer"):
        parts.append("issuer spread %.3f%% (%d priced tokens, %d "
                     "distinct issuers, %d null)" % (
            spread["spread_pct"], spread["priced_count"],
            spread.get("issuer_count", 0), spread["null_count"]))
        if spread.get("robust_spread_pct") is not None:
            parts.append("robust spread %.3f%% (IQR/median)" % (
                spread["robust_spread_pct"],))
    changes = row.get("changes") or {}
    if changes.get("chg_prev") is not None:
        parts.append("change vs prev daily-period obs (%s to %s) "
                     "%+.2f%%" % (changes.get("chg_prev_from"),
                                   changes.get("chg_prev_to"),
                                   changes["chg_prev"]))
    if changes.get("chg_8back") is not None:
        parts.append("change vs 8th-back daily-period obs (%s to %s) "
                     "%+.2f%%" % (changes.get("chg_8back_from"),
                                   changes.get("chg_8back_to"),
                                   changes["chg_8back"]))
    if row.get("reason_codes"):
        parts.append("codes: %s" % ", ".join(row["reason_codes"]))
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# Snapshot (canonical JSON + snapshot_id)
# ---------------------------------------------------------------------------

def _canonical_id(body):
    """snapshot_id = snap-<first 16 hex of sha256(canonical JSON body)>."""
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
    return "snap-" + hashlib.sha256(blob).hexdigest()[:16]


def build_snapshot(assets, historical_by_id=None, context="board",
                   now=None):
    """Build a canonical snapshot from quote assets.

    `assets` — list of quote-asset dicts (quotes/latest or assets/list
    rows). `historical_by_id` — optional {rwa_id: historical asset} for
    % change + sparkline. Returns the snapshot dict (with snapshot_id).
    """
    now = now or datetime.now(timezone.utc)
    historical_by_id = historical_by_id or {}
    rows = []
    for asset in assets:
        spread = compute_spread(asset)
        changes = None
        hist = historical_by_id.get(asset.get("rwa_id"))
        if hist is not None:
            changes = compute_changes(hist)
        codes = assess_asset(asset, spread, changes, context=context,
                             now=now)
        rows.append({
            "rwa_id": asset.get("rwa_id"),
            "symbol": asset.get("symbol"),
            "name": asset.get("name"),
            "asset_type": asset.get("asset_type"),
            "rwa_rank": asset.get("rwa_rank"),
            "has_tokens": asset.get("has_tokens"),
            "average_tokenized_price":
                asset.get("average_tokenized_price"),
            "tokenized_market_cap": asset.get("tokenized_market_cap"),
            "tokenized_volume_24h": asset.get("tokenized_volume_24h"),
            "last_updated": asset.get("last_updated"),
            "spread": spread,
            "changes": changes,
            "reason_codes": codes,
            "decision": decide(codes),
        })
    cadence = cfg.CADENCE[cfg.CREDIT_MODE]
    if context == "monitor":
        # The monitor rewrites the snapshot on every quotes cycle.
        expected_cadence = cadence["quotes_seconds"]
    else:
        # Board snapshots refresh on the board cadence; a one-shot
        # asset snapshot is judged against the same horizon — the
        # dashboard uses this to warn when the producer has stopped
        # (a stopped producer otherwise leaves a green OK on an old
        # snapshot; see dashboard/index.html age-banner).
        expected_cadence = cadence["board_seconds"]
    body = {
        "schema": cfg.SCHEMA_VERSION,
        "method": cfg.METHOD_VERSION,
        "policy": cfg.POLICY_VERSION,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expected_cadence_seconds": expected_cadence,
        "context": context,
        "credit_mode": cfg.CREDIT_MODE,
        "counts": {
            "assets": len(rows),
            "ok": sum(1 for r in rows if r["decision"] == DECISION_OK),
            "watch": sum(1 for r in rows
                         if r["decision"] == DECISION_WATCH),
            "no_signal": sum(1 for r in rows
                             if r["decision"] == DECISION_NO_SIGNAL),
        },
        "assets": rows,
    }
    body["snapshot_id"] = _canonical_id(body)
    return body


def public_snapshot(snapshot):
    """Public view of a snapshot: deep copy with every internal key
    (any key starting with "_") stripped, recursively."""
    def strip(obj):
        if isinstance(obj, dict):
            return {k: strip(v) for k, v in obj.items()
                    if not k.startswith("_")}
        if isinstance(obj, list):
            return [strip(v) for v in obj]
        return obj
    return strip(copy.deepcopy(snapshot))


# ---------------------------------------------------------------------------
# Fail-closed: API errors never invent data (design §3.5)
# ---------------------------------------------------------------------------

def apply_error(previous_snapshot, error):
    """Mark a snapshot stale after an API error — WITHOUT inventing data.

    Returns the previous snapshot unchanged (same rows, same snapshot_id)
    plus status "stale" and the reason. With no previous snapshot, returns
    an empty stale snapshot — never a fabricated one.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if previous_snapshot is None:
        return {"status": "stale", "stale_reason": str(error),
                "stale_at": now, "assets": [], "snapshot_id": None}
    out = copy.deepcopy(previous_snapshot)
    out["status"] = "stale"
    out["stale_reason"] = str(error)
    out["stale_at"] = now
    return out
