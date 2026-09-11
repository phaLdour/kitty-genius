"""Senaryo temizleyici — güvenli olmayan seçenek içeren veya görseli olmayan hero kullanan
senaryo dosyalarını siler. Çocuk kanalı için tehlikeli emoji (bıçak, şırınga, testere...) yasak.

Kullanım:  python tools/clean_scenarios.py            # ne silineceğini gösterir
           python tools/clean_scenarios.py --apply    # gerçekten siler
Sonra:     python generate.py --count N --start YYYY-MM-DD --per-day 2
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kg.brand import ROOT, pipeline
from kg.scenario import have_heroes

UNSAFE = {"kitchen knife", "knife", "fire", "scissors", "hammer", "firecracker",
          "chainsaw", "syringe", "saw", "drill", "axe", "thumbtack", "gun", "pill",
          "cigarette", "lighter", "razor", "sword", "bomb"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="gerçekten sil")
    a = ap.parse_args()
    P = pipeline()
    sdir = ROOT / P["paths"]["scenarios_dir"]
    out_dir = ROOT / P["paths"]["out_dir"]
    lib = ROOT / P["paths"]["hero_dir"] / "lib"
    man = ROOT / "config" / "manifest.txt"
    allow = {l.strip() for l in man.read_text("utf-8").splitlines() if l.strip()} if man.exists() else None
    bad = []
    for p in sorted(sdir.glob("kg-*.json")):
        sc = json.loads(p.read_text("utf-8"))
        why = []
        names = {o["name"].lower() for r in sc["rounds"] for o in r["options"]}
        if (u := sorted(names & UNSAFE)):
            why.append("güvensiz seçenek: " + ", ".join(u))
        miss = sorted({r["hero_key"] for r in sc["rounds"]
                       if not any((lib / f"{r['hero_key']}{e}").exists() for e in (".png", ".jpg", ".jpeg"))})
        if miss:
            why.append("görseli yok: " + ", ".join(miss))
        if allow is not None and sc["id"] not in allow:
            why.append("eski parti (manifest'te yok)")
        if why:
            bad.append((p, sc["id"], "; ".join(why)))
    if not bad:
        print("temiz — silinecek senaryo yok.")
        return
    for p, sid, why in bad:
        print(f"{'SİL' if a.apply else 'silinecek'}: {p.name:36} {why}")
        if a.apply:
            p.unlink()
            for extra in (out_dir / f"{sid}.mp4", out_dir / f"{sid}.log.json", out_dir / f"qc_{sid}.json"):
                if extra.exists():
                    extra.unlink()
                    print(f"     + {extra.name} silindi")
    if not a.apply:
        print(f"\n{len(bad)} dosya. Silmek için: python tools/clean_scenarios.py --apply")


if __name__ == "__main__":
    main()
