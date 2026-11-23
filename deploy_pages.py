#!/usr/bin/env python3
"""Deploy the CMC RWA Radar static dashboard to Cloudflare Pages
(project: cmc-rwa-radar). Token comes from the stored custom.cloudflare
surrogate via dynamic_credentials. Never prints the token.

Deploy dir: pages-deploy/ (dashboard/index.html + fresh cmc_snapshot.json).
The dashboard is fully static: serve.py never reads the API key and
never makes outbound calls, so the hosted copy has no key and no
live API dependency — only the snapshot file it ships with.
"""
import os
import subprocess
import sys

for p in (
    "/opt/hatch/workflow-skills/custom-connector-setup/bin",
    "/opt/muse/skills/custom-connector-setup/bin",
):
    if os.path.isdir(p):
        sys.path.insert(0, p)

from dynamic_credentials import dynamic_credential_entry  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
WRANGLER = os.path.expanduser(
    "~/workspace/radar-tokenized-stocks/web/node_modules/.bin/wrangler"
)

token = dynamic_credential_entry("custom.cloudflare")["surrogate"]
env = dict(os.environ)
env["CLOUDFLARE_API_TOKEN"] = token

cmd = [
    WRANGLER,
    "pages",
    "deploy",
    os.path.join(BASE, "pages-deploy"),
    "--project-name",
    "cmc-rwa-radar",
    "--commit-dirty=true",
]
print("Running:", " ".join(cmd[:4]), "...")
res = subprocess.run(cmd, env=env, cwd=BASE, capture_output=True, text=True)
print(res.stdout)
print(res.stderr, file=sys.stderr)
print("exit:", res.returncode)
sys.exit(res.returncode)
