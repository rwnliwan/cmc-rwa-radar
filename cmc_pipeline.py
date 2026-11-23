"""RWA Radar — pipeline: issuer spread, % change, reason codes, snapshot.

Written for the "Build with CMC: API Hackathon, Round 2" (Real World Assets
track). Python 3.10+ standard library only.

This module NEVER talks to the network and NEVER reads the API key: it
works on parsed CMC envelopes (as returned by cmc_adapter, or loaded from
fixtures/cmc/). The CLI (cmc_run.py, milestone 26) wires adapter -> pipeline.

Formulas (DESIGN-CMC-RWA.md §3.3):
- Issuer spread, from `tokens[]` ONLY, priced tokens only (nulls excluded):
      spread_abs = max(priced) - min(priced)
      spread_pct = spread_abs / average_tokenized_price * 100
      dev_i      = (price_i - average_tokenized_price)
                   / average_tokenized_price * 100
  The aggregate `average_tokenized_price` is an INDEPENDENT reference for
  dev_i, never assumed to equal the mean of tokens[] (live data shows it
  is not: 23 Nov 12:26 it was BELOW the cheapest priced token).
  If the aggregate is missing, the mean of priced tokens is used as the
  denominator instead and recorded as such — never silently swapped.
- % change from `quotes/historical` daily closes (no percent-change field
  exists in list/quotes — verified live):
      chg_24h = (close_last - close_prev) / close_prev * 100
      chg_7d  = (close_last - close_7d_ago) / close_7d_ago * 100
  Daily bars for stocks/ETFs start at midnight New York, not UTC.
- Thresholds are EXPERIMENTAL (config): SPREAD_WATCH_PCT = 0.5%,
  SPREAD_EXTREME_PCT = 2.0%. They are guesses from one observation, not
  calibrated — never present them as calibrated.
- Mixed underlying (config MIXED_UNDERLYING_MEDIAN_DEVIATION_PCT =
  50%): a priced token deviating from the MEDIAN priced token by more
  than 50% gets reason code `mixed_underlying` (non-blocking). The
  token is NEVER dropped from the spread — the extreme spread is
  explained, not hidden. Live case: SPCX, 10 tokens ~$131 plus
  SPACEX PreStocks ~$531 and tSpaceX ~$512 (spread 305%).

Decisions are honest monitor states, never investment advice:
OK / WATCH / NO_SIGNAL (design §3.3).
"""

import copy
import hashlib
import json
import statistics
from datetime import datetime, timezone

import cmc_config as cfg

BLOCKING_CODES = {"no_tokens", "all_prices_null", "thin_issuer_count"}

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

def _token_entry(token, denominator):
    price = token.get("price")
    dev = None
    if isinstance(price, (int, float)) and denominator:
        dev = (price - denominator) / denominator * 100.0
    return {
        "symbol": token.get("symbol"),
        "issuer_name": token.get("issuer_name"),
        "price": price,
        "dev_pct": dev,
    }


