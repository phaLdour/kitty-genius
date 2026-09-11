"""Onaylı videoları yükle + zamanla (kendi kanalına, madeForKids=true).
Kullanım:
  python schedule.py --dry-run            # ne yüklenecek, hangi tarihe — listeler
  python schedule.py --all                # QC OK + henüz yüklenmemiş tüm senaryolar
  python schedule.py --ids kg-20260921-birthday-c893,kg-20260922-...
Yayın saati: pipeline.yaml → cadence.publish_time_utc (16:00 PT). Audit geçmemişse video private düşer;
o zaman Studio'da videoyu açıp "Zamanla" ile aynı tarihi seçersin (tarih ekranda yazar).
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from kg.brand import ROOT, pipeline
import upload as up

P = pipeline()
OUT = ROOT / P["paths"]["out_dir"]
SC = ROOT / P["paths"]["scenarios_dir"]
UPLOG = ROOT / P["paths"]["archive_dir"] / "uploads.jsonl"


def uploaded_ids() -> set[str]:
    if not UPLOG.exists():
        return set()
    return {json.loads(l)["scenario"] for l in UPLOG.read_text("utf-8").splitlines() if l.strip() and "scenario" in l}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--ids", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=6, help="tek seferde en fazla kaç video (API kotası: gün 10.000 birim / yükleme 1.600 = 6 video)")
    a = ap.parse_args()
    want = set(a.ids.split(",")) if a.ids else None
    done = uploaded_ids()
    hh, mm = P["cadence"]["publish_time_utc"].split(":")
    plan = []
    for sp in sorted(SC.glob("kg-*.json")):
        sc = json.loads(sp.read_text("utf-8"))
        sid = sc["id"]
        if want is not None and sid not in want:
            continue
        if sid in done:
            continue
        qc = OUT / f"qc_{sid}.json"
        if not qc.exists() or json.loads(qc.read_text("utf-8"))["status"] != "OK":
            print(f"atla (QC OK değil): {sid}")
            continue
        mp4 = OUT / f"{sid}.mp4"
        publish_at = f"{sc['publish_day']}T{hh}:{mm}:00Z"
        plan.append((sid, mp4, publish_at))
    if len(plan) > a.limit:
        print(f"not: {len(plan)} aday var, kota nedeniyle ilk {a.limit} tanesi yüklenecek — kalanı yarın tekrar çalıştır.")
        plan = plan[:a.limit]
    if not plan:
        print("yüklenecek video yok.")
        return
    for sid, mp4, pa in plan:
        print(f"{'[dry] ' if a.dry_run else ''}{sid}  →  publishAt {pa}  ({mp4.stat().st_size // 1_000_000} MB)")
    if a.dry_run or not (a.all or want):
        return
    for sid, mp4, pa in plan:
        ns = argparse.Namespace(video=str(mp4), publish_at=pa, title=None, description=None)
        up.cmd_upload(ns)
        with open(UPLOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"scenario": sid, "publishAt": pa, "at": datetime.now(timezone.utc).isoformat()}) + "\n")


if __name__ == "__main__":
    main()
