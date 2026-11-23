#!/usr/bin/env python3
"""Backup CMC RWA Radar submission evidence to Google Drive.
Folder: cmc-rwa-radar (1-blTU7gZpe9KHajVx9-lBGH0hdTP8TD_, under bug bounty).
SATU exec call = SATU kartu approval.
Isi: 6 PDF screenshot alur submit DoraHacks (23 Nov 22:57-23:00 WITA) +
SUBMISSION.md + README + DESIGN + CMC_INTEGRATION + ENDPOINTS +
evidence manifest + 2 video demo. Verifikasi md5 tiap file + rename
bila upload mengabaikan nama (jadi 'Untitled').
"""
import hashlib, json, os, shutil, subprocess, sys

CLI = "/opt/hatch/bin/hatch_gws_cli"
HOME = os.path.expanduser("~")
ENTRY = f"{HOME}/workspace/cmc-rwa-entry"
BROWSER_OUT = (f"{HOME}/workspace/.hatch-browser/outputs/"
               "browser-task:63417727-04a2-5304-a2a1-71c1eb8fbaa7")
STAGE = f"{ENTRY}/submission-evidence"
FOLDER = "1-blTU7gZpe9KHajVx9-lBGH0hdTP8TD_"

PDFS = [
    ("browser-page-20261123T145758.088078838Z-0.pdf", "dorahacks-hackathon-detail-page.pdf"),
    ("browser-page-20261123T145811.267170072Z-1.pdf", "dorahacks-builds-list-search-rwa-radar.pdf"),
    ("browser-page-20261123T145856.075330486Z-2.pdf", "dorahacks-build-submission-modal-tracks.pdf"),
    ("browser-page-20261123T145940.225785816Z-3.pdf", "dorahacks-create-build-form.pdf"),
    ("browser-page-20261123T150009.843716032Z-4.pdf", "dorahacks-details-rules-page.pdf"),
    ("browser-page-20261123T150020.921533521Z-5.pdf", "dorahacks-tracks-page.pdf"),
]

OTHERS = [
    (f"{ENTRY}/SUBMISSION.md", "SUBMISSION.md"),
    (f"{ENTRY}/README.md", "README.md"),
    (f"{ENTRY}/DESIGN-CMC-RWA.md", "DESIGN-CMC-RWA.md"),
    (f"{ENTRY}/CMC_INTEGRATION.md", "CMC_INTEGRATION.md"),
    (f"{ENTRY}/CMC-RWA-ENDPOINTS.md", "CMC-RWA-ENDPOINTS.md"),
    (f"{ENTRY}/evidence/cmc/manifest.json", "evidence-manifest.json"),
    (f"{ENTRY}/demo/video-final.mp4", "video-final.mp4"),
    (f"{ENTRY}/demo/video-final-x.mp4", "video-final-x.mp4"),
]


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cli(*args, timeout=600):
    r = subprocess.run([CLI, *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"CLI FAIL: {' '.join(args)}\nSTDOUT: {r.stdout[-1500:]}\nSTDERR: {r.stderr[-1500:]}")
    return json.loads(r.stdout) if r.stdout.strip() else {}


def drive_get(fid):
    return cli("drive", "files", "get", "--params",
               json.dumps({"fileId": fid, "fields": "id,name,md5Checksum,size"}))


def main():
    os.makedirs(STAGE, exist_ok=True)
    uploads = []
    for src, name in PDFS:
        s = os.path.join(BROWSER_OUT, src)
        assert os.path.exists(s), f"tidak ada: {s}"
        d = os.path.join(STAGE, name)
        shutil.copyfile(s, d)
        uploads.append((d, name))
    for path, name in OTHERS:
        assert os.path.exists(path), f"tidak ada: {path}"
        uploads.append((path, name))

    results = []
    for path, name in uploads:
        local_md5 = md5_of(path)
        out = cli("drive", "files", "create", "--upload", path, "--json",
                  json.dumps({"name": name, "parents": [FOLDER]}))
        fid = out.get("id") or out.get("fileId")
        if not fid:
            raise RuntimeError(f"upload {name} returned no id: {out}")
        info = drive_get(fid)
        if info.get("name") != name:
            cli("drive", "files", "update", "--params", json.dumps({"fileId": fid}),
                "--json", json.dumps({"name": name}))
            info = drive_get(fid)
        remote_md5 = info.get("md5Checksum")
        ok = (remote_md5 == local_md5 and info.get("name") == name)
        print(f"{'OK ' if ok else 'MISMATCH'} {name} local={local_md5} drive={remote_md5} id={fid}")
        results.append((name, ok))
    print("== verify folder ==")
    res = cli("drive", "files", "list", "--params",
              json.dumps({"q": f"'{FOLDER}' in parents",
                          "fields": "files(id,name,size,md5Checksum)"}))
    for f in res.get("files", []):
        print(f"  - {f.get('name')} | {f.get('size')} byte | md5={f.get('md5Checksum')}")
    print(f"  total file di folder: {len(res.get('files', []))}")
    bad = [n for n, ok in results if not ok]
    print(f"\nTOTAL: {len(results)} upload, {len(results)-len(bad)} OK, {len(bad)} MISMATCH")
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
