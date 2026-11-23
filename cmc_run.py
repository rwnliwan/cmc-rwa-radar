"""RWA Radar — CLI: board / monitor / asset.

Written for the "Build with CMC: API Hackathon, Round 2" (Real World Assets
track). Python 3.10+ standard library only. Milestone 26 Nov
(DESIGN-CMC-RWA.md §4.1, §6).

Modes:
  board   (default) — top-N tokenised stocks by rwa_rank: assets/list +
          quotes/latest for those assets -> canonical snapshot + table.
  monitor           — poll quotes/latest for the default watchlist
          (top-20 by rank + optional --ticker) every `quotes_seconds`
          from the active credit-mode cadence; one line per asset per
          cycle; fail-closed via pipeline.apply_error (API error ->
          previous snapshot kept + marked stale, never invented data).
          --cycles N limits the run (demo); without it, runs forever.
  asset <rwa_id|symbol> — one asset in detail: company info + tokens[]
          + issuer spread + % change + sparkline from historical
          daily-period observations (count=30; each observation is
          the FIRST value in its period, not a close).

Read-only throughout: no trading, no wallet, no private key. Decisions
are monitor states (OK / WATCH / NO_SIGNAL) — never investment advice.
Daily bars for stocks/ETFs start at midnight New York, not UTC; the
output labels that explicitly.

The API key is read by cmc_adapter from .env.local at runtime and is
NEVER printed, logged, or written into any snapshot, fixture, or file
this CLI produces.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cmc_adapter as ad
import cmc_config as cfg
import cmc_pipeline as pipe

OUT_DIR = Path(__file__).resolve().parent / "out"

DISCLAIMER = "Monitor status only — not investment advice."

# WITA (Asia/Makassar) is UTC+8; used only for display next to UTC stamps.
WITA = timezone(timedelta(hours=8))


def _fmt_ts(dt):
    """UTC ISO stamp + WITA equivalent, for human-readable headers."""
    return "%s UTC (%s WITA)" % (
        dt.strftime("%Y-%m-%d %H:%M:%S"),
        dt.astimezone(WITA).strftime("%Y-%m-%d %H:%M:%S"))


def _fmt_price(value):
    return "—" if value is None else "%.2f" % value


def _fmt_spread(spread):
    if not spread or spread.get("status") != "ok":
        return "—"
    return "%.3f%%" % spread["spread_pct"]


def _fmt_robust(spread):
    """The decision metric (IQR/median) — shown next to the reported
    max-min spread so a verdict is explainable from the board."""
    if not spread or spread.get("status") != "ok":
        return "—"
    robust = spread.get("robust_spread_pct")
    return "—" if robust is None else "%.3f%%" % robust


# ---------------------------------------------------------------------------
# Credit accounting — every envelope carries status.credit_count.
# ---------------------------------------------------------------------------

class CreditMeter:
    """Sum of CMC credits spent by this run, per call."""

    def __init__(self):
        self.total = 0
        self.calls = []  # (label, credits)

    def record(self, envelope, label):
        n = (envelope.get("status") or {}).get("credit_count") or 0
        self.total += int(n)
        self.calls.append((label, int(n)))
        return envelope


def _call(meter, label, func, *args, **kwargs):
    return meter.record(func(*args, **kwargs), label)


# ---------------------------------------------------------------------------
# Snapshot writing — latest file + timestamped archive (design §3.2).
# ---------------------------------------------------------------------------

def write_snapshot(snapshot):
    """Write the canonical snapshot to out/cmc_snapshot.json and an
    archive copy out/cmc_snapshot_<ts>_<snapshot_id>.json. Returns the
    archive path."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    body = pipe.public_snapshot(snapshot)
    text = json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False)
    stamp = (snapshot.get("generated_at") or snapshot.get("stale_at")
             or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    stamp = stamp.replace("-", "").replace(":", "")
    sid = snapshot.get("snapshot_id") or "no-id"
    archive = OUT_DIR / ("cmc_snapshot_%s_%s.json" % (stamp, sid))
    archive.write_text(text, encoding="utf-8")
    (OUT_DIR / "cmc_snapshot.json").write_text(text, encoding="utf-8")
    return archive


# ---------------------------------------------------------------------------
# Shared fetch helpers
# ---------------------------------------------------------------------------

def _rank_order(list_assets):
    """rwa_id -> position in the assets/list ranking (for board order)."""
    return {a.get("rwa_id"): i for i, a in enumerate(list_assets)}


def fetch_board_ids(meter, limit):
    """assets/list top-`limit` stocks by rwa_rank. Returns (assets, ids).

    Live quirk (observed 23 Nov 2026): some list rows carry
    rwa_id=null (GOOG and a duplicate BRK.B row in the top-20) — those
    rows cannot be quoted by id at all, so they are dropped here and
    reported, never silently counted as covered."""
    env = _call(meter, "assets/list limit=%d" % limit, ad.fetch_list,
                asset_type=cfg.BOARD_ASSET_TYPE, sort=cfg.BOARD_SORT,
                limit=limit)
    assets = pipe.assets_from_envelope(env)
    ids, dropped = pipe.partition_list_rows(assets)
    if dropped:
        print("warning: assets/list returned %d row(s) with rwa_id=null "
              "(cannot be quoted): %s"
              % (len(dropped), ", ".join(dropped)), file=sys.stderr)
    return assets, ids


def fetch_quotes(meter, rwa_ids, label="quotes/latest"):
    """quotes/latest for a list of rwa_ids (one call, 1 credit/250)."""
    env = _call(meter, label, ad.fetch_quotes_latest,
                rwa_id=",".join(rwa_ids))
    return pipe.assets_from_envelope(env)


def fetch_historical_map(meter, rwa_ids, label="quotes/historical"):
    """quotes/historical daily x30 for a list of rwa_ids (one call).
    Returns {rwa_id: historical asset}. May raise CmcApiError (e.g. 403
    code 1014 out-of-window) — the caller decides how to degrade."""
    env = _call(meter, label, ad.fetch_historical,
                rwa_id=",".join(rwa_ids),
                interval=cfg.HISTORICAL_INTERVAL,
                count=cfg.HISTORICAL_COUNT)
    return {a.get("rwa_id"): a
            for a in pipe.assets_from_envelope(env)}


def historical_ids(ids, extra_rid, cap):
    """ids for the historical request, under the active mode's cap.

    The explicitly requested ticker goes FIRST when present (it is
    the asset the user asked to watch), then the ranked watchlist
    fills up to the cap. The result is at most `cap` ids — the cap
    is what the credit budget is derived from, so the request path
    must enforce it (a previous version sent the full watchlist and
    the documented Basic budget was wrong: 7,920/month instead of
    6,840)."""
    ordered = ([extra_rid] if extra_rid else []) + \
        [i for i in ids if i != extra_rid]
    return ordered[:cap]


# ---------------------------------------------------------------------------
# board
# ---------------------------------------------------------------------------

def _print_board_table(snapshot):
    rows = snapshot["assets"]
    print("rank  symbol  name                      avg USD     spread    "
          "robust    tokens  decision  reason codes")
    print("----  ------  ------------------------  ----------  --------  "
          "--------  ------  --------  ------------")
    for row in rows:
        codes = ",".join(row["reason_codes"]) or "-"
        spread = row.get("spread") or {}
        toks = ("%dt/%di" % (spread.get("token_count", 0),
                             spread.get("issuer_count", 0))
                if spread.get("status") in ("ok", "single_issuer")
                else "-")
        print("%4s  %-6s  %-24s  %10s  %8s  %8s  %6s  %-8s  %s" % (
            row.get("rwa_rank") if row.get("rwa_rank") is not None else "-",
            row.get("symbol") or "-",
            (row.get("name") or "-")[:24],
            _fmt_price(row.get("average_tokenized_price")),
            _fmt_spread(row.get("spread")),
            _fmt_robust(row.get("spread")),
            toks,
            row.get("decision"),
            codes))
    c = snapshot["counts"]
    print("assets=%d  OK=%d  WATCH=%d  NO_SIGNAL=%d"
          % (c["assets"], c["ok"], c["watch"], c["no_signal"]))


def _print_flagged_breakdown(snapshot):
    """Per-token deviation from the median priced token, for every
    flagged (WATCH) asset with a spread. Token deviations are sorted
    to aid inspection; that order is NOT a causal attribution of the
    IQR flag — the largest deviation explains the max-min extreme,
    not necessarily the central-dispersion trigger."""
    flagged = [row for row in snapshot["assets"]
               if row.get("decision") == "WATCH"
               and (row.get("spread") or {}).get("status") == "ok"]
    if not flagged:
        return
    print("flagged assets — per-token deviation from the median "
          "priced token (largest first; sorted to aid inspection, "
          "not a causal attribution of the IQR flag):")
    for row in flagged:
        spread = row["spread"]
        print("  %s (rwa_id %s) — robust %.3f%%, spread %.3f%%, codes: %s"
              % (row.get("symbol") or "-",
                 row.get("rwa_id"),
                 spread.get("robust_spread_pct") or 0.0,
                 spread.get("spread_pct") or 0.0,
                 ",".join(row["reason_codes"]) or "-"))
        toks = sorted(spread.get("tokens") or [],
                      key=lambda t: abs(t.get("dev_median_pct") or 0.0),
                      reverse=True)
        for tok in toks:
            dev_med = ("%.3f%%" % tok["dev_median_pct"]
                       if tok.get("dev_median_pct") is not None else "—")
            print("    %-7s %-19s %11s  %s"
                  % (tok.get("symbol") or "-",
                     (tok.get("issuer_name") or "-")[:19],
                     _fmt_price(tok.get("price")), dev_med))


def cmd_board(args, meter):
    now = datetime.now(timezone.utc)
    list_assets, ids = fetch_board_ids(meter, args.limit)
    if not ids:
        print("board: assets/list returned no stocks", file=sys.stderr)
        return 1
    quotes = fetch_quotes(meter, ids)
    by_id = {a.get("rwa_id"): a for a in quotes}
    order = _rank_order(list_assets)
    ordered = [by_id[i] for i in
               sorted(by_id, key=lambda rid: order.get(rid, 10 ** 9))]
    missing = [rid for rid in ids
               if int(rid) not in by_id] if ids else []
    snapshot = pipe.build_snapshot(ordered, context="board", now=now)
    path = write_snapshot(snapshot)
    print("RWA Radar — board (top-%d stocks by rwa_rank)" % args.limit)
    print("generated: %s" % _fmt_ts(now))
    print("snapshot: %s (%s)" % (snapshot["snapshot_id"], path.name))
    if missing:
        print("warning: quotes/latest did not return rwa_id(s): %s"
              % ", ".join(missing), file=sys.stderr)
    _print_board_table(snapshot)
    _print_flagged_breakdown(snapshot)
    print("credits this run: %d (%s)"
          % (meter.total,
             ", ".join("%s=%d" % kv for kv in meter.calls)))
    print(DISCLAIMER)
    return 0


# ---------------------------------------------------------------------------
# monitor
# ---------------------------------------------------------------------------

def _print_monitor_line(ts, row):
    print("%s  %-6s  avg %10s  spread %8s  robust %8s  %-9s  %s" % (
        ts.strftime("%H:%M:%S"),
        row.get("symbol") or "-",
        _fmt_price(row.get("average_tokenized_price")),
        _fmt_spread(row.get("spread")),
        _fmt_robust(row.get("spread")),
        row.get("decision"),
        ",".join(row["reason_codes"]) or "-"))


def refresh_watchlist(meter, extra_rid):
    """Re-fetch the ranked watchlist, preserving the explicitly
    requested ticker. A previous version rebuilt `ids` from the
    ranking on refresh and DROPPED the ticker from cycle 2 onward."""
    _, ids = fetch_board_ids(meter, cfg.WATCHLIST_SIZE)
    if extra_rid and extra_rid not in ids:
        ids.append(extra_rid)
    return ids


def cmd_monitor(args, meter):
    cadence = cfg.CADENCE[cfg.CREDIT_MODE]
    interval = args.interval if args.interval is not None \
        else cadence["quotes_seconds"]
    board_seconds = cadence["board_seconds"]
    hist_seconds = cadence["historical_seconds"]

    print("RWA Radar — monitor (credit mode %s, quotes every %ds, "
          "board refresh every %ds, historical every %ds)"
          % (cfg.CREDIT_MODE, interval, board_seconds, hist_seconds))
    print("started: %s" % _fmt_ts(datetime.now(timezone.utc)))
    print(DISCLAIMER)

    list_assets, ids = fetch_board_ids(meter, cfg.WATCHLIST_SIZE)
    extra_rid = None
    if args.ticker:
        env = _call(meter, "map symbol=%s" % args.ticker, ad.fetch_map,
                    symbol=args.ticker, asset_type="stock")
        asset = pipe.resolve_asset(env, args.ticker, asset_type="stock")
        if asset is None:
            print("monitor: ticker %s not found as a stock (map)"
                  % args.ticker, file=sys.stderr)
            return 1
        extra_rid = str(asset["rwa_id"])
        if extra_rid not in ids:
            ids.append(extra_rid)
    print("watchlist: %d assets (top-%d by rwa_rank%s)"
          % (len(ids), cfg.WATCHLIST_SIZE,
             " + %s" % args.ticker if args.ticker else ""))

    previous = None
    last_board = time.monotonic()
    last_hist = 0.0  # 0 => fetch historical on the first cycle
    hist_by_id = {}
    hist_disabled = False
    cycle = 0
    try:
        while args.cycles is None or cycle < args.cycles:
            cycle += 1
            now = datetime.now(timezone.utc)
            try:
                if cycle > 1 and \
                        time.monotonic() - last_board >= board_seconds:
                    ids = refresh_watchlist(meter, extra_rid)
                    last_board = time.monotonic()
                if not hist_disabled and \
                        time.monotonic() - last_hist >= hist_seconds:
                    try:
                        hist_by_id = fetch_historical_map(
                            meter, historical_ids(
                                ids, extra_rid,
                                cadence["historical_assets"]))
                        last_hist = time.monotonic()
                    except ad.CmcApiError as exc:
                        # 403 code 1014 (out-of-window) or any historical
                        # failure: degrade to quotes-only, do NOT repeat
                        # the same failing call this run (design §3.5).
                        print("cycle %d: historical skipped (%s)"
                              % (cycle, exc), file=sys.stderr)
                        hist_disabled = True
                        hist_by_id = {}
                quotes = fetch_quotes(meter, ids)
                returned = {a.get("rwa_id") for a in quotes}
                missing = [rid for rid in ids
                           if int(rid) not in returned]
                if missing:
                    # quotes/latest silently drops some ids (observed
                    # live: GOOG + one BRK.B duplicate of 20) — never
                    # hide that; the snapshot covers only what came back.
                    print("cycle %d: warning: quotes/latest did not "
                          "return rwa_id(s): %s"
                          % (cycle, ", ".join(missing)), file=sys.stderr)
                order = _rank_order(list_assets)
                ordered = sorted(
                    quotes,
                    key=lambda a: order.get(a.get("rwa_id"), 10 ** 9))
                snapshot = pipe.build_snapshot(
                    ordered, historical_by_id=hist_by_id,
                    context="monitor", now=now)
                previous = snapshot
                path = write_snapshot(snapshot)
                print("--- cycle %d @ %s  snapshot %s"
                      % (cycle, _fmt_ts(now), snapshot["snapshot_id"]))
                for row in snapshot["assets"]:
                    _print_monitor_line(now, row)
                print("    snapshot: %s  credits so far: %d"
                      % (path.name, meter.total))
            except ad.CmcError as exc:
                # Fail-closed: keep the last good snapshot, mark it stale
                # (design §3.5) — never invent data for this cycle.
                stale = pipe.apply_error(previous, exc)
                path = write_snapshot(stale)
                print("--- cycle %d @ %s  STALE: %s"
                      % (cycle, _fmt_ts(now), exc))
                print("    previous snapshot kept (%s); no data invented"
                      % path.name)
            if args.cycles is None or cycle < args.cycles:
                time.sleep(interval)
    except KeyboardInterrupt:
        print("\nmonitor stopped by user after %d cycle(s)" % cycle)
    print("monitor done: %d cycle(s), credits this run: %d (%s)"
          % (cycle, meter.total,
             ", ".join("%s=%d" % kv for kv in meter.calls)))
    return 0


# ---------------------------------------------------------------------------
# asset
# ---------------------------------------------------------------------------

def _ascii_spark(closes):
    """Tiny sparkline from daily-period first values (▁..█),
    oldest -> newest."""
    if not closes:
        return "—"
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(closes), max(closes)
    if hi == lo:
        return blocks[3] * len(closes)
    return "".join(blocks[min(7, int((v - lo) / (hi - lo) * 8))]
                    for v in closes)


def cmd_asset(args, meter):
    arg = args.asset
    if arg.isdigit():
        rwa_id = int(arg)
        symbol = None
    else:
        symbol = arg.upper()
        env = _call(meter, "map symbol=%s" % symbol, ad.fetch_map,
                    symbol=symbol, asset_type="stock")
        asset = pipe.resolve_asset(env, symbol, asset_type="stock")
        if asset is None:
            print("asset: symbol %s not found as a stock (or ambiguous "
                  "across asset types — pass an rwa_id)" % symbol,
                  file=sys.stderr)
            return 1
        rwa_id = asset["rwa_id"]

    info_env = _call(meter, "info rwa_id=%d" % rwa_id,
                     ad.fetch_info, rwa_id=rwa_id)
    info_assets = pipe.assets_from_envelope(info_env)
    info = info_assets[0] if info_assets else {}
    quotes = fetch_quotes(meter, [str(rwa_id)],
                          label="quotes/latest rwa_id=%d" % rwa_id)
    if not quotes:
        print("asset: quotes/latest returned nothing for rwa_id %d"
              % rwa_id, file=sys.stderr)
        return 1
    quote = quotes[0]
    hist_by_id = {}
    hist_note = None
    try:
        hist_by_id = fetch_historical_map(
            meter, [str(rwa_id)],
            label="quotes/historical rwa_id=%d" % rwa_id)
    except ad.CmcApiError as exc:
        # Out-of-window (403 code 1014) or other historical failure:
        # show the quote without % change (design §3.5).
        hist_note = "historical unavailable: %s" % exc
    snapshot = pipe.build_snapshot([quote], historical_by_id=hist_by_id,
                                   context="asset")
    row = snapshot["assets"][0]
    path = write_snapshot(snapshot)

    print("RWA Radar — asset detail")
    print("generated: %s"
          % _fmt_ts(datetime.now(timezone.utc)))
    print("%s · %s · rwa_id %d (rank #%s) — %s"
          % (row.get("name"), row.get("symbol"), row.get("rwa_id"),
             row.get("rwa_rank") if row.get("rwa_rank") is not None
             else "-", row.get("decision")))
    print("snapshot: %s (%s)" % (snapshot["snapshot_id"], path.name))
    # Company fields from info (only those present are printed).
    company = []
    for key, label in (("industry", "industry"),
                       ("primary_exchange", "exchange"),
                       ("employees", "employees"),
                       ("founded", "founded"),
                       ("cik", "CIK"),
                       ("website", "website")):
        if info.get(key) is not None:
            company.append("%s: %s" % (label, info[key]))
    if company:
        print("company: %s" % "; ".join(company))
    if info.get("description"):
        print("about: %s" % str(info["description"])[:300])
    print("avg tokenised price: %s USD  ·  tokenised mcap: %s  ·  "
          "24h volume: %s"
          % (_fmt_price(row.get("average_tokenized_price")),
             _fmt_price(row.get("tokenized_market_cap")),
             _fmt_price(row.get("tokenized_volume_24h"))))
    print("last updated: %s" % (row.get("last_updated") or "—"))
    spread = row.get("spread") or {}
    if spread.get("status") in ("ok", "single_issuer"):
        print("issuer spread: %.3f%% (abs %.6f; %d priced tokens from "
              "%d distinct issuers, %d null; denominator: %s)"
              % (spread["spread_pct"], spread["spread_abs"],
                 spread["priced_count"], spread.get("issuer_count", 0),
                 spread["null_count"],
                 spread.get("spread_denominator")))
        print("robust spread (IQR/median, decision metric): %.3f%% "
              "(flag threshold: robust spread > %.1f%%; "
              "exploratory heuristic, not a validated threshold)"
              % (spread["robust_spread_pct"],
                 cfg.ROBUST_SPREAD_FLAG_PCT))
        print("quartiles of priced tokens: Q1 %.2f · median %.2f · "
              "Q3 %.2f USD"
              % (spread.get("q1_price") or 0.0,
                 spread.get("median_price") or 0.0,
                 spread.get("q3_price") or 0.0))
        if spread.get("status") == "single_issuer":
            print("note: all priced tokens are from ONE issuer "
                  "(single_issuer) — this is not a cross-issuer "
                  "comparison; decision NO_SIGNAL.")
        print("token   issuer              price       dev vs median  dev vs avg")
        for tok in spread["tokens"]:
            dev_med = ("%.3f%%" % tok["dev_median_pct"]
                       if tok.get("dev_median_pct") is not None else "—")
            dev = ("%.3f%%" % tok["dev_pct"]
                   if tok.get("dev_pct") is not None else "—")
            print("%-7s %-19s %11s  %13s  %s"
                  % (tok.get("symbol") or "-",
                     (tok.get("issuer_name") or "-")[:19],
                     _fmt_price(tok.get("price")), dev_med, dev))
        if spread["null_count"]:
            nulls = [t.get("symbol") for t in quote.get("tokens") or []
                     if not isinstance(t.get("price"), (int, float))]
            print("null-priced tokens (excluded from spread): %s"
                  % ", ".join(nulls))
    else:
        print("issuer spread: unavailable (%s)"
              % spread.get("status", "no data"))
    changes = row.get("changes")
    if changes is not None:
        print("daily-period observations (%d points; each is the FIRST "
              "value in its period, bars start at midnight New York):"
              % changes["n_points"])
        print("  spark: %s" % _ascii_spark(changes["spark"]))
        print("  values: %s"
              % ", ".join("%.2f" % v for v in changes["spark"]))
        if changes.get("chg_prev") is not None:
            print("  change vs previous daily-period observation "
                  "(%s to %s): %+.2f%%"
                  % (changes.get("chg_prev_from"),
                     changes.get("chg_prev_to"), changes["chg_prev"]))
        if changes.get("chg_8back") is not None:
            print("  change vs observation 7 periods back "
                  "(%s to %s): %+.2f%%"
                  % (changes.get("chg_8back_from"),
                     changes.get("chg_8back_to"), changes["chg_8back"]))
        if changes.get("history_short"):
            print("  history too short for %% change (history_short)")
    if hist_note:
        print(hist_note)
    if row.get("reason_codes"):
        print("reason codes: %s" % ", ".join(row["reason_codes"]))
    print(pipe.explain(row))
    print("credits this run: %d (%s)"
          % (meter.total,
             ", ".join("%s=%d" % kv for kv in meter.calls)))
    print(DISCLAIMER)
    return 0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="cmc_run.py",
        description="RWA Radar — CoinMarketCap RWA screener & "
                    "issuer-spread monitor (read-only; not investment "
                    "advice).")
    sub = parser.add_subparsers(dest="mode")
    p_board = sub.add_parser(
        "board", help="top-N stocks board (default mode)")
    p_board.add_argument("--limit", type=int, default=25,
                         help="board size (default 25)")
    p_mon = sub.add_parser(
        "monitor", help="poll the watchlist periodically")
    p_mon.add_argument("--cycles", type=int, default=None,
                       help="number of cycles, then stop "
                            "(default: run until interrupted)")
    p_mon.add_argument("--interval", type=int, default=None,
                       help="seconds between cycles (default: cadence "
                            "for the active credit mode)")
    p_mon.add_argument("--ticker", default=None,
                       help="extra stock ticker to add to the watchlist")
    p_asset = sub.add_parser(
        "asset", help="detail for one asset")
    p_asset.add_argument("asset",
                         help="rwa_id (number) or stock symbol, e.g. NVDA")
    # Defaults for a bare `cmc_run.py` run (no subcommand -> board):
    # subparser defaults are NOT applied when no subcommand is given,
    # so the board limit must also be defaulted here.
    parser.set_defaults(mode="board", limit=25)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    meter = CreditMeter()
    try:
        if args.mode == "board":
            return cmd_board(args, meter)
        if args.mode == "monitor":
            return cmd_monitor(args, meter)
        if args.mode == "asset":
            return cmd_asset(args, meter)
    except ad.CmcKeyError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    except ad.CmcApiError as exc:
        print("error: %s" % exc, file=sys.stderr)
        print("fail-closed: no snapshot was written or invented",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
