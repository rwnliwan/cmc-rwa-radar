"""RWA Radar — capture raw CMC API responses as evidence.

Milestone 29–30 Nov (DESIGN-CMC-RWA.md §4.1, §5.3 item 4 / §6).

Saves the RAW JSON envelopes of the backbone endpoints to
evidence/cmc/<name>.json and writes evidence/cmc/manifest.json with
a SHA-256 hash, byte size, endpoint, credit count and capture time per
file — proof of real API calls for the judges.

This script NEVER prints, logs, or writes the API key: all calls go
through cmc_adapter, which reads .env.local at runtime. The captured
envelopes contain only public market data (no key, no account data).

Calls made (5 credits total):
  map NVDA                      0 credits
  assets/list stock limit=5     1 credit
  quotes/latest rwa_id=2        1 credit
  quotes/historical rwa_id=2    1 credit (daily x30)
  info rwa_id=2                 1 credit
  issuers/list limit=10         1 credit

Usage:  python3 capture_cmc_evidence.py [--out evidence/cmc]
Re-runnable: overwrites the files and regenerates the manifest.
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

import cmc_adapter as ad

CALLS = [
    ("map-nvda.json",
     "GET /v5/real-world-assets/map?symbol=NVDA&asset_type=stock",
     lambda: ad.fetch_map(symbol="NVDA", asset_type="stock")),
    ("list-stock-limit5.json",
     "GET /v5/real-world-assets/assets/list?asset_type=stock&sort=rwa_rank&limit=5",
     lambda: ad.fetch_list(asset_type="stock", sort="rwa_rank", limit=5)),
    ("quotes-latest-nvda.json",
     "GET /v5/real-world-assets/quotes/latest?rwa_id=2",
     lambda: ad.fetch_quotes_latest(rwa_id=2)),
    ("quotes-historical-nvda-daily30.json",
     "GET /v5/real-world-assets/quotes/historical?rwa_id=2&interval=daily&count=30",
     lambda: ad.fetch_historical(rwa_id=2, interval="daily", count=30)),
    ("info-nvda.json",
     "GET /v5/real-world-assets/info?rwa_id=2",
     lambda: ad.fetch_info(rwa_id=2)),
    ("issuers-list.json",
     "GET /v5/real-world-assets/issuers/list?limit=10",
     lambda: ad.fetch_issuers_list(limit=10)),
]


def _sha256(blob):
    return hashlib.sha256(blob).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(REPO / "evidence" / "cmc"),
                        help="evidence directory (default: evidence/cmc)")
    args = parser.parse_args(argv)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    captured_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {"captured_at_utc": captured_at, "files": {},
                "total_credits": 0}
    for name, endpoint, call in CALLS:
        env = call()
        credits = int((env.get("status") or {}).get("credit_count") or 0)
        text = json.dumps(env, indent=2, sort_keys=True,
                          ensure_ascii=False)
        blob = text.encode("utf-8")
        (out_dir / name).write_bytes(blob)
        manifest["files"][name] = {
            "endpoint": endpoint,
            "bytes": len(blob),
            "sha256": _sha256(blob),
            "credit_count": credits,
            "captured_at_utc": captured_at,
        }
        manifest["total_credits"] += credits
        print("captured %s (%d bytes, sha256 %s…, %d credit(s))"
              % (name, len(blob),
                 manifest["files"][name]["sha256"][:12], credits))
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8")
    print("manifest: %s (total credits this run: %d)"
          % (out_dir / "manifest.json", manifest["total_credits"]))
    print("evidence is public market data only — no API key in any file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
