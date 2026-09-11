"""Ses: SFX sentezi (tik, ding), edge-tts anlatım, zaman çizelgesine göre miks."""
from __future__ import annotations
import asyncio
import os
import math
import subprocess
import wave
from pathlib import Path
import numpy as np
from .brand import brand, ROOT

SR = 44100
A = brand()["audio"]


def _tone(freq: float, dur: float, decay: float = 8.0, vol: float = 0.6) -> np.ndarray:
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    env = np.exp(-decay * t)
    return (np.sin(2 * math.pi * freq * t) * env * vol).astype(np.float32)


def tick() -> np.ndarray:
    """Kısa, tok tık sesi (geri sayım)."""
    n = int(SR * 0.06)
    t = np.linspace(0, 0.06, n, endpoint=False)
    noise = (np.random.default_rng(1).standard_normal(n) * 0.25).astype(np.float32)
    env = np.exp(-60 * t).astype(np.float32)
    return (noise * env + _tone(1800, 0.06, decay=50, vol=0.5))


def ding() -> np.ndarray:
    """İki tonlu 'doğru cevap' ding'i."""
    a = _tone(1046.5, 0.9, decay=4, vol=0.5)   # C6
    b = _tone(1318.5, 0.9, decay=4, vol=0.5)   # E6
    b = np.concatenate([np.zeros(int(SR * 0.12), np.float32), b])[: len(a)]
    return a + b


def whoosh() -> np.ndarray:
    n = int(SR * 0.25)
    t = np.linspace(0, 0.25, n, endpoint=False)
    noise = np.random.default_rng(2).standard_normal(n).astype(np.float32)
    env = (np.sin(math.pi * t / 0.25) ** 2).astype(np.float32)
    return noise * env * 0.18


def pop() -> np.ndarray:
    """Kare gelirken kısa 'pop': hızlı yükselen frekans."""
    dur = 0.12
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    f = 300 + 900 * (t / dur)
    env = np.exp(-25 * t)
    return (np.sin(2 * math.pi * f * t) * env * 0.7).astype(np.float32)


def riser(dur: float = 1.0) -> np.ndarray:
    """Reveal'dan önce gerilim: yükselen filtreli gürültü + yükselen ton."""
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    noise = np.random.default_rng(3).standard_normal(n).astype(np.float32)
    env = (t / dur) ** 2
    tone = np.sin(2 * math.pi * (200 + 600 * t / dur) * t) * 0.35
    return ((noise * 0.25 + tone) * env).astype(np.float32)


def sparkle() -> np.ndarray:
    """Ding'in üstüne parıltı: rastgele yüksek kısa tonlar."""
    rng = np.random.default_rng(4)
    out = np.zeros(int(SR * 0.7), np.float32)
    for k in range(10):
        f = rng.choice([2093, 2637, 3136, 3520, 4186])
        s = _tone(f, 0.15, decay=25, vol=0.25)
        i = int(SR * (0.05 + k * 0.05))
        out[i:i + len(s)] += s[: len(out) - i]
    return out


def db(x: float) -> float:
    return 10 ** (x / 20)


async def _tts_async(text: str, voice: str, out: Path, rate: str) -> None:
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(out))


def tts(text: str, voice: str, out: Path) -> Path | None:
    """edge-tts ile mp3 üretir; ağ yoksa None döner (video sessiz anlatımla devam eder)."""
    try:
        asyncio.run(_tts_async(text, voice, out, A.get("tts_rate", "+0%")))
        return out if out.exists() and out.stat().st_size > 0 else None
    except Exception as e:  # noqa: BLE001
        if os.environ.get("KG_REQUIRE_TTS") == "1":
            raise RuntimeError(f"TTS zorunlu ama başarısız ({voice}): {e}") from e
        print(f"[tts] atlandı ({voice}): {e}")
        return None


def load_audio(path: Path) -> np.ndarray:
    """ffmpeg ile mono float32 PCM'e çevir."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def mix_timeline(total: float, events: list[tuple[float, np.ndarray, float]]) -> np.ndarray:
    """events: (başlangıç sn, örnekler, kazanç dB)."""
    buf = np.zeros(int(SR * total) + SR, np.float32)
    for start, samples, gain in events:
        i = int(start * SR)
        j = min(i + len(samples), len(buf))
        buf[i:j] += samples[: j - i] * db(gain)
    peak = float(np.max(np.abs(buf))) or 1.0
    if peak > 0.98:
        buf *= 0.98 / peak
    return buf[: int(SR * total)]


def write_wav(path: Path, samples: np.ndarray) -> None:
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
