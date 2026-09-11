"""Pillow ile kart düzeni: hero + panel + soru + 2×2 seçenek + geri sayım + reveal."""
from __future__ import annotations
import math
from PIL import Image, ImageDraw, ImageFilter
from .brand import brand, hex_to_rgb, question_font
from .assets import EmojiAssets, hero_image, _noto_emoji

B = brand()
W, H = B["canvas"]["width"], B["canvas"]["height"]
L = B["layout"]
C = {k: hex_to_rgb(v) for k, v in B["colors"].items()}
HERO_H = round(H * L["hero_height_ratio"])
GRID = L["grid"]
TILE, GAP, TOP = GRID["tile"], GRID["gap"], GRID["top"]
GRID_W = TILE * 2 + GAP
GRID_X0 = (W - GRID_W) // 2
_assets = EmojiAssets()


def tile_positions() -> list[tuple[int, int]]:
    return [(GRID_X0 + c * (TILE + GAP), TOP + r * (TILE + GAP)) for r in range(2) for c in range(2)]


def _wrap(text: str, font, max_w: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_question(img: Image.Image, text: str) -> None:
    q = L["question"]
    d = ImageDraw.Draw(img)
    size = q["font_size"]
    font = question_font(size)
    lines = _wrap(text.upper(), font, q["max_width"], d)
    while len(lines) > q["max_lines"] and size > 48:      # sığmazsa küçült
        size -= 4
        font = question_font(size)
        lines = _wrap(text.upper(), font, q["max_width"], d)
    line_h = round(size * q["line_spacing"])
    total = line_h * len(lines)
    y = q["center_y"] - total // 2
    for ln in lines:
        d.text((W // 2, y), ln, font=font, fill=C["text"], anchor="ma",
               stroke_width=q["stroke_width"], stroke_fill=C["text_stroke"])
        y += line_h


def draw_tile(img: Image.Image, xy: tuple[int, int], opt: dict, size: int = TILE) -> None:
    x, y = xy
    r = round(GRID["radius"] * size / TILE)
    bw = round(GRID["border"] * size / TILE)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x, y, x + size, y + size), radius=r, fill=C["tile_border"])
    d.rounded_rectangle((x + bw, y + bw, x + size - bw, y + size - bw), radius=max(r - bw, 4), fill=C["tile_bg"])
    is_photo = _assets.photo(opt["name"]) is not None
    inner = size - 2 * bw if is_photo else round(size * GRID["emoji_ratio"])
    obj = _assets.render(opt["name"], opt["emoji"], inner)
    img.paste(obj, (x + (size - inner) // 2, y + (size - inner) // 2), obj)


FX = B.get("fx", {})


def enhance_hero(hero: Image.Image) -> Image.Image:
    """Doygunluk/kontrast/parlaklık artışı + vinyet: 'duygu' katmanı."""
    from PIL import ImageEnhance
    im = hero.convert("RGB")
    im = ImageEnhance.Color(im).enhance(FX.get("hero_saturation", 1.0))
    im = ImageEnhance.Contrast(im).enhance(FX.get("hero_contrast", 1.0))
    im = ImageEnhance.Brightness(im).enhance(FX.get("hero_brightness", 1.0))
    v = FX.get("hero_vignette", 0)
    if v > 0:
        w, h = im.size
        mask = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(mask)
        d.ellipse((-w * 0.25, -h * 0.35, w * 1.25, h * 1.35), fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(w * 0.18))
        dark = Image.new("RGB", (w, h), (0, 0, 0))
        im = Image.composite(im, Image.blend(im, dark, v), mask)
    return im


def hero_zoom(hero: Image.Image, z: float) -> Image.Image:
    """Ken Burns: merkezden z kadar yakınlaş (aynı boyutta döner)."""
    if z <= 1.001:
        return hero
    w, h = hero.size
    cw, ch = round(w / z), round(h / z)
    l, t = (w - cw) // 2, (h - ch) // 2
    return hero.crop((l, t, l + cw, t + ch)).resize((w, h), Image.BILINEAR)


def base_card(rnd: dict, hero: Image.Image, tile_scales: list[float] | None = None) -> Image.Image:
    """Soru + seçenekler (sayaç hariç). tile_scales: her kare için 0..1 pop-in ölçeği (None = hepsi tam)."""
    img = Image.new("RGB", (W, H), C["panel"])
    img.paste(hero, (0, 0))
    draw_question(img, rnd["question"])
    scales = tile_scales or [1.0] * 4
    for (x, y), opt, s in zip(tile_positions(), rnd["options"], scales):
        if s <= 0.02:
            continue
        size = max(8, round(TILE * s))
        off = (TILE - size) // 2
        if s >= 0.999:
            draw_tile(img, (x, y), opt)
        else:
            t = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw_tile(t, (0, 0), opt, size)
            img.paste(t, (x + off, y + off), t)
    return img


def white_flash(img: Image.Image, amount: float = 0.55) -> Image.Image:
    return Image.blend(img, Image.new("RGB", img.size, (255, 255, 255)), amount)


def draw_countdown(img: Image.Image, number: int, remaining: float) -> None:
    """remaining: 0..1 — sarı yayın kalan kısmı."""
    cd = L["countdown"]
    dia, cy, ring = cd["diameter"], cd["center_y"], cd["ring_width"]
    cx = W // 2
    d = ImageDraw.Draw(img)
    box = (cx - dia // 2, cy - dia // 2, cx + dia // 2, cy + dia // 2)
    d.ellipse(box, fill=C["countdown_bg"], outline=C["text_stroke"], width=4)
    if remaining > 0:
        d.arc(box, start=-90, end=-90 + 360 * remaining, fill=C["countdown_arc"], width=ring)
    font = question_font(cd["font_size"])
    d.text((cx, cy + 2), str(number), font=font, fill=C["countdown_text"], anchor="mm")


def reveal_card(rnd: dict, hero: Image.Image, scale: float, badge: bool) -> Image.Image:
    """Yanlışlar yok; doğru kare büyümüş + döndürülmüş, yeşil 👍 rozeti."""
    img = Image.new("RGB", (W, H), C["panel"])
    img.paste(hero, (0, 0))
    draw_question(img, rnd["question"])
    correct = next(o for o in rnd["options"] if o.get("correct"))
    rv = L["reveal"]
    size = round(TILE * rv["scale"] * scale)
    if FX.get("panel_glow") and scale > 0.5:
        gcx0, gcy0 = W // 2, TOP + GRID_W // 2
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        r = int(size * 0.85)
        gd.ellipse((gcx0 - r, gcy0 - r, gcx0 + r, gcy0 + r), fill=(255, 255, 255, 110))
        glow = glow.filter(ImageFilter.GaussianBlur(70))
        img.paste(glow, (0, 0), glow)
    tile = Image.new("RGBA", (size + 40, size + 40), (0, 0, 0, 0))
    draw_tile(tile, (20, 20), correct, size)
    tile = tile.rotate(rv["rotate_deg"] * scale, resample=Image.BICUBIC, expand=True)
    gcx, gcy = W // 2, TOP + GRID_W // 2
    img.paste(tile, (gcx - tile.width // 2, gcy - tile.height // 2), tile)
    if badge:
        bd = rv["badge_diameter"]
        bx, by = gcx + size // 2 - bd // 2, gcy - size // 2 - bd // 4
        d = ImageDraw.Draw(img)
        d.ellipse((bx, by, bx + bd, by + bd), fill=C["reveal_badge"], outline=C["tile_border"], width=8)
        thumb = _noto_emoji("👍")
        thumb.thumbnail((round(bd * 0.62), round(bd * 0.62)), Image.LANCZOS)
        img.paste(thumb, (bx + (bd - thumb.width) // 2, by + (bd - thumb.height) // 2), thumb)
    return img


def punch_in(img: Image.Image, zoom: float) -> Image.Image:
    """zoom>1: merkezden kırp ve tam boyuta büyüt (hızlı zoom hissi)."""
    if zoom <= 1.001:
        return img
    cw, ch = round(W / zoom), round(H / zoom)
    left, top = (W - cw) // 2, (H - ch) // 2
    return img.crop((left, top, left + cw, top + ch)).resize((W, H), Image.BILINEAR)


def ease_out_back(t: float) -> float:
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def hero_for(rnd_index: int, scenario_id: str, rtype: str = "", hero_key: str = "") -> Image.Image:
    return enhance_hero(hero_image(rnd_index, scenario_id, (W, HERO_H), rtype, hero_key))
