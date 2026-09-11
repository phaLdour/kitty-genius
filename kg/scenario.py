"""Senaryo motoru: hikâye iskeleti × tur şablonu × seçenek seti → 6 turluk mini hikâye.
Benzersizlik bekçisi (90 gün), art arda aynı hikâye yok, yasaklı liste."""
from __future__ import annotations
import hashlib
import json
import random
import re
from datetime import date, datetime, timedelta
from pathlib import Path
import yaml
from .brand import ROOT, pipeline

CONTENT = yaml.safe_load((ROOT / "config" / "content.yaml").read_text("utf-8"))
P = pipeline()
LEDGER = ROOT / P["paths"]["archive_dir"] / "ledger.json"


def _load_ledger() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text("utf-8"))
    return {"rounds": {}, "scenarios": []}   # rounds: hash -> date


def _save_ledger(led: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(led, ensure_ascii=False, indent=1), "utf-8")


def _round_hash(rtype: str, question: str, options: list[dict]) -> str:
    key = rtype + "|" + question + "|" + ",".join(sorted(o["name"] for o in options))
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def _blocked(text: str) -> str | None:
    words = [w.lower() for w in P["blocklist"]["words"]] + [w.lower() for w in P["blocklist"]["themes"]]
    t = text.lower()
    for w in words:
        if re.search(rf"\b{re.escape(w)}\b", t):
            return w
    return None


def have_heroes(rtype: str) -> list[str]:
    """Bu tur tipi için diskte GERÇEK görseli olan hero anahtarları."""
    lib = ROOT / P["paths"]["hero_dir"] / "lib"
    return [k for k in CONTENT["rounds"][rtype]["heroes"]
            if any((lib / f"{k}{e}").exists() for e in (".png", ".jpg", ".jpeg"))]


def usable_stories() -> list[str]:
    """Her slotu için en az bir gerçek hero görseli olan hikâyeler."""
    return [s for s, spec in CONTENT["stories"].items()
            if all(have_heroes(t) for t in spec["slots"])]


def _opt(pair, correct: bool) -> dict:
    return {"name": pair[0], "emoji": pair[1], "correct": correct}


def build_round(rtype: str, rng: random.Random, led: dict, today: date, hero_override: str | None = None,
                avoid: set[str] | None = None) -> dict:
    tpl = CONTENT["rounds"][rtype]
    cutoff = (today - timedelta(days=P["uniqueness"]["no_repeat_round_days"])).isoformat()
    for _ in range(60):
        question = rng.choice(tpl["questions"])
        if rtype == "ODD":
            prs = [pr for pr in tpl["pairs"] if not avoid or not any(x[0] in avoid for x in pr)] or tpl["pairs"]
            base, odd = rng.choice(prs)
            if rng.random() < 0.5:
                base, odd = odd, base
            options = [_opt(base, False), _opt(base, False), _opt(base, False), _opt(odd, True)]
        else:
            cs = [x for x in tpl["correct"] if not avoid or x[0] not in avoid]
            c = rng.choice(cs or tpl["correct"])
            # aynı videoda aynı nesne iki kez görünmesin
            pool = [w for w in tpl["wrong"] if not avoid or w[0] not in avoid]
            if len(pool) < 3:
                pool = tpl["wrong"]
            wrongs = rng.sample(pool, 3)
            options = [_opt(c, True)] + [_opt(w, False) for w in wrongs]
        rng.shuffle(options)
        h = _round_hash(rtype, question, options)
        seen = led["rounds"].get(h)
        if seen and seen >= cutoff:
            continue
        correct = next(o for o in options if o["correct"])
        reveal = rng.choice(tpl["reveal"]).format(c=correct["name"])
        narration = rng.choice(tpl["narration"])
        have = have_heroes(rtype)
        if not have:
            raise RuntimeError(f"{rtype} için hiç hero görseli yok — tools/image_queue.py çalıştır")
        hero_key = hero_override or rng.choice(have)   # SADECE görseli olan sahneler
        text = " ".join([question, narration, reveal] + [o["name"] for o in options])
        if (b := _blocked(text)):
            raise ValueError(f"yasaklı kelime: {b} ({rtype})")
        return {"type": rtype, "question": question, "narration": narration, "reveal_line": reveal,
                "hero_key": hero_key, "options": options, "hash": h}
    raise RuntimeError(f"{rtype} için 90 günde tekrar etmeyen kombinasyon kalmadı — content.yaml havuzunu büyüt")


def generate(publish_day: date, rng: random.Random | None = None) -> dict:
    rng = rng or random.Random()
    led = _load_ledger()
    last_story = led["scenarios"][-1]["story"] if led["scenarios"] else None
    ok = usable_stories()
    if not ok:
        raise RuntimeError("hiçbir hikâyenin tüm turları için hero görseli yok")
    stories = [s for s in ok if s != last_story] if P["uniqueness"]["no_same_story_consecutive"] else list(ok)
    if not stories:
        stories = ok
    # az kullanılan hikâyeleri öne al
    used = {s: sum(1 for x in led["scenarios"] if x["story"] == s) for s in stories}
    least = min(used.values())
    story = rng.choice([s for s in stories if used[s] == least])
    spec = CONTENT["stories"][story]
    rounds, avoid = [], set()
    for t in spec["slots"]:
        r = build_round(t, rng, led, publish_day, avoid=avoid)
        avoid |= {o["name"] for o in r["options"]}
        rounds.append(r)
    sid = f"kg-{publish_day:%Y%m%d}-{story.replace('_', '')}-{hashlib.sha1(json.dumps(rounds, sort_keys=True).encode()).hexdigest()[:4]}"
    sc = {"id": sid, "story": story, "story_label": spec["label"], "publish_day": publish_day.isoformat(),
          "title": P["youtube"]["title_template"], "rounds": rounds}
    for r in rounds:
        led["rounds"][r["hash"]] = publish_day.isoformat()
    led["scenarios"].append({"id": sid, "story": story, "date": publish_day.isoformat(), "created": datetime.now().isoformat(timespec="seconds")})
    _save_ledger(led)
    return sc


def save(sc: dict) -> Path:
    d = ROOT / P["paths"]["scenarios_dir"]
    d.mkdir(exist_ok=True)
    p = d / f"{sc['id']}.json"
    p.write_text(json.dumps(sc, ensure_ascii=False, indent=2), "utf-8")
    return p


def hero_prompt_for(rtype: str, hero_key: str) -> str:
    """content.yaml sahne + hero_prompts.yaml duygu + base → tam prompt."""
    hp = yaml.safe_load((ROOT / "config" / "hero_prompts.yaml").read_text("utf-8"))
    scene = CONTENT["rounds"][rtype]["heroes"].get(hero_key, "")
    emo = hp["emotions"].get(rtype, hp["emotions"].get({"RAIN": "SAVE", "SNOW": "SAVE", "SUN": "DRINK", "TEETH": "ODD"}.get(rtype, ""), ""))
    return ", ".join(x for x in [emo, scene, hp["base"]] if x) + " No text, no watermark, no people."
