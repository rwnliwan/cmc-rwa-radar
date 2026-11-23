"""Regression tests for the 23 Nov 2026 re-gate must-fix #1 (Instinct
86/100, HOLD): read timeout + valid-JSON wrong-shape must not escape
the adapter as a raw TimeoutError / AttributeError, and the monitor
must keep the previous snapshot, mark it stale, and keep cycling.

Stdlib only. Run from the repo root:

    python3 -m unittest test_cmc_failclosed -v
    # or
    python3 test_cmc_failclosed.py

(a) Real local HTTP server answers headers then stalls the body past
    the client timeout -> adapter raises CmcApiError (not TimeoutError),
    after the one allowed retry.
(b) 200 with valid JSON but status null / status list / data list /
    rwa_assets dict -> CmcApiError. A well-shaped envelope still
    returns normally.
(c) Monitor end-to-end (adapter faked at the fetch boundary): cycle 1
    writes a good snapshot -> cycle 2 quotes raises CmcApiError ->
    previous data kept, stale snapshot written, no crash -> cycle 3
    recovers fresh.
(d) Historical-only failure -> quotes keep running, degradation is
    recorded, the failing historical call is not repeated this run.
"""

import argparse
import copy
import io
import json
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cmc_adapter as ad
import cmc_config as cfg
import cmc_run as run

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "cmc"


def _ok_envelope(assets):
    return {"data": {"rwa_assets": assets},
            "status": {"error_code": "0", "credit_count": 1,
                       "error_message": "",
                       "timestamp": "2026-11-23T04:47:01.203Z"}}


def _fresh_ts():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _quote_assets():
    """NVDA from the stored fixture + one synthetic AAPL row, both
    with fresh last_updated so the monitor does not flag stale_quote."""
    env = json.loads((FIXTURES / "quotes-latest-nvda.json").read_text())
    nvda = copy.deepcopy(env["data"]["rwa_assets"][0])
    nvda["last_updated"] = _fresh_ts()
    aapl = {
        "rwa_id": 3, "symbol": "AAPL", "name": "Apple Inc",
        "asset_type": "stock", "rwa_rank": 6, "has_tokens": True,
        "average_tokenized_price": 250.0,
        "tokenized_market_cap": 3000000000000.0,
        "tokenized_volume_24h": 1000000.0,
        "last_updated": _fresh_ts(),
        "tokens": [
            {"symbol": "AAPLX", "issuer_name": "Backed Assets",
             "issuer_id": "issuer-backed", "crypto_id": 1,
             "price": 249.5},
            {"symbol": "wAAPLX", "issuer_name": "Ondo",
             "issuer_id": "issuer-ondo", "crypto_id": 2,
             "price": 250.5},
        ],
    }
    return [nvda, aapl]


def _list_rows():
    return [
        {"rwa_id": 2, "symbol": "NVDA", "name": "NVIDIA Corporation",
         "asset_type": "stock", "rwa_rank": 5},
        {"rwa_id": 3, "symbol": "AAPL", "name": "Apple Inc",
         "asset_type": "stock", "rwa_rank": 6},
    ]


class _Fake200:
    """Minimal urlopen() stand-in returning a fixed body."""

    def __init__(self, body):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._body


# ---------------------------------------------------------------------------
# (a) Real stalling server
# ---------------------------------------------------------------------------

class _StallHandler(BaseHTTPRequestHandler):
    """Answers 200 + headers, then holds the body forever (3 s here —
    far past the patched 0.5 s client timeout)."""
    requests = 0

    def do_GET(self):
        type(self).requests += 1
        body = (b'{"data": {"rwa_assets": []}, "status": '
                b'{"error_code": "0", "credit_count": 0}}')
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        time.sleep(3)  # hold the body; the client times out first

    def log_message(self, *a):
        pass


