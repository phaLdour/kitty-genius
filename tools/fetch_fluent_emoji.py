"""Microsoft Fluent Emoji 3D PNG'lerini indirir (MIT lisans) ve assets/emoji/index.json üretir.

Kullanım (PC'de, repo kökünde):  python tools/fetch_fluent_emoji.py
~1.500 PNG + metadata (≈150 MB). Tekrar çalıştırınca sadece eksikleri indirir.
"""
from __future__ import annotations
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "emoji"
API = "https://api.github.com/repos/microsoft/fluentui-emoji/git/trees/main?recursive=1"
RAW = "https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/"


def snake(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def used_names() -> set[str]:
    """content.yaml'da geçen seçenek adları (+ emoji karakterleri) — CI'da sadece bunlar indirilir."""
    import yaml
    C = yaml.safe_load((ROOT / "config" / "content.yaml").read_text("utf-8"))
    names, chars = set(), set()
    for t in C["rounds"].values():
        for f in ("correct", "wrong"):
            for o in t.get(f, []):
                names.add(snake(o[0])); chars.add(o[1])
        for pr in t.get("pairs", []):
            for o in pr:
                names.add(snake(o[0])); chars.add(o[1])
    return names | {c for c in chars}


def main() -> None:
    only_used = "--used" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    print("Dosya listesi alınıyor…")
    r = requests.get(API, timeout=60)
    r.raise_for_status()
    tree = r.json()
    if tree.get("truncated"):
        print("UYARI: GitHub ağaç listesi kesildi; bazı emojiler eksik kalabilir.")
    paths = [t["path"] for t in tree["tree"] if t["type"] == "blob"]

    # assets/<Name>/3D/<x>.png  veya  assets/<Name>/Default/3D/<x>.png  (ten tonu olanlarda Default)
    pngs: dict[str, str] = {}
    for p in paths:
        m = re.match(r"assets/([^/]+)/(?:Default/)?3D/([^/]+\.png)$", p)
        if m:
            name = m.group(1)
            if name not in pngs or "/Default/" in p:
                pngs[name] = p
    metas = {re.match(r"assets/([^/]+)/metadata\.json$", p).group(1): p
             for p in paths if re.match(r"assets/([^/]+)/metadata\.json$", p)}
    print(f"{len(pngs)} adet 3D emoji bulundu.")
    if only_used:
        want = used_names()
        # ad eşleşmesi gevşek: "glass of milk" → "glass_of_milk"; kısmi eşleşmeyi de al
        keep = {n for n in pngs if snake(n) in want or any(w and (w in snake(n) or snake(n) in w) for w in want if len(w) > 3)}
        pngs = {n: p for n, p in pngs.items() if n in keep}
        print(f"  --used: {len(pngs)} tanesi indirilecek")

    sess = requests.Session()

    def fetch(name: str) -> tuple[str, str, str | None]:
        fn = snake(name) + ".png"
        dst = OUT / fn
        for attempt in range(3):
            try:
                if not dst.exists():
                    d = sess.get(RAW + pngs[name].replace(" ", "%20"), timeout=60)
                    d.raise_for_status()
                    dst.write_bytes(d.content)
                uni = None
                if name in metas:
                    mp = OUT / (snake(name) + ".json")
                    if not mp.exists():
                        m = sess.get(RAW + metas[name].replace(" ", "%20"), timeout=60)
                        m.raise_for_status()
                        mp.write_bytes(m.content)
                    try:
                        uni = json.loads(mp.read_text("utf-8")).get("unicode")
                    except Exception:  # noqa: BLE001
                        uni = None
                return name, fn, uni
            except Exception as e:  # noqa: BLE001
                time.sleep(1.5 * (attempt + 1))
                err = e
        print(f"  ! {name}: {err}")
        return name, fn, None

    by_name: dict[str, str] = {}
    by_char: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=12) as ex:
        for i, (name, fn, uni) in enumerate(ex.map(fetch, sorted(pngs)), 1):
            if (OUT / fn).exists():
                by_name[snake(name)] = fn
                if uni:
                    # "1f95b" veya "1f3f3 fe0f 200d 1f308" → gerçek karakter
                    try:
                        ch = "".join(chr(int(cp, 16)) for cp in uni.split())
                        by_char[ch] = fn
                        by_char[ch.replace("️", "")] = fn
                    except ValueError:
                        pass
            if i % 100 == 0:
                print(f"  {i}/{len(pngs)}")
    (OUT / "index.json").write_text(json.dumps({"by_name": by_name, "by_char": by_char}, ensure_ascii=False, indent=1), "utf-8")
    print(f"Bitti: {len(by_name)} emoji, index.json yazıldı → {OUT}")


if __name__ == "__main__":
    sys.exit(main())
