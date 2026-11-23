#!/usr/bin/env python3
"""Backup susulan #3 CMC RWA Radar — file final sesudah fix round v0.4.2.
Folder: cmc-rwa-radar (1-blTU7gZpe9KHajVx9-lBGH0hdTP8TD_, under bug bounty).
SATU exec call = SATU kartu approval.
Semua file SUDAH ADA di Drive (dari backup #2) -> update in-place
(files update --upload, ID sama), folder tetap 20 file.
Update: 2 video voiced re-cut S2 (commit 2277d4b) + narration-script.md
(416/359 kata) + SUBMISSION.md (sinkron deskripsi Build baru + fix round).
Verifikasi md5 tiap file.
"""
import hashlib, json, os, subprocess, sys

CLI = "/opt/hatch/bin/hatch_gws_cli"
HOME = os.path.expanduser("~")
ENTRY = f"{HOME}/workspace/cmc-rwa-entry"
FOLDER = "1-blTU7gZpe9KHajVx9-lBGH0hdTP8TD_"

UPDATES = [
    (f"{ENTRY}/demo/video-final-voiced.mp4", "video-final-voiced.mp4",
     "1oRWtdMLbjVcTa3rICvvNc7AxmBTAJlB_"),
    (f"{ENTRY}/demo/video-final-x-voiced.mp4", "video-final-x-voiced.mp4",
     "1cWfjk56u-FZ5vyqSofT1bibdesq6Ja-a"),
    (f"{ENTRY}/demo/narration-script.md", "narration-script.md",
     "1Ia7SobSpnBYX9FhP0PYVJ2xQ1CixwtIB"),
    (f"{ENTRY}/SUBMISSION.md", "SUBMISSION.md",
     "18Zti35xuC0ztMMQAxZ6MoVja991XrhM0"),
]


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cli(*args, timeout=900):
    r = subprocess.run([CLI, *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"CLI FAIL: {' '.join(args)}\nSTDOUT: {r.stdout[-1500:]}\nSTDERR: {r.stderr[-1500:]}")
    return json.loads(r.stdout) if r.stdout.strip() else {}


def drive_get(fid):
    return cli("drive", "files", "get", "--params",
               json.dumps({"fileId": fid, "fields": "id,name,md5Checksum,size"}))


def main():
    results = []
    for path, name, fid in UPDATES:
        assert os.path.exists(path), f"tidak ada: {path}"
        local_md5 = md5_of(path)
        cli("drive", "files", "update", "--upload", path, "--params",
            json.dumps({"fileId": fid}))
        info = drive_get(fid)
        ok = (info.get("md5Checksum") == local_md5 and info.get("name") == name)
        print(f"{'OK ' if ok else 'MISMATCH'} {name} (update) local={local_md5} drive={info.get('md5Checksum')} id={fid} size={info.get('size')}")
        results.append((name, ok))

    print("== verify folder ==")
    res = cli("drive", "files", "list", "--params",
              json.dumps({"q": f"'{FOLDER}' in parents",
                          "fields": "files(id,name,size,md5Checksum)"}))
    for f in res.get("files", []):
        print(f"  - {f.get('name')} | {f.get('size')} byte | md5={f.get('md5Checksum')}")
    print(f"  total file di folder: {len(res.get('files', []))}")
    bad = [n for n, ok in results if not ok]
    print(f"\nTOTAL: {len(results)} update, {len(results)-len(bad)} OK, {len(bad)} MISMATCH")
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