class AdapterTimeoutTests(unittest.TestCase):
    def test_stalled_body_raises_cmc_api_error_not_timeout_error(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), _StallHandler)
        server.daemon_threads = True
        _StallHandler.requests = 0
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            with mock.patch.object(cfg, "BASE_URL",
                                   "http://127.0.0.1:%d" % port), \
                 mock.patch.object(cfg, "REQUEST_TIMEOUT_SECONDS", 0.5), \
                 mock.patch.object(cfg, "RETRY_BACKOFF_SECONDS", 0):
                with self.assertRaises(ad.CmcApiError) as ctx:
                    ad.fetch_map(symbol="NVDA", asset_type="stock")
                # The point of the fix: this used to escape as a raw
                # TimeoutError, which the monitor does not catch.
                self.assertNotIsInstance(ctx.exception, TimeoutError)
                self.assertIsInstance(ctx.exception, ad.CmcError)
            # One retry, as for URLError / 429 / 5xx.
            self.assertEqual(_StallHandler.requests, 2)
        finally:
            server.shutdown()
            server.server_close()

    def test_mocked_timeout_and_reset_are_normalised(self):
        # Fast unit-level cover for the same except clause (connect /
        # read phase, TimeoutError and ConnectionError alike).
        for exc in (TimeoutError("timed out"),
                    ConnectionResetError("connection reset by peer")):
            with mock.patch.object(ad.urllib.request, "urlopen",
                                   side_effect=exc), \
                 mock.patch.object(ad.time, "sleep", lambda s: None):
                with self.assertRaises(ad.CmcApiError):
                    ad._get_json("/v5/real-world-assets/map", {})

    def test_programming_bug_is_not_swallowed(self):
        # The fix must NOT be a bare `except Exception`: a TypeError
        # from inside the adapter still propagates as itself.
        with mock.patch.object(ad.urllib.request, "urlopen",
                               side_effect=TypeError("boom")):
            with self.assertRaises(TypeError):
                ad._get_json("/v5/real-world-assets/map", {})


# ---------------------------------------------------------------------------
# (b) Valid JSON, wrong envelope shape
# ---------------------------------------------------------------------------

class EnvelopeShapeTests(unittest.TestCase):
    def _call(self, payload):
        body = json.dumps(payload).encode("utf-8")
        with mock.patch.object(ad.urllib.request, "urlopen",
                               return_value=_Fake200(body)):
            return ad._get_json("/v5/real-world-assets/map", {})

    def test_status_null_raises(self):
        with self.assertRaises(ad.CmcApiError):
            self._call({"status": None,
                        "data": {"rwa_assets": []}})

    def test_status_list_raises(self):
        with self.assertRaises(ad.CmcApiError):
            self._call({"status": ["0"],
                        "data": {"rwa_assets": []}})

    def test_data_list_raises(self):
        with self.assertRaises(ad.CmcApiError):
            self._call({"status": {"error_code": "0"}, "data": []})

    def test_rwa_assets_dict_raises(self):
        with self.assertRaises(ad.CmcApiError):
            self._call({"status": {"error_code": "0"},
                        "data": {"rwa_assets": {"2": {}}}})

    def test_well_shaped_envelope_passes(self):
        out = self._call({"status": {"error_code": "0",
                                     "credit_count": 1},
                          "data": {"rwa_assets": []}})
        self.assertEqual(out["data"]["rwa_assets"], [])

    def test_missing_data_and_rwa_assets_still_legal(self):
        # Absent keys read as "no assets" downstream; only wrong
        # TYPES are rejected.
        out = self._call({"status": {"error_code": "0"}})
        self.assertEqual(out["status"]["error_code"], "0")


# ---------------------------------------------------------------------------
# (c) + (d) Monitor end-to-end, adapter faked at the fetch boundary
# ---------------------------------------------------------------------------

