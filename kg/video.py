"""Senaryo → kare listesi (concat) → ses → ffmpeg mp4."""
from __future__ import annotations
import json
import shutil
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image
from . import layout as ly
from . import audio as au
from .brand import brand, pipeline, ROOT

T = brand()["timing"]
FPS = brand()["canvas"]["fps"]
ARC_FPS = 12          # sayaç yayı için yeterli
POP_FRAMES = 8
PUNCH_FRAMES = 10


class FrameList:
    def __init__(self, d: Path):
        self.dir = d
        self.items: list[tuple[str, float]] = []
        self.n = 0

    def add(self, img: Image.Image, dur: float) -> None:
        p = self.dir / f"f{self.n:05d}.png"
        img.save(p, compress_level=1)
        self.items.append((p.name, dur))
        self.n += 1

    def write_concat(self) -> Path:
        p = self.dir / "list.txt"
        with open(p, "w", encoding="utf-8") as f:
            for name, dur in self.items:
                f.write(f"file '{name}'\nduration {dur:.4f}\n")
            f.write(f"file '{self.items[-1][0]}'\n")   # concat demuxer son kareyi bir daha ister
        return p

    @property
    def total(self) -> float:
        return sum(d for _, d in self.items)


def build(scenario: dict, out_mp4: Path, voice: str | None = None, music: Path | None = None, keep_tmp: bool = False) -> dict:
    tmp = out_mp4.parent / f"_tmp_{scenario['id']}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    frames = FrameList(tmp)
    events: list[tuple[float, np.ndarray, float]] = []
    A = brand()["audio"]
    tick, ding, whoosh, pop, sparkle = au.tick(), au.ding(), au.whoosh(), au.pop(), au.sparkle()
    voices = A["tts_voices"]
    voice = voice or voices[0]
    log = {"scenario": scenario["id"], "voice": voice, "rounds": []}
    FX = brand().get("fx", {})
    zoom_total = FX.get("hero_zoom_per_round", 1.0)
    cs = T["countdown_seconds"]
    round_len = T["punch_in"] + 4 * T["tile_pop"] + T["question_hold"] + cs + T["reveal_pop"] + T["reveal_hold"]

    t = 0.0
    for i, rnd in enumerate(scenario["rounds"]):
        hero0 = ly.hero_for(i, scenario["id"], rnd.get("type", ""), rnd.get("hero_key", ""))
        r0 = t

        def hero_at(local_t: float):
            return ly.hero_zoom(hero0, 1 + (zoom_total - 1) * min(1.0, local_t / round_len))

        # anlatım + giriş whoosh
        mp3 = au.tts(rnd.get("narration", rnd["question"]), voice, tmp / f"tts_{i}.mp3")
        if mp3:
            events.append((t, au.load_audio(mp3), A.get("tts_gain_db", 0.0)))
        correct_name = next(o["name"] for o in rnd["options"] if o.get("correct"))
        reveal_line = rnd.get("reveal_line") or f"Yes! The {correct_name}!"
        mp3r = au.tts(reveal_line, voice, tmp / f"tts_{i}_reveal.mp3")
        events.append((t, whoosh, A["whoosh_gain_db"]))
        # 1) punch-in: hero + soru (kareler henüz yok)
        for k in range(PUNCH_FRAMES):
            z = 1.25 - 0.25 * ly.ease_out_back(k / (PUNCH_FRAMES - 1))
            z = max(1.0, min(1.25, z))
            fr = ly.base_card(rnd, hero_at(t - r0), tile_scales=[0, 0, 0, 0])
            ly.draw_countdown(fr, cs, 1.0)
            frames.add(ly.punch_in(fr, z), T["punch_in"] / PUNCH_FRAMES)
        t += T["punch_in"]
        # 2) kareler sırayla pop-in (her biri 3 kare animasyon + pop sesi)
        for j in range(4):
            events.append((t, pop, A["pop_gain_db"]))
            for k in range(3):
                sc = ly.ease_out_back((k + 1) / 3)
                scales = [1.0] * j + [max(sc, 0.05)] + [0.0] * (3 - j)
                fr = ly.base_card(rnd, hero_at(t - r0), tile_scales=scales)
                ly.draw_countdown(fr, cs, 1.0)
                frames.add(fr, T["tile_pop"] / 3)
            t += T["tile_pop"]
        # 3) kısa bekleme
        fr = ly.base_card(rnd, hero_at(t - r0))
        ly.draw_countdown(fr, cs, 1.0)
        frames.add(fr, T["question_hold"])
        t += T["question_hold"]
        # 4) geri sayım (yay animasyonu + Ken Burns) + tik + son saniye riser
        n = cs * ARC_FPS
        for k in range(n):
            tt = k / ARC_FPS
            fr = ly.base_card(rnd, hero_at(t - r0 + tt))
            ly.draw_countdown(fr, cs - int(tt), 1 - tt / cs)
            frames.add(fr, 1 / ARC_FPS)
        for s in range(cs):
            events.append((t + s, tick, A["tick_gain_db"]))
        events.append((t + cs - 1.0, au.riser(1.0), A["riser_gain_db"]))
        t += cs
        # 5) reveal: flaş + pop + ding + sparkle
        hero_r = hero_at(t - r0)
        if FX.get("reveal_flash"):
            frames.add(ly.white_flash(ly.reveal_card(rnd, hero_r, 0.3, badge=False)), 1 / FPS)
        for k in range(POP_FRAMES):
            sc = ly.ease_out_back((k + 1) / POP_FRAMES)
            frames.add(ly.reveal_card(rnd, hero_r, max(sc, 0.05), badge=(k == POP_FRAMES - 1)), (T["reveal_pop"] - 1 / FPS) / POP_FRAMES)
        events.append((t, ding, A["ding_gain_db"]))
        events.append((t + 0.1, sparkle, A["sparkle_gain_db"]))
        if mp3r:
            events.append((t + A.get("reveal_line_delay", 0.35), au.load_audio(mp3r), A.get("tts_gain_db", 0.0)))
        t += T["reveal_pop"]
        # 6) reveal bekleme (hero zoom devam eder: 2 kare)
        half = T["reveal_hold"] / 2
        frames.add(ly.reveal_card(rnd, hero_at(t - r0), 1.0, badge=True), half)
        frames.add(ly.reveal_card(rnd, hero_at(t - r0 + half), 1.0, badge=True), half)
        t += T["reveal_hold"]
        log["rounds"].append({"i": i, "type": rnd["type"], "question": rnd["question"], "start": round(r0, 2), "end": round(t, 2)})

    total = frames.total
    concat = frames.write_concat()
    wav = tmp / "mix.wav"
    au.write_wav(wav, au.mix_timeline(total, events))

    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(wav)]
    if music and Path(music).exists():
        cmd += ["-stream_loop", "-1", "-i", str(music),
                "-filter_complex", f"[2:a]volume={au.db(brand()['audio']['music_gain_db']):.3f}[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=0,loudnorm=I={brand()['audio']['target_lufs']}:TP=-1.5:LRA=11[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-filter_complex", f"[1:a]loudnorm=I={brand()['audio']['target_lufs']}:TP=-1.5:LRA=11[a]", "-map", "0:v", "-map", "[a]"]
    cmd += ["-r", str(FPS), "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(out_mp4)]
    subprocess.run(cmd, check=True)
    log["duration"] = round(total, 2)
    log["frames"] = frames.n
    (out_mp4.with_suffix(".log.json")).write_text(json.dumps(log, indent=2, ensure_ascii=False), "utf-8")
    if not keep_tmp:
        shutil.rmtree(tmp)
    return log
