"""Kullanım: python render.py scenarios/sample_kittys_day.json [--voice en-US-JennyNeural] [--music assets/music/x.mp3]"""
import argparse
import json
from pathlib import Path
from kg.video import build
from kg.brand import ROOT, pipeline


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("--voice", default=None)
    ap.add_argument("--music", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--keep-tmp", action="store_true")
    a = ap.parse_args()
    sc = json.loads(Path(a.scenario).read_text("utf-8"))
    out_dir = ROOT / pipeline()["paths"]["out_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = Path(a.out) if a.out else out_dir / f"{sc['id']}.mp4"
    log = build(sc, out, voice=a.voice, music=Path(a.music) if a.music else None, keep_tmp=a.keep_tmp)
    print(f"OK {out}  {log['duration']} s  {log['frames']} kare  ses={log['voice']}")


if __name__ == "__main__":
    main()