def compute_spread(quote):
    """Compute the issuer spread for one quote asset.

    Returns None when the asset carries no per-token data at all (e.g. a
    board row from assets/list, which has no tokens[] — spread simply does
    not apply there). Otherwise a dict with status "ok" | "no_tokens" |
    "all_prices_null" | "thin_issuer_count".
    """
    if quote.get("has_tokens") is False:
        return {"status": "no_tokens", "priced_count": 0, "null_count": 0,
                "spread_abs": None, "spread_pct": None, "tokens": []}
    tokens = quote.get("tokens")
    if tokens is None:
        return None
    priced = [t for t in tokens
              if isinstance(t.get("price"), (int, float))]
    null_count = len(tokens) - len(priced)
    if not priced:
        return {"status": "all_prices_null", "priced_count": 0,
                "null_count": null_count, "spread_abs": None,
                "spread_pct": None, "tokens": []}
    avg = quote.get("average_tokenized_price")
    if isinstance(avg, (int, float)) and avg:
        denominator, denom_source = avg, "average_tokenized_price"
    else:
        denominator = sum(t["price"] for t in priced) / len(priced)
        denom_source = "mean_priced"
    if len(priced) < 2:
        return {"status": "thin_issuer_count", "priced_count": len(priced),
                "null_count": null_count, "spread_abs": None,
                "spread_pct": None, "spread_denominator": denom_source,
                "average_tokenized_price": avg,
                "tokens": [_token_entry(t, denominator) for t in priced]}
    prices = [t["price"] for t in priced]
    lo, hi = min(prices), max(prices)
    spread_abs = hi - lo
    # Mixed-underlying detection: a token priced far from the MEDIAN
    # priced token is almost certainly a different instrument grouped
    # under the same rwa_id (live: SPCX ~$131 vs SPACEX ~$531 / tSpaceX
    # ~$512). The spread is still computed over ALL priced tokens —
    # nothing is silently dropped — but the outliers are listed and the
    # reason code `mixed_underlying` explains the extreme spread.
    median = statistics.median(prices)
    outliers = [t.get("symbol") for t in priced
                if median and abs(t["price"] - median) / median * 100.0
                > cfg.MIXED_UNDERLYING_MEDIAN_DEVIATION_PCT]
    return {
        "status": "ok",
        "priced_count": len(priced),
        "null_count": null_count,
        "spread_abs": spread_abs,
        "spread_pct": spread_abs / denominator * 100.0,
        "spread_denominator": denom_source,
        "average_tokenized_price": avg,
        "median_price": median,
        "outlier_tokens": outliers,
        "min_price": lo,
        "max_price": hi,
        "tokens": [_token_entry(t, denominator) for t in priced],
    }


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
# % change + sparkline (from quotes/historical daily closes)
# ---------------------------------------------------------------------------

def compute_changes(hist_asset):
    """Compute % change + sparkline from one historical asset.

    `hist_asset` is one entry of a quotes/historical envelope's
    data.rwa_assets — its `quotes` list holds the daily points
    (timestamp + average_tokenized_price). Fewer than 2 points means
    history_short and % change is None (never 0%).
    """
    points = (hist_asset or {}).get("quotes") or []
    closes = [p["average_tokenized_price"] for p in points
              if isinstance(p.get("average_tokenized_price"), (int, float))]
    out = {
        "n_points": len(closes),
        "spark": closes,
        "day_start": cfg.HISTORICAL_DAY_START,
        "chg_24h": None,
        "chg_7d": None,
        "history_short": len(closes) < 2,
    }
    if len(closes) >= 2:
        out["chg_24h"] = (closes[-1] - closes[-2]) / closes[-2] * 100.0
    if len(closes) >= 8:
        out["chg_7d"] = (closes[-1] - closes[-8]) / closes[-8] * 100.0
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
        elif status == "thin_issuer_count":
            codes.append("thin_issuer_count")
        elif status == "ok":
            if spread["null_count"] > 0:
                codes.append("partial_prices_null")
            if spread.get("outlier_tokens"):
                codes.append("mixed_underlying")
            pct = spread.get("spread_pct")
            if pct is not None:
                if pct > cfg.SPREAD_EXTREME_PCT:
                    codes.append("issuer_spread_extreme")
                elif pct > cfg.SPREAD_WATCH_PCT:
                    codes.append("issuer_spread_watch")
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
    """OK / WATCH / NO_SIGNAL from reason codes (blocking codes first)."""
    if any(c in BLOCKING_CODES for c in codes):
        return DECISION_NO_SIGNAL
    if codes:
        return DECISION_WATCH
    return DECISION_OK


def explain(row):
    """One human-readable paragraph for a snapshot row (for CLI/UI)."""
    parts = ["%s · %s · rwa_id %s — %s" % (
        row.get("name"), row.get("symbol"), row.get("rwa_id"),
        row.get("decision"))]
    spread = row.get("spread") or {}
    if spread.get("status") == "ok":
        parts.append("issuer spread %.3f%% (%d priced, %d null)" % (
            spread["spread_pct"], spread["priced_count"],
            spread["null_count"]))
    changes = row.get("changes") or {}
    if changes.get("chg_24h") is not None:
        parts.append("24h %+.2f%%" % changes["chg_24h"])
    if changes.get("chg_7d") is not None:
        parts.append("7d %+.2f%%" % changes["chg_7d"])
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
    body = {
        "schema": cfg.SCHEMA_VERSION,
        "method": cfg.METHOD_VERSION,
        "policy": cfg.POLICY_VERSION,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
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
