"""Senaryodan hero prompt listesi üretir (Amuse'a yapıştırmak ya da ComfyUI API'ye vermek için).

Kullanım:  python tools/hero_prompts.py scenarios/sample_kittys_day.json
Çıktı:     out/prompts_<id>.txt  (+ ekrana basar)
"""
from __future__ import annotations
import json
import sys
import zlib
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent


def prompts_for(sc: dict) -> list[dict]:
    cfg = yaml.safe_load((ROOT / "config" / "hero_prompts.yaml").read_text("utf-8"))
    out = []
    for i, r in enumerate(sc["rounds"], 1):
        emo = cfg["emotions"].get(r.get("type", ""), "")
        pos = ", ".join(x for x in [emo, r.get("hero_prompt", ""), cfg["base"]] if x)
        seed = (zlib.crc32(sc["id"].encode()) + i) % 2_000_000_000
        out.append({"n": i, "type": r.get("type"), "file": cfg["settings"]["file_pattern"].format(scenario_id=sc["id"], n=i),
                    "seed": seed, "positive": pos, "negative": cfg["negative"], "size": cfg["settings"]["size"]})
    return out


def main():
    sc = json.loads(Path(sys.argv[1]).read_text("utf-8"))
    ps = prompts_for(sc)
    lines = []
    for p in ps:
        lines += [f"=== Tur {p['n']} ({p['type']}) → {p['file']}  | size {p['size']} | seed {p['seed']}",
                  "POSITIVE: " + p["positive"], "NEGATIVE: " + p["negative"], ""]
    txt = "\n".join(lines)
    out = ROOT / "out" / f"prompts_{sc['id']}.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text(txt, "utf-8")
    print(txt)
    print(f"→ {out}")


if __name__ == "__main__":
    main()
