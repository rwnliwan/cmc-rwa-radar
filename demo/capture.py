"""RWA Radar — demo capture (Playwright headless Chromium).

Milestone 28 Nov (DESIGN-CMC-RWA.md §5.1, §6). Takes one screenshot per
demo shot + records raw video of the dashboard interaction
(`record_video_dir` -> demo/shots/video/ — raw video v1, unedited).

This script NEVER reads .env.local and NEVER calls the CMC API. It only
renders text files the demo run already captured (terminal output,
manifest) and screenshots the local dashboard at http://127.0.0.1:8000/
(which itself only serves files already on disk).

Usage:
  python3 demo/capture.py --phase terminal
      shot-1 (asset NVDA terminal), shot-2 (board terminal),
      shot-4 (MANIFEST.json).
  python3 demo/capture.py --phase dashboard --select NVDA
      shot-3-dashboard-board.png + shot-3-detail-nvda.png
      (video recording on).
  python3 demo/capture.py --phase dashboard --select FGI
      shot-3b-detail-nosignal.png (board has 1 row after `asset 4379`).
  python3 demo/capture.py --phase closing
      shot-5-closing.png (full-page dashboard incl. footer).
"""

import argparse
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "demo" / "shots"
VIDEO_DIR = SHOTS / "video"
BASE_URL = "http://127.0.0.1:8000/"

VIEWPORT = {"width": 1280, "height": 800}


def _terminal_page(title, text):
    """Minimal dark terminal-style page rendering pre-captured text."""
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>body{margin:0;background:#1e1e1e;color:#e8e8e8;"
        "font-family:ui-monospace,Menlo,Consolas,monospace;"
        "font-size:15px;line-height:1.55;padding:28px 32px;}"
        "h1{font-size:15px;color:#8ab4f8;margin:0 0 14px;}"
        "pre{margin:0;white-space:pre-wrap;word-wrap:break-word;}"
        "</style></head><body><h1>%s</h1><pre>%s</pre></body></html>"
        % (html.escape(title), html.escape(text))
    )


def _shot(page, path, full_page=False):
    page.screenshot(path=str(path), full_page=full_page)
    if not path.is_file() or path.stat().st_size < 5000:
        raise RuntimeError("screenshot looks empty: %s" % path)
    print("shot: %s (%d bytes)" % (path.name, path.stat().st_size))


def phase_terminal(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport=VIEWPORT)
    jobs = [
        ("terminal-asset-nvda.txt",
         "RWA Radar — asset NVDA (live CLI output)",
         "shot-1-problem-nvda-tokens.png"),
        ("terminal-board.txt",
         "RWA Radar — board top-10 (live CLI output)",
         "shot-2-cli-board.png"),
    ]
    for src_name, title, out_name in jobs:
        src = SHOTS / src_name
        if not src.is_file():
            raise RuntimeError("missing terminal capture: %s "
                               "(run demo/run_demo.sh first)" % src)
        page.set_content(_terminal_page(title, src.read_text()))
        page.wait_for_timeout(300)
        _shot(page, SHOTS / out_name, full_page=True)
    # Shot 4 — proof: the REAL evidence manifest (raw API responses +
    # SHA-256, written by capture_cmc_evidence.py, milestone 29–30 Nov).
    # Falls back to the fixture manifest only if evidence was never
    # captured — the fallback is labelled as such in the shot title.
    manifest = ROOT / "evidence" / "cmc" / "manifest.json"
    title = ("Evidence — evidence/cmc/manifest.json "
             "(raw API responses, SHA-256 manifest)")
    if not manifest.is_file():
        manifest = ROOT / "fixtures" / "cmc" / "MANIFEST.json"
        title = ("Evidence — fixtures/cmc/MANIFEST.json (fallback: "
                 "evidence/cmc/manifest.json not captured yet)")
    if not manifest.is_file():
        raise RuntimeError("missing manifest: %s" % manifest)
    page.set_content(_terminal_page(title, manifest.read_text()))
    page.wait_for_timeout(300)
    _shot(page, SHOTS / "shot-4-evidence-manifest.png", full_page=True)
    browser.close()
    return 0


def _dashboard_context(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        viewport=VIEWPORT,
        record_video_dir=str(VIDEO_DIR),
        record_video_size=VIEWPORT)
    return browser, context


def phase_dashboard(playwright, symbol):
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    browser, context = _dashboard_context(playwright)
    page = context.new_page()
    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_selector("#board-body tr", timeout=10000)
    page.wait_for_timeout(500)
    if symbol == "NVDA":
        _shot(page, SHOTS / "shot-3-dashboard-board.png")
    row = page.locator("#board-body tr", has_text=symbol).first
    if row.count() == 0:
        raise RuntimeError("symbol %s not found on the dashboard board "
                           "(is the right snapshot served?)" % symbol)
    row.click()
    page.wait_for_selector("#detail:not([hidden])", timeout=10000)
    page.wait_for_timeout(500)
    if symbol == "NVDA":
        _shot(page, SHOTS / "shot-3-detail-nvda.png", full_page=True)
    else:
        detail = page.locator("#detail").inner_text()
        if "no_tokens" not in detail:
            raise RuntimeError(
                "expected NO_SIGNAL/no_tokens in the detail pane for "
                "%s, got: %s" % (symbol, detail[:200]))
        _shot(page, SHOTS / "shot-3b-detail-nosignal.png", full_page=True)
    video_path = page.video.path() if page.video else None
    context.close()
    browser.close()
    if video_path:
        print("video: %s" % video_path)
    return 0


def phase_closing(playwright):
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    browser, context = _dashboard_context(playwright)
    page = context.new_page()
    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_selector("#board-body tr", timeout=10000)
    page.wait_for_timeout(500)
    footer = page.locator("footer").inner_text()
    for needle in ("github.com/rwnliwan/cmc-rwa-radar", "#BuildwithCMC"):
        if needle not in footer:
            raise RuntimeError("closing text missing from dashboard "
                               "footer: %s" % needle)
    _shot(page, SHOTS / "shot-5-closing.png", full_page=True)
    video_path = page.video.path() if page.video else None
    context.close()
    browser.close()
    if video_path:
        print("video: %s" % video_path)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="capture.py",
        description="RWA Radar demo capture — screenshots per shot "
                    "(Playwright headless; no API key, no API calls).")
    parser.add_argument("--phase", required=True,
                        choices=["terminal", "dashboard", "closing"],
                        help="which shots to capture")
    parser.add_argument("--select", default=None,
                        help="dashboard symbol to click (NVDA or FGI)")
    args = parser.parse_args(argv)

    if args.phase == "dashboard" and not args.select:
        parser.error("--phase dashboard needs --select SYMBOL")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        if args.phase == "terminal":
            return phase_terminal(playwright)
        if args.phase == "dashboard":
            return phase_dashboard(playwright, args.select)
        return phase_closing(playwright)


if __name__ == "__main__":
    sys.exit(main())
