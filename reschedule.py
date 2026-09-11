"""Yüklenmiş (zamanlanmış) videoları en erken günden başlayarak günde 1 olacak şekilde yeniden zamanlar.
Kullanım:
  python reschedule.py                 # bugünden (UTC 23:00 geçmediyse) başlar, günde 1
  python reschedule.py --start 2026-09-12 --per-day 1
Kaynak: out/archive/uploads.jsonl (upload.py'nin yazdığı video id'leri). Saat: pipeline.yaml → cadence.publish_time_utc.
"""
from __future__ import annotations
import argparse
import json
from datetime import date, datetime, timedelta, timezone
from kg.brand import ROOT, pipeline
import upload as up

P = pipeline()
UPLOG = ROOT / P["paths"]["archive_dir"] / "uploads.jsonl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=None, help="YYYY-MM-DD (UTC günü); boşsa bugün/yarın otomatik")
    ap.add_argument("--per-day", type=int, default=P["cadence"]["videos_per_day"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    hh, mm = (int(x) for x in P["cadence"]["publish_time_utc"].split(":"))
    now = datetime.now(timezone.utc)
    if a.start:
        d0 = date.fromisoformat(a.start)
    else:
        d0 = now.date() if now.hour * 60 + now.minute < hh * 60 + mm - 30 else now.date() + timedelta(days=1)
    rows = [json.loads(l) for l in UPLOG.read_text("utf-8").splitlines() if l.strip()]
    vids = [r for r in rows if "id" in r]
    seen, ordered = set(), []
    for r in sorted(vids, key=lambda r: r.get("publishAt") or ""):
        if r["id"] not in seen:
            seen.add(r["id"])
            ordered.append(r)
    if not ordered:
        print("uploads.jsonl içinde video id yok.")
        return
    yt = None if a.dry_run else up._service()
    for i, r in enumerate(ordered):
        day = d0 + timedelta(days=i // a.per_day)
        new_pa = datetime(day.year, day.month, day.day, hh, mm, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        tr = (datetime(day.year, day.month, day.day, hh, mm, tzinfo=timezone.utc) + timedelta(hours=3)).strftime("%d %b %H:%M")
        print(f"{r['id']}  {r.get('file','')[:34]:34} {r.get('publishAt')}  →  {new_pa}  (TR {tr})")
        if yt is not None:
            yt.videos().update(part="status", body={"id": r["id"], "status": {
                "privacyStatus": "private", "publishAt": new_pa,
                "selfDeclaredMadeForKids": bool(P["youtube"]["self_declared_made_for_kids"])}}).execute()
            r["publishAt"] = new_pa
    if yt is not None:
        with open(UPLOG, "a", encoding="utf-8") as f:
            for r in ordered:
                f.write(json.dumps({"id": r["id"], "file": r.get("file"), "publishAt": r["publishAt"], "rescheduled": now.isoformat()}) + "\n")
        print("bitti — Studio'da tarihleri kontrol et.")


if __name__ == "__main__":
    main()
