"""Eksik hero sahnelerinin tam promptlarını listeler (Gemini'ye yapıştırmak için).

Kullanım:
  python tools/hero_queue.py                # tüm eksik sahneler
  python tools/hero_queue.py --limit 10     # günlük Gemini kotası kadar
Çıktı: out/hero_queue.txt + ekran. Kaydedeceğin dosya adı listede yazıyor:
  assets/hero/lib/<KEY>.png  (Gemini'den inen jpg'yi 1024x1024 png'ye çevirip oraya koy)
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kg.brand import ROOT, pipeline
from kg.scenario import hero_prompt_for, CONTENT


def missing() -> list[tuple[str, str]]:
    lib = ROOT / pipeline()["paths"]["hero_dir"] / "lib"
    out = []
    for rt, t in CONTENT["rounds"].items():
        for k in t["heroes"]:
            if not any((lib / f"{k}{e}").exists() for e in (".png", ".jpg", ".jpeg")):
                out.append((k, rt))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    rows = missing()
    if a.limit:
        rows = rows[:a.limit]
    lines = []
    for k, rt in rows:
        lines += [f"=== {k}  ({rt})  →  assets/hero/lib/{k}.png",
                  "Generate an image, landscape 4:3: " + hero_prompt_for(rt, k), ""]
    txt = "\n".join(lines)
    p = ROOT / pipeline()["paths"]["out_dir"] / "hero_queue.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, "utf-8")
    print(txt)
    print(f"{len(rows)} eksik sahne  →  {p}")


if __name__ == "__main__":
    main()
