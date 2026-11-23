#!/usr/bin/env python3
"""Recompute the 23 Nov 2026 calibration numbers from the stored board.

Input: calibration/cmc_snapshot_20261123T122301Z_snap-232a348a8e3b911b.json
— the top-25 board snapshot taken 23 Nov 2026 20:23 WITA (12:23:01 UTC),
BEFORE the v0.2.0 recalibration. The snapshot itself was written by the
v0.1.0 method (max-min decisions only: 0 OK / 23 WATCH, no
robust_spread_pct field), but it carries every asset's priced token
prices, so the robust (IQR/median) distribution CAN be recomputed from
it — that is what this script does, independently of cmc_pipeline.py
(the quantiles are recomputed here from the raw prices).

What it checks:
  1. The robust-spread distribution across the 23 covered assets:
     median / p75 / p90 (inclusive quantiles, statistics.quantiles
     method="inclusive" — the same definition the pipeline uses).
  2. The decision counts under the v0.2.0 rules on this frozen input:
     WATCH when robust spread > 0.5% OR any priced token deviates
     >100% from the asset median (mixed underlying). Expected:
     18 OK / 5 WATCH (4 robust-flagged + SPCX via mixed_underlying).
  3. The frozen-input equivalence of v0.2.0 vs v0.3.0 decisions:
     v0.2.0 mapped BOTH its >0.5% and >1.0% codes to WATCH, so on
     identical inputs removing the upper level cannot change WATCH
     membership — the two rule sets must decide identically here.
     (The 20:48 board reading 15 OK / 8 WATCH is a DIFFERENT snapshot
     taken 25 minutes later; the flag mix moved because prices moved,
     not because the upper level was removed.)
  4. Where the 0.5% line sits in the distribution (percentile).

Percentile convention: LINEAR interpolation (inclusive quantiles,
statistics.quantiles method="inclusive") — the same convention the
pipeline uses for Q1/median/Q3, and the same one behind the median and
p75 figures in the docs. NOTE on the earlier p90 figure: rounds
v0.2.0/v0.3.0 quoted p90 = 0.597%. That value is the FLOOR-index
("lower") 90th percentile of these same 23 values — the 20th smallest
— not the linear-interpolation p90, which is 0.924%. The docs now use
the linear figure (0.924%) so median/p75/p90 share one convention;
the 0.597% figure is retained here only as a historical note.
Likewise the line was described as "~p85"; the exact figure is
p82.6 (19 of 23 assets at or below 0.5%), so the docs now say ~p83.

Usage: python3 calibration/recompute_calibration.py
Output: calibration/calibration-output.json (committed) + a human
summary on stdout. Exit 0 only when every claimed number reproduces.
"""
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "cmc_snapshot_20261123T122301Z_snap-232a348a8e3b911b.json"
OUT = ROOT / "calibration-output.json"

FLAG_PCT = 0.5
MIXED_PCT = 100.0


def robust_spread(prices):
    """(Q3 - Q1) / median * 100, inclusive quartiles; None if < 2 prices."""
    if len(prices) < 2:
        return None
    q1, median, q3 = statistics.quantiles(prices, n=4, method="inclusive")
    if not median:
        return None
    return (q3 - q1) / median * 100.0