class MonitorFailClosedTests(unittest.TestCase):
    def _run_monitor(self, quotes_impl, hist_impl, cycles):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        outdir = Path(tmp.name)
        calls = {"list": 0, "quotes": 0, "hist": 0}

        def fake_list(**kw):
            calls["list"] += 1
            return copy.deepcopy(_ok_envelope(_list_rows()))

        def fake_quotes(**kw):
            calls["quotes"] += 1
            return quotes_impl(calls["quotes"])

        def fake_hist(**kw):
            calls["hist"] += 1
            return hist_impl(calls["hist"])

        written = []
        orig_write = run.write_snapshot

        def spy_write(snapshot):
            written.append(copy.deepcopy(snapshot))
            return orig_write(snapshot)

        out = io.StringIO()
        err = io.StringIO()
        with mock.patch.object(ad, "fetch_list", fake_list), \
             mock.patch.object(ad, "fetch_quotes_latest", fake_quotes), \
             mock.patch.object(ad, "fetch_historical", fake_hist), \
             mock.patch.object(run, "write_snapshot", spy_write), \
             mock.patch.object(run, "OUT_DIR", outdir), \
             redirect_stdout(out), redirect_stderr(err):
            args = argparse.Namespace(cycles=cycles, interval=0,
                                      ticker=None)
            rc = run.cmd_monitor(args, run.CreditMeter())
        return rc, written, calls, out.getvalue(), err.getvalue()

    def test_error_cycle_keeps_previous_marks_stale_recovers(self):
        quotes_env = _ok_envelope(_quote_assets())

        def fake_quotes(n):
            if n == 2:
                raise ad.CmcApiError(
                    "CMC request to /v5/real-world-assets/quotes/latest "
                    "timed out or dropped: timed out")
            return copy.deepcopy(quotes_env)

        def fake_hist(n):
            return copy.deepcopy(_ok_envelope([]))

        rc, written, calls, stdout, _ = self._run_monitor(
            fake_quotes, fake_hist, cycles=3)
        self.assertEqual(rc, 0, stdout)
        self.assertEqual(len(written), 3)
        # Cycle 1: fresh snapshot, 2 assets.
        self.assertNotEqual(written[0].get("status"), "stale")
        self.assertEqual(len(written[0]["assets"]), 2)
        # Cycle 2: monitor did NOT terminate; previous data kept,
        # same snapshot_id, status stale, reason recorded.
        self.assertEqual(written[1].get("status"), "stale")
        self.assertEqual(written[1].get("snapshot_id"),
                         written[0].get("snapshot_id"))
        self.assertEqual(written[1].get("assets"),
                         written[0].get("assets"))
        self.assertIn("timed out", written[1].get("stale_reason", ""))
        self.assertIn("STALE", stdout)
        # Cycle 3: recovered — fresh snapshot, same coverage. NOTE:
        # snapshot_id is a content hash with second-resolution
        # generated_at, so a recovery inside the same second as cycle
        # 1 legitimately reuses cycle 1's id (identical content);
        # freshness is shown by the ABSENCE of the stale status.
        self.assertNotEqual(written[2].get("status"), "stale")
        self.assertEqual(written[2]["assets"], written[0]["assets"])
        self.assertEqual(calls["quotes"], 3)

    def test_historical_only_failure_degrades_to_quotes_only(self):
        quotes_env = _ok_envelope(_quote_assets())

        def fake_quotes(n):
            return copy.deepcopy(quotes_env)

        def fake_hist(n):
            raise ad.CmcApiError(
                "CMC error 1014 on /v5/real-world-assets/quotes/"
                "historical: out of window", error_code="1014")

        rc, written, calls, stdout, stderr = self._run_monitor(
            fake_quotes, fake_hist, cycles=2)
        self.assertEqual(rc, 0, stdout)
        self.assertEqual(len(written), 2)
        # Historical was attempted once, then disabled for the run —
        # the same failing call is not repeated.
        self.assertEqual(calls["hist"], 1)
        # Quotes kept running both cycles.
        self.assertEqual(calls["quotes"], 2)
        self.assertIn("historical skipped", stderr)
        # Snapshots still written, quotes data present, no % change
        # (no history) — degradation, not invented data.
        for snap in written:
            self.assertNotEqual(snap.get("status"), "stale")
            self.assertEqual(len(snap["assets"]), 2)
            for row in snap["assets"]:
                self.assertIsNone(row.get("changes"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
