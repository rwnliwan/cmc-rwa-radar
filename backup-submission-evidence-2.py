#!/usr/bin/env python3
"""Backup susulan CMC RWA Radar — file final sesudah submit (23 Nov 23:56 WITA).
Folder: cmc-rwa-radar (1-blTU7gZpe9KHajVx9-lBGH0hdTP8TD_, under bug bounty).
SATU exec call = SATU kartu approval.
Baru: 2 video voiced + logo + naskah narasi + verdict DeepSeek final.
Update: SUBMISSION.md (ID 18Zti35xuC0ztMMQAxZ6MoVja991XrhM0) ke versi final
yang sudah berisi status SUBMITTED + caption v2. Verifikasi md5 tiap file.
"""
import hashlib, json, os, subprocess, sys

CLI = "/opt/hatch/bin/hatch_gws_cli"
HOME = os.path.expanduser("~")
ENTRY = f"{HOME}/workspace/cmc-rwa-entry"
FOLDER = "1-blTU7gZpe9KHajVx9-lBGH0hdTP8TD_"
SUBMISSION_ID = "18Zti35xuC0ztMMQAxZ6MoVja991XrhM0"

NEW = [
    (f"{ENTRY}/demo/video-final-voiced.mp4", "video-final-voiced.mp4"),
    (f"{ENTRY}/demo/video-final-x-voiced.mp4", "video-final-x-voiced.mp4"),
    (f"{ENTRY}/demo/logo.png", "logo.png"),
    (f"{ENTRY}/demo/narration-script.md", "narration-script.md"),
    (f"{HOME}/workspace/bug-bounty/deepseek-cmc-final-review-2026-11-23.md",
     "deepseek-cmc-final-review-2026-11-23.md"),
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
    for path, name in NEW:
        assert os.path.exists(path), f"tidak ada: {path}"
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
        ok = (info.get("md5Checksum") == local_md5 and info.get("name") == name)
        print(f"{'OK ' if ok else 'MISMATCH'} {name} local={local_md5} drive={info.get('md5Checksum')} id={fid}")
        results.append((name, ok))

    # Update SUBMISSION.md in place (same file ID, new content)
    path = f"{ENTRY}/SUBMISSION.md"
    local_md5 = md5_of(path)
    cli("drive", "files", "update", "--upload", path, "--params",
        json.dumps({"fileId": SUBMISSION_ID}))
    info = drive_get(SUBMISSION_ID)
    ok = (info.get("md5Checksum") == local_md5 and info.get("name") == "SUBMISSION.md")
    print(f"{'OK ' if ok else 'MISMATCH'} SUBMISSION.md (update) local={local_md5} drive={info.get('md5Checksum')} id={SUBMISSION_ID} size={info.get('size')}")
    results.append(("SUBMISSION.md (update)", ok))

    print("== verify folder ==")
    res = cli("drive", "files", "list", "--params",
              json.dumps({"q": f"'{FOLDER}' in parents",
                          "fields": "files(id,name,size,md5Checksum)"}))
    for f in res.get("files", []):
        print(f"  - {f.get('name')} | {f.get('size')} byte | md5={f.get('md5Checksum')}")
    print(f"  total file di folder: {len(res.get('files', []))}")
    bad = [n for n, ok in results if not ok]
    print(f"\nTOTAL: {len(results)} operasi, {len(results)-len(bad)} OK, {len(bad)} MISMATCH")
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
