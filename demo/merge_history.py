#!/usr/bin/env python3
"""RWA Radar — merge historical data into a board snapshot (demo only).

Problem (final-gate review, group 6): the dashboard detail capture
(shot 3a) used the BOARD snapshot, and board snapshots carry no
historical data — so the detail pane said "Sparkline not available"
while the video's title card advertised "sparkline 30 daily closes".

Fix: after the demo run fetches the board AND the asset detail for
NVDA (two live fetches of the same asset, minutes apart), this script
attaches the asset run's `changes` (sparkline + % change between the
available daily-period observations) to the NVDA row of the board
snapshot, and writes the merged snapshot back as out/cmc_snapshot.json
(with a recomputed snapshot_id). The board row keeps the BOARD run's
spread/decision — only the historical part comes from the asset run —
and both halves are live data of the same asset, fetched minutes
apart; nothing is invented. If the asset snapshot has no historical
data, the script exits 1 instead of silently producing another
"Sparkline not available" capture.

Usage:
  python3 demo/merge_history.py <board-snapshot.json> <asset-snapshot.json>
      [--symbol NVDA] [--out out/cmc_snapshot.json]

Both inputs are snapshot files written by cmc_run.py (board / asset).
The output is written via cmc_run.write_snapshot (canonical JSON +
archive copy). Exit 0 on success, 1 on any mismatch.
"""
import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cmc_pipeline as pl
import cmc_run as run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("board_snapshot", help="board snapshot JSON")
    parser.add_argument("asset_snapshot", help="asset snapshot JSON")
    parser.add_argument("--symbol", default="NVDA",
                        help="symbol whose history is merged (default NVDA)")
    parser.add_argument("--out", default=None,
                        help="output path (default: out/cmc_snapshot.json)")
    args = parser.parse_args(argv)

    board = json.loads(Path(args.board_snapshot).read_text())
    asset = json.loads(Path(args.asset_snapshot).read_text())

    board_rows = board.get("assets") or []
    asset_rows = asset.get("assets") or []
    if len(asset_rows) != 1:
        print("error: asset snapshot must hold exactly 1 asset, got %d"
              % len(asset_rows), file=sys.stderr)
        return 1
    src = asset_rows[0]
    if (src.get("symbol") or "").upper() != args.symbol.upper():
        print("error: asset snapshot is %s, expected %s"
              % (src.get("symbol"), args.symbol), file=sys.stderr)
        return 1
    changes = src.get("changes")
    if not changes or not (changes.get("spark") or []):
        print("error: asset snapshot for %s has no historical data "
              "(changes missing/empty) — refusing to merge"
              % args.symbol, file=sys.stderr)
        return 1

    target = None
    for row in board_rows:
        if (row.get("symbol") or "").upper() == args.symbol.upper():
            target = row
            break
    if target is None:
        print("error: %s not on the board snapshot"
              % args.symbol, file=sys.stderr)
        return 1
    if target.get("rwa_id") != src.get("rwa_id"):
        print("error: rwa_id mismatch (board %s vs asset %s)"
              % (target.get("rwa_id"), src.get("rwa_id")), file=sys.stderr)
        return 1

    merged = copy.deepcopy(board)
    for row in merged["assets"]:
        if row.get("rwa_id") == target["rwa_id"]:
            row["changes"] = copy.deepcopy(changes)
    # The body changed: recompute the canonical snapshot_id.
    merged.pop("snapshot_id", None)
    merged["snapshot_id"] = pl._canonical_id(merged)

    out = Path(args.out) if args.out else ROOT / "out" / "cmc_snapshot.json"
    # write_snapshot writes to out/cmc_snapshot.json (+ archive); use
    # it when the target is the default, otherwise write directly.
    if out == ROOT / "out" / "cmc_snapshot.json":
        archive = run.write_snapshot(merged)
        print("merged %s history (%d daily-period observations, "
              "%s to %s) into the board snapshot -> %s (archive %s)"
              % (args.symbol, changes["n_points"],
                 (changes.get("obs_dates") or ["?"])[0],
                 (changes.get("obs_dates") or ["?"])[-1],
                 out, archive))
    else:
        out.write_text(json.dumps(
            pl.public_snapshot(merged), indent=2, sort_keys=True,
            ensure_ascii=False), encoding="utf-8")
        print("merged %s history into %s" % (args.symbol, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
