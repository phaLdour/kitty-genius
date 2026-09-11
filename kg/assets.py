"""Görsel varlıklar: seçenek nesneleri (Fluent Emoji 3D → yoksa Noto emoji placeholder) ve hero görseli."""
from __future__ import annotations
import json
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from .brand import ROOT, brand, pipeline, emoji_font, hex_to_rgb


def _snake(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


class EmojiAssets:
    """assets/emoji/<snake_name>.png (Fluent 3D). index.json isim→dosya eşlemesi tutar."""

    def __init__(self):
        self.dir = ROOT / pipeline()["paths"]["emoji_dir"]
        idx = self.dir / "index.json"
        data = json.loads(idx.read_text("utf-8")) if idx.exists() else {}
        self.index: dict[str, str] = data.get("by_name", {})
        self.by_char: dict[str, str] = data.get("by_char", {})

    def find(self, name: str, emoji_char: str = "") -> Path | None:
        key = _snake(name)
        for ch in (emoji_char, emoji_char.replace("️", "")):
            if ch and ch in self.by_char and (self.dir / self.by_char[ch]).exists():
                return self.dir / self.by_char[ch]
        if key in self.index:
            p = self.dir / self.index[key]
            if p.exists():
                return p
        p = self.dir / f"{key}.png"
        if p.exists():
            return p
        # gevşek eşleme: "milk" → "glass_of_milk"
        for k, v in self.index.items():
            if key in k or k in key:
                p = self.dir / v
                if p.exists():
                    return p
        return None

    def photo(self, name: str) -> Path | None:
        """assets/options/<snake>.png|.jpg — gerçekçi fotoğraf (öncelik 2/3)."""
        d = ROOT / pipeline()["paths"].get("options_dir", "assets/options")
        for ext in (".png", ".jpg", ".jpeg"):
            q = d / (_snake(name) + ext)
            if q.exists():
                return q
        return None

    def render(self, name: str, emoji_char: str, size: int) -> Image.Image:
        """Sıra: gerçekçi fotoğraf (assets/options) → Fluent 3D PNG → Noto emoji (RGBA, size×size)."""
        ph = self.photo(name)
        if ph is not None:
            im = _cover(Image.open(ph).convert("RGB"), size, size).convert("RGBA")
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 12, fill=255)
            im.putalpha(mask)
            return im
        p = self.find(name, emoji_char)
        if p is not None:
            im = Image.open(p).convert("RGBA")
        else:
            im = _noto_emoji(emoji_char)
        im.thumbnail((size, size), Image.LANCZOS)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.paste(im, ((size - im.width) // 2, (size - im.height) // 2), im)
        return canvas


def _noto_emoji(ch: str) -> Image.Image:
    font = emoji_font()
    if font is None:
        # font yoksa gri daire
        im = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        ImageDraw.Draw(im).ellipse((16, 16, 240, 240), fill=(180, 180, 180, 255))
        return im
    im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((80, 80), ch, font=font, embedded_color=True, anchor="mm")
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    return im.resize((im.width * 4, im.height * 4), Image.LANCZOS)


EMOTION = {"FOOD": "😿", "FIND_MOM": "🙀", "TOY": "😺", "BATH": "😹", "SLEEP": "😽", "SAVE": "😿", "RAIN": "😿", "SNOW": "🥶", "SUN": "🥵", "BIRTHDAY": "😻", "ODD": "🤔", "DRINK": "😿", "SCHOOL": "😺", "TEETH": "😸"}


def hero_path(round_index: int, scenario_id: str, hero_key: str = "") -> Path | None:
    """Sıra: assets/hero/<scenario_id>_r<N>.png → assets/hero/lib/<hero_key>.png|jpg → yok."""
    d = ROOT / pipeline()["paths"]["hero_dir"]
    p = d / f"{scenario_id}_r{round_index + 1}.png"
    if p.exists():
        return p
    if hero_key:
        for ext in (".png", ".jpg", ".jpeg"):
            q = d / "lib" / f"{hero_key}{ext}"
            if q.exists():
                return q
    return None


def hero_image(round_index: int, scenario_id: str, size: tuple[int, int], rtype: str = "", hero_key: str = "") -> Image.Image:
    """Gerçek hero görseli (senaryoya özel ya da kütüphaneden) cover-fit; yoksa placeholder."""
    w, h = size
    p = hero_path(round_index, scenario_id, hero_key)
    if p is not None:
        return _cover(Image.open(p).convert("RGB"), w, h)
    return _placeholder_hero(w, h, round_index, EMOTION.get(rtype, "🐱"))


def _cover(im: Image.Image, w: int, h: int) -> Image.Image:
    scale = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    left, top = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((left, top, left + w, top + h))


def _placeholder_hero(w: int, h: int, i: int, emoji_char: str = "🐱") -> Image.Image:
    palettes = [((255, 226, 89), (255, 150, 60)), ((120, 220, 255), (60, 120, 255)), ((255, 170, 220), (200, 80, 200)),
                ((170, 255, 190), (40, 180, 120)), ((60, 60, 120), (20, 20, 60)), ((190, 210, 255), (80, 110, 200))]
    c1, c2 = palettes[i % len(palettes)]
    im = Image.new("RGB", (w, h), c1)
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / max(h - 1, 1)
        d.line([(0, y), (w, y)], fill=tuple(round(c1[k] * (1 - t) + c2[k] * t) for k in range(3)))
    cat = _noto_emoji(emoji_char)
    cat.thumbnail((int(h * 0.62), int(h * 0.62)), Image.LANCZOS)
    im.paste(cat, ((w - cat.width) // 2, (h - cat.height) // 2 + 20), cat)
    tag = ImageDraw.Draw(im)
    tag.text((w // 2, 40), "PLACEHOLDER HERO — SD render buraya gelecek", fill=(0, 0, 0), anchor="ma")
    return im
