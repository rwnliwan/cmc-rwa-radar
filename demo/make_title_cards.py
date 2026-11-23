#!/usr/bin/env python3
"""RWA Radar — title-card overlays for the final demo video.

Re-cut 23 Nov 2026 20:34 WITA (recalibration v0.2.0). Renders one
transparent PNG per video segment (1280x104): a dark bar with a bold
title line + a subtitle line. All numbers come from the live demo
captures of 23 Nov 2026 20:34 WITA (demo/shots/terminal-*.txt) —
nothing invented. Thresholds are the calibrated robust-spread lines
(WATCH > 0.5%, EXTREME > 1.0%), not the old experimental ones.

Usage: python3 demo/make_title_cards.py
Output: demo/title-cards/<segment>.png
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "demo" / "title-cards"

FONT_TITLE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_SUB = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

W, H = 1280, 104

# (segment, title, subtitle)
CARDS = [
    ("s1", "SHOT 1 \u2014 THE PROBLEM: ONE STOCK, MANY ISSUERS, DIFFERENT PRICES",
     "NVDA \u00b7 9 tokens, 8 priced, 1 null (Dinari) \u00b7 spread 0.312% \u00b7 24h +3.46% \u00b7 7d \u221217.07%"),
    ("s2", "SHOT 2 \u2014 CLI LIVE: TOP-10 BOARD",
     "9 assets covered \u00b7 7 OK / 2 WATCH \u00b7 AMZN 20.2% \u00b7 SPCX 311.9% (mixed underlying)"),
    ("s3a_board", "SHOT 3 \u2014 DASHBOARD: BOARD",
     "Click a row for the detail pane \u2014 per-issuer prices, spread, sparkline"),
    ("s3a_clip", "SHOT 3 \u2014 DASHBOARD (LIVE RECORDING)",
     "Board \u2192 click NVDA \u2192 detail pane"),
    ("s3a_detail", "SHOT 3 \u2014 DASHBOARD: NVDA DETAIL",
     "Price per issuer \u00b7 spread 0.312% \u00b7 robust 0.150% \u00b7 sparkline 30 daily closes"),
    ("s3b_clip", "SHOT 3 \u2014 HONEST NO_SIGNAL (LIVE RECORDING)",
     "FGI \u2014 an asset with no tokens"),
    ("s3b_detail", "SHOT 3 \u2014 HONEST NO_SIGNAL",
     "FGI (rwa_id 4379) \u00b7 no_tokens \u00b7 no price, no spread, no invented numbers"),
    ("s4", "SHOT 4 \u2014 PROOF: REAL API CALLS",
     "evidence/cmc/manifest.json \u00b7 raw responses \u00b7 SHA-256 per file \u00b7 5 credits, 23 Nov 13:06 WITA"),
    ("s5", "RWA RADAR \u2014 BUILT WITH THE COINMARKETCAP RWA API",
     "github.com/rwnliwan/cmc-rwa-radar \u00b7 #BuildwithCMC \u00b7 Monitor status only \u2014 not investment advice"),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    title_font = ImageFont.truetype(FONT_TITLE, 27)
    sub_font = ImageFont.truetype(FONT_SUB, 19)
    for name, title, sub in CARDS:
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, W, H], fill=(0, 0, 0, 165))
        draw.rectangle([0, H - 3, W, H], fill=(138, 180, 248, 255))
        tw = draw.textlength(title, font=title_font)
        sw = draw.textlength(sub, font=sub_font)
        if tw > W - 56 or sw > W - 56:
            print("WARNING: text too wide in %s (title %.0f, sub %.0f)"
                  % (name, tw, sw), file=sys.stderr)
        draw.text((28, 12), title, font=title_font, fill=(255, 255, 255, 255))
        draw.text((28, 56), sub, font=sub_font, fill=(232, 232, 232, 255))
        path = OUT / ("%s.png" % name)
        img.save(path)
        print("card: %s (%d bytes)" % (path.name, path.stat().st_size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
