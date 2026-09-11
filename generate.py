"""Senaryo üretimi. Kullanım:
  python generate.py --count 6 --start 2026-09-21        # 6 gün, günde 1 senaryo
Çıktı: scenarios/kg-<tarih>-<hikaye>-<hash>.json + out/archive/ledger.json (benzersizlik defteri)
Sonra: python tools/image_queue.py  → eksik hero/nesne görselleri (öncelik sırasıyla)
"""
import argparse
import random
from datetime import date, timedelta
from kg.scenario import generate, save


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--start", default=(date.today()+timedelta(days=1)).isoformat(), help="ilk senaryonun yayın günü (UTC); varsayılan yarın")
    ap.add_argument("--per-day", type=int, default=1, help="gün başına senaryo (kadans)")
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    d0 = date.fromisoformat(a.start)
    for i in range(a.count):
        sc = generate(d0 + timedelta(days=i // a.per_day), rng)
        p = save(sc)
        heroes = ", ".join(r["hero_key"] for r in sc["rounds"])
        print(f"{sc['publish_day']}  {sc['story_label']:20}  {p.name}   heroes: {heroes}")


if __name__ == "__main__":
    main()
