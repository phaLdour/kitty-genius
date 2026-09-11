"""scenarios/ altındaki mp4'ü olmayan tüm senaryoları render eder (ses/müzik rotasyonlu).
Kullanım: python render_all.py [--force]
"""
import argparse
import json
import random
from pathlib import Path
from kg.brand import ROOT, brand, pipeline
from kg.video import build


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="var olan mp4'leri de yeniden üret")
    a = ap.parse_args()
    out_dir = ROOT / pipeline()["paths"]["out_dir"]
    out_dir.mkdir(exist_ok=True)
    voices = brand()["audio"]["tts_voices"]
    music = sorted((ROOT / pipeline()["paths"]["music_dir"]).glob("*.mp3"))
    last_voice, last_music = None, None
    scs = sorted((ROOT / pipeline()["paths"]["scenarios_dir"]).glob("kg-*.json"))
    if not scs:
        print("scenarios/ içinde kg-*.json yok. Önce: python generate.py --count 6 --start YYYY-MM-DD")
        return
    for p in scs:
        sc = json.loads(p.read_text("utf-8"))
        mp4 = out_dir / f"{sc['id']}.mp4"
        if mp4.exists() and not a.force:
            print(f"atla (var): {mp4.name}")
            continue
        voice = random.choice([v for v in voices if v != last_voice] or voices)
        m = random.choice([x for x in music if x != last_music] or music) if music else None
        print(f"render: {sc['id']}  ses={voice}  müzik={m.name if m else '-'}")
        build(sc, mp4, voice=voice, music=m)
        last_voice, last_music = voice, m
    print("bitti →", out_dir)


if __name__ == "__main__":
    main()
