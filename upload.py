"""Kitty Genius Uploader — kendi kanalına zamanlanmış Shorts yükleme + istatistik okuma.

Kullanım:
  python upload.py auth                                   # bir kez: tarayıcıda OAuth izni, token.json yazılır
  python upload.py upload out/video.mp4 --publish-at 2026-09-12T23:00:00Z [--title "Choose Correctly. 🧠"]
  python upload.py stats                                  # kendi videolarının view/like sayıları
Kotayı ve kuralları config/pipeline.yaml belirler (madeForKids=true, kategori 22, dil en).
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from kg.brand import ROOT, pipeline

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube",          # videos.update = zamanlama değiştirme
          "https://www.googleapis.com/auth/youtube.readonly"]
Y = pipeline()["youtube"]


def _creds():
    import os
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token = ROOT / Y["token_file"]
    # CI (GitHub Actions): secret'lardan yaz, tarayıcı akışı yok
    if not token.exists() and os.environ.get("KG_TOKEN_JSON"):
        token.write_text(os.environ["KG_TOKEN_JSON"], "utf-8")
    cs = ROOT / Y["client_secret"]
    if not cs.exists() and os.environ.get("KG_CLIENT_SECRET_JSON"):
        cs.write_text(os.environ["KG_CLIENT_SECRET_JSON"], "utf-8")
    creds = Credentials.from_authorized_user_file(str(token), SCOPES) if token.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if os.environ.get("CI"):
                raise RuntimeError("KG_TOKEN_JSON geçersiz/süresi dolmuş — yerelde 'python upload.py auth' çalıştırıp "
                                   "token.json içeriğini KG_TOKEN_JSON secret'ına yeniden yapıştır.")
            flow = InstalledAppFlow.from_client_secrets_file(str(cs), SCOPES)
            creds = flow.run_local_server(port=0)
        token.write_text(creds.to_json(), "utf-8")
    return creds


def _service():
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=_creds())


def cmd_auth(_a):
    yt = _service()
    me = yt.channels().list(part="snippet,statistics", mine=True).execute()["items"][0]
    print(f"OK: {me['snippet']['title']}  abone={me['statistics'].get('subscriberCount')}  video={me['statistics'].get('videoCount')}")


def cmd_upload(a):
    from googleapiclient.http import MediaFileUpload
    path = Path(a.video)
    if not path.exists():
        sys.exit(f"dosya yok: {path}")
    publish_at = a.publish_at
    if publish_at:
        datetime.fromisoformat(publish_at.replace("Z", "+00:00"))  # format kontrolü
    body = {
        "snippet": {
            "title": a.title or Y["title_template"],
            "description": a.description or Y["description"],
            "categoryId": Y["category_id"],
            "defaultLanguage": Y["default_language"],
            "defaultAudioLanguage": Y["default_language"],
        },
        "status": {
            "privacyStatus": "private",              # zamanlanmış yayın için private + publishAt
            "selfDeclaredMadeForKids": bool(Y["self_declared_made_for_kids"]),
            "containsSyntheticMedia": True,          # AI görsel beyanı
            **({"publishAt": publish_at} if publish_at else {}),
        },
    }
    media = MediaFileUpload(str(path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = _service().videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"  yükleniyor %{int(status.progress() * 100)}", end="\r")
    vid = resp["id"]
    print(f"\nOK video id={vid}  https://youtube.com/shorts/{vid}  publishAt={publish_at or '-'}")
    log = ROOT / pipeline()["paths"]["archive_dir"] / "uploads.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": vid, "file": path.name, "publishAt": publish_at, "at": datetime.now(timezone.utc).isoformat()}) + "\n")


def cmd_stats(_a):
    yt = _service()
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, page = [], None
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50, pageToken=page).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        page = r.get("nextPageToken")
        if not page or len(ids) >= 200:
            break
    rows = []
    for i in range(0, len(ids), 50):
        r = yt.videos().list(part="snippet,statistics", id=",".join(ids[i:i + 50])).execute()
        for v in r["items"]:
            s = v["statistics"]
            rows.append((v["snippet"]["publishedAt"][:10], v["id"], int(s.get("viewCount", 0)), int(s.get("likeCount", 0)), v["snippet"]["title"]))
    rows.sort(reverse=True)
    print(f"{'tarih':10} {'id':12} {'view':>8} {'like':>6}  başlık")
    for d, vid, vc, lc, t in rows:
        print(f"{d:10} {vid:12} {vc:8d} {lc:6d}  {t[:40]}")
    out = ROOT / pipeline()["paths"]["archive_dir"] / f"stats_{datetime.now():%Y%m%d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), "utf-8")


def main():
    ap = argparse.ArgumentParser(prog="upload.py", description="Kitty Genius Uploader — own-channel scheduled Shorts upload + stats")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auth", help="OAuth ile giriş yap, kanalı doğrula")
    up = sub.add_parser("upload", help="videoyu private + publishAt ile yükle (madeForKids=true)")
    up.add_argument("video")
    up.add_argument("--publish-at", help="RFC3339 UTC, ör. 2026-09-12T23:00:00Z")
    up.add_argument("--title")
    up.add_argument("--description")
    sub.add_parser("stats", help="kendi videolarının view/like sayıları")
    a = ap.parse_args()
    {"auth": cmd_auth, "upload": cmd_upload, "stats": cmd_stats}[a.cmd](a)


if __name__ == "__main__":
    main()
