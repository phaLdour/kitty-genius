"""Görsel üretim kuyruğu — öncelik sırasıyla (1 hero, 2 hayvan seçenekleri, 3 diğer nesneler) EKSİK görselleri listeler.

Kullanım:  python tools/image_queue.py [scenarios/*.json ...]   (argümansız: tüm senaryolar)
Çıktı:     out/image_queue.txt + out/image_queue.json
Hero'lar kütüphaneden gelir (assets/hero/lib/<hero_key>.png) → aynı sahne birçok videoda tekrar kullanılır.
Hayvan/nesne fotoğrafları assets/options/<isim>.png altında bir kez üretilir.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kg.scenario import hero_prompt_for  # noqa: E402
from kg.assets import hero_path  # noqa: E402

PIPE = yaml.safe_load((ROOT / "config" / "pipeline.yaml").read_text("utf-8"))
ANIMALS = set(PIPE["images"]["animal_words"])
OPT_DIR = ROOT / PIPE["paths"].get("options_dir", "assets/options")

OPTION_PROMPT = ("photorealistic photo of a {name}, cute and expressive, whole subject visible, centered, "
                 "plain soft white studio background, soft even lighting, vivid colors, sharp focus, square 1:1. "
                 "No text, no watermark, no people.")


def snake(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def is_animal(name: str) -> bool:
    return any(w in name.lower().split() for w in ANIMALS)


def queue_for(paths: list[str]) -> list[dict]:
    p1, p2, p3, seen_h, seen_o = [], [], [], set(), set()
    for sp in paths:
        sc = json.loads(Path(sp).read_text("utf-8"))
        for i, r in enumerate(sc["rounds"]):
            hk = r.get("hero_key", "")
            if hero_path(i, sc["id"], hk) is None:
                key = hk or f"{sc['id']}_r{i + 1}"
                if key in seen_h:
                    continue
                seen_h.add(key)
                file = f"assets/hero/lib/{hk}.png" if hk else f"assets/hero/{sc['id']}_r{i + 1}.png"
                p1.append({"prio": 1, "key": key, "file": file, "size": "4:3 landscape",
                           "prompt": hero_prompt_for(r["type"], hk) if hk else r.get("hero_prompt", "")})
            for o in r["options"]:
                key = snake(o["name"])
                if key in seen_o:
                    continue
                seen_o.add(key)
                if any((OPT_DIR / f"{key}{e}").exists() for e in (".png", ".jpg", ".jpeg")):
                    continue
                item = {"prio": 2 if is_animal(o["name"]) else 3, "key": key, "file": f"assets/options/{key}.png",
                        "prompt": OPTION_PROMPT.format(name=o["name"]), "size": "1:1 square"}
                (p2 if item["prio"] == 2 else p3).append(item)
    return p1 + p2 + p3


def main():
    paths = sys.argv[1:] or sorted(str(p) for p in (ROOT / "scenarios").glob("*.json"))
    q = queue_for(paths)
    lines = [f"EKSİK GÖRSEL KUYRUĞU — {len(q)} adet (P1 hero: {sum(i['prio']==1 for i in q)}, "
             f"P2 hayvan: {sum(i['prio']==2 for i in q)}, P3 nesne: {sum(i['prio']==3 for i in q)})", ""]
    for n, i in enumerate(q, 1):
        lines += [f"#{n}  [P{i['prio']}]  → {i['file']}   ({i['size']})", "PROMPT: " + i["prompt"], ""]
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    (out / "image_queue.txt").write_text("\n".join(lines), "utf-8")
    (out / "image_queue.json").write_text(json.dumps(q, ensure_ascii=False, indent=1), "utf-8")
    print("\n".join(lines[:2]))
    for i in q:
        print(f"  [P{i['prio']}] {i['file']}")


if __name__ == "__main__":
    main()