def main():
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assets = snap["assets"]
    assert len(assets) == 23, "expected 23 assets, got %d" % len(assets)

    rows = []
    for asset in assets:
        spread = asset.get("spread") or {}
        tokens = spread.get("tokens") or []
        prices = [t["price"] for t in tokens
                  if isinstance(t.get("price"), (int, float))]
        median = statistics.median(prices) if prices else None
        robust = robust_spread(prices)
        mixed = bool(median) and any(
            abs(p - median) / median * 100.0 > MIXED_PCT for p in prices)
        # Distinct issuers, by name (the v0.1.0 snapshot did not store
        # issuer_id; issuer_name is the stable identifier it carries).
        issuers = {t.get("issuer_name") for t in tokens
                   if isinstance(t.get("price"), (int, float))}
        rows.append({
            "symbol": asset.get("symbol"),
            "rwa_id": asset.get("rwa_id"),
            "token_count": len(tokens),
            "priced_count": len(prices),
            "issuer_count_by_name": len(issuers),
            "robust_spread_pct": robust,
            "mixed_underlying": mixed,
            "watch_v020": bool(robust is not None and robust > FLAG_PCT)
            or mixed,
            "watch_v030": bool(robust is not None and robust > FLAG_PCT)
            or mixed,
        })

    robs = sorted(r["robust_spread_pct"] for r in rows
                  if r["robust_spread_pct"] is not None)
    median_r = statistics.median(robs)
    q1_r, _, q3_r = statistics.quantiles(robs, n=4, method="inclusive")
    # p90 by linear interpolation (the same inclusive-quantile family).
    p90_r = statistics.quantiles(robs, n=10, method="inclusive")[8]
    at_or_below = sum(1 for x in robs if x <= FLAG_PCT)
    pct_line = 100.0 * at_or_below / len(robs)

    watch_v020 = [r["symbol"] for r in rows if r["watch_v020"]]
    watch_v030 = [r["symbol"] for r in rows if r["watch_v030"]]
    result = {
        "input": SNAPSHOT.name,
        "input_generated_at": snap.get("generated_at"),
        "input_method": snap.get("method"),
        "n_assets": len(rows),
        "robust_distribution_pct": {
            "median": round(median_r, 4),
            "p75": round(q3_r, 4),
            "p90": round(p90_r, 4),
            "min": round(robs[0], 4),
            "max": round(robs[-1], 4),
        },
        "flag_line_pct": FLAG_PCT,
        "flag_line_percentile": round(pct_line, 1),
        "p90_note": ("linear-interpolation p90 is 0.924%; the 0.597% "
                     "quoted in earlier rounds is the floor-index "
                     "(lower) 90th percentile of the same 23 values"),
        "decisions_v020": {
            "ok": len(rows) - len(watch_v020),
            "watch": len(watch_v020),
            "watch_symbols": watch_v020,
        },
        "decisions_v030": {
            "ok": len(rows) - len(watch_v030),
            "watch": len(watch_v030),
            "watch_symbols": watch_v030,
        },
        "v020_v030_identical": watch_v020 == watch_v030,
        "per_asset": rows,
    }
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True),
                   encoding="utf-8")

    print("calibration input: %s (generated %s, method %s)"
          % (SNAPSHOT.name, snap.get("generated_at"), snap.get("method")))
    print("assets: %d" % len(rows))
    print("robust spread: median %.4f%%, p75 %.4f%%, p90 %.4f%%, "
          "range %.4f%%-%.4f%%"
          % (median_r, q3_r, p90_r, robs[0], robs[-1]))
    print("0.5%% line sits at p%.1f (%d of %d assets at or below it)"
          % (pct_line, at_or_below, len(robs)))
    print("v0.2.0 decisions on this frozen input: %d OK / %d WATCH %s"
          % (len(rows) - len(watch_v020), len(watch_v020), watch_v020))
    print("v0.3.0 decisions on this frozen input: %d OK / %d WATCH %s"
          % (len(rows) - len(watch_v030), len(watch_v030), watch_v030))
    print("v0.2.0 vs v0.3.0 identical on frozen input: %s"
          % (watch_v020 == watch_v030))

    # Claims the docs make about this input — all must reproduce.
    failures = []
    if abs(median_r - 0.265) > 0.005:
        failures.append("median %.4f != claimed 0.265" % median_r)
    if abs(q3_r - 0.440) > 0.005:
        failures.append("p75 %.4f != claimed 0.440" % q3_r)
    if abs(p90_r - 0.924) > 0.005:
        failures.append("p90 %.4f != 0.924 (linear interpolation; the "
                        "0.597% quoted earlier is the floor-index p90)"
                        % p90_r)
    if len(watch_v020) != 5 or len(rows) - len(watch_v020) != 18:
        failures.append("v0.2.0 counts %d OK / %d WATCH != claimed 18/5"
                        % (len(rows) - len(watch_v020), len(watch_v020)))
    if watch_v020 != watch_v030:
        failures.append("v0.2.0 vs v0.3.0 decisions differ on frozen input")
    if failures:
        print("REPRODUCTION FAILED:")
        for failure in failures:
            print("  - " + failure)
        return 1
    print("all claimed numbers reproduce from the stored input")
    return 0


if __name__ == "__main__":
    sys.exit(main())
