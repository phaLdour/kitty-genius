"""Config yükleme + font/renk yardımcıları."""
from __future__ import annotations
import os
from functools import lru_cache
from pathlib import Path
import yaml
from PIL import ImageFont

ROOT = Path(__file__).resolve().parent.parent


def load_yaml(rel: str) -> dict:
    with open(ROOT / rel, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=None)
def brand() -> dict:
    return load_yaml("config/brand.yaml")


@lru_cache(maxsize=None)
def pipeline() -> dict:
    return load_yaml("config/pipeline.yaml")


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def question_font(size: int) -> ImageFont.FreeTypeFont:
    fonts = brand()["fonts"]
    for key in ("question", "question_fallback"):
        p = ROOT / fonts[key]
        if p.exists():
            return ImageFont.truetype(str(p), size)
    raise FileNotFoundError("Soru fontu bulunamadı: fonts/ klasörüne Montserrat-ExtraBold.ttf veya Poppins-Bold.ttf koy")


def emoji_font() -> ImageFont.FreeTypeFont | None:
    """Noto Color Emoji sadece 109 px bitmap destekler; büyütme ayrıca yapılır."""
    p = brand()["fonts"].get("emoji", "")
    if p and os.path.exists(p):
        try:
            return ImageFont.truetype(p, 109)
        except OSError:
            return None
    return None
