"""Günlük tam otomatik tur — GitHub Actions bunu çalıştırır.

Sırayla:
  1. Takvimde boşluk varsa senaryo üretir (kadans: pipeline.yaml → cadence.ramp)
  2. Yüklenmemiş, yayın günü yakın senaryoları render eder (günlük kota bütçesi kadar)
  3. QC'den geçirir
  4. YouTube'a private + publishAt ile yükler; gün içindeki videolar cadence.slots_utc
     saatlerine dağıtılır (hepsi aynı dakikada yayına girmesin)
  5. Özet basar; kalıcı durum (scenarios/, ledger.json, uploads.jsonl) commit edilir

Günlük yükleme bütçesi uploads.jsonl'den okunur, yani workflow günde iki kez çalışsa bile
kota aşılmaz — sabahki tur patlarsa öğleden sonraki tur kaldığı yerden devam eder.

Kullanım:
  python run_daily.py
  python run_daily.py --dry-run
"""
from __future__ import annotations
import argparse
import json
import os
import random
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from kg.brand import ROOT, brand, pipeline
from kg.scenario import generate, save
from kg.video import build

P = pipeline()
C = P["cadence"]
OUT = ROOT / P["paths"]["out_dir"]
SC = ROOT / P["paths"]["scenarios_dir"]
UPLOG = ROOT / P["paths"]["archive_dir"] / "uploads.jsonl"


def scenarios() -> list[dict]:
    return [json.loads(p.read_text("utf-8")) for p in sorted(SC.glob("kg-*.json"))]


def _log_rows() -> list[dict]:
    if not UPLOG.exists():
        return []
    rows = []
    for l in UPLOG.read_text("utf-8").splitlines():
        if not l.strip():
            continue
        try:
            rows.append(json.loads(l))
        except json.JSONDecodeError:
            continue
    return rows


def uploaded_ids() -> set[str]:
    return {r["scenario"] for r in _log_rows() if "scenario" in r}


def uploads_today() -> int:
    """Bugün (UTC) kaç video yüklendi — günlük API kotası bütçesi için."""
    t = datetime.now(timezone.utc).date().isoformat()
    return sum(1 for r in _log_rows() if "scenario" in r and str(r.get("at", "")).startswith(t))


def slot_times() -> list[str]:
    return [str(x) for x in (C.get("slots_utc") or [C["publish_time_utc"]])]


def per_day_for(d: date, default: int) -> int:
    """cadence.ramp: tarihe göre günlük video sayısı; yoksa varsayılan."""
    n = default
    for r in sorted(C.get("ramp") or [], key=lambda r: str(r["from"])):
        if d >= date.fromisoformat(str(r["from"])):
            n = int(r["per_day"])
    return n


def publish_map() -> dict[str, str]:
    """senaryo id → publishAt (RFC3339). Aynı güne düşenler slot saatlerine dağıtılır.
    Zaten yüklenmiş videoların saatleri korunur ve o slotlar yeniden kullanılmaz."""
    slots = slot_times()
    logged = {r["scenario"]: r["publishAt"] for r in _log_rows()
              if "scenario" in r and r.get("publishAt")}
    out: dict[str, str] = {}
    taken: dict[str, set[str]] = {}
    scs = sorted(scenarios(), key=lambda s: s["id"])
    for sc in scs:                                   # 1) yüklenmişler saatini korur
        if sc["id"] in logged:
            pa = logged[sc["id"]]
            out[sc["id"]] = pa
            taken.setdefault(sc["publish_day"], set()).add(pa[11:16])
    for sc in scs:                                   # 2) kalanlara boş slotlar
        if sc["id"] in out:
            continue
        day = sc["publish_day"]
        used = taken.setdefault(day, set())
        free = [t for t in slots if t not in used]
        t = free[0] if free else slots[len(used) % len(slots)]
        used.add(t)
        out[sc["id"]] = f"{day}T{t}:00Z"
    return out


def fill_calendar(horizon: int, per_day: int, log: list[str]) -> None:
    """Bugünden itibaren `horizon` gün boyunca her güne kadans kadar senaryo olsun."""
    have: dict[str, int] = {}
    for sc in scenarios():
        have[sc["publish_day"]] = have.get(sc["publish_day"], 0) + 1
    rng = random.Random()
    today = datetime.now(timezone.utc).date()
    made = 0
    for i in range(horizon + 1):
        d = today + timedelta(days=i)
        if d == today:                       # bugünün slotları geçmiş olabilir
            continue
        for _ in range(per_day_for(d, per_day) - have.get(d.isoformat(), 0)):
            sc = generate(d, rng)
            save(sc)
            log.append(f"senaryo  + {sc['id']}  ({sc['story_label']})")
            made += 1
    if not made:
        log.append("senaryo  takvim zaten dolu")


def render_pending(window: int, limit: int, log: list[str]) -> None:
    if limit <= 0:
        log.append("render   günlük kota dolu, render atlandı")
        return
    done = uploaded_ids()
    voices = brand()["audio"]["tts_voices"]
    music = sorted((ROOT / P["paths"]["music_dir"]).glob("*.mp3"))
    today = datetime.now(timezone.utc).date()
    todo = []
    for sc in scenarios():
        if sc["id"] in done or (OUT / f"{sc['id']}.mp4").exists():
            continue
        if date.fromisoformat(sc["publish_day"]) > today + timedelta(days=window):
            continue
        todo.append(sc)
    todo.sort(key=lambda s: (s["publish_day"], s["id"]))
    rng = random.Random()
    last_v = last_m = None
    for sc in todo[:limit]:
        voice = rng.choice([v for v in voices if v != last_v] or voices)
        m = rng.choice([x for x in music if x != last_m] or music) if music else None
        build(sc, OUT / f"{sc['id']}.mp4", voice=voice, music=m)
        last_v, last_m = voice, m
        log.append(f"render   + {sc['id']}  ses={voice}  müzik={m.name if m else '-'}")
    if len(todo) > limit:
        log.append(f"render   {len(todo) - limit} senaryo sıraya kaldı")


def run_qc(log: list[str]) -> None:
    r = subprocess.run([sys.executable, "qc.py"], cwd=ROOT, capture_output=True, text=True)
    bad = [l for l in r.stdout.splitlines() if l.strip() and " OK " not in l and not l.startswith("=")]
    log.append("qc       " + ("hepsi OK" if not bad else "SORUN: " + " | ".join(bad[:5])))


def do_upload(limit: int, dry: bool, log: list[str]) -> None:
    if limit <= 0:
        log.append("yükleme  günlük kota dolu, yarın devam")
        return
    import upload as up
    done = uploaded_ids()
    pmap = publish_map()
    plan = []
    for sc in scenarios():
        if sc["id"] in done:
            continue
        mp4 = OUT / f"{sc['id']}.mp4"
        qc = OUT / f"qc_{sc['id']}.json"
        if not mp4.exists():
            continue
        if not qc.exists() or json.loads(qc.read_text("utf-8"))["status"] != "OK":
            log.append(f"yükleme  atlandı (QC): {sc['id']}")
            continue
        plan.append((sc["id"], mp4, pmap[sc["id"]]))
    plan.sort(key=lambda x: x[2])
    if not plan:
        log.append("yükleme  sıra boş")
        return
    for sid, mp4, pa in plan[:limit]:
        if dry:
            log.append(f"yükleme  [dry] {sid} → {pa}")
            continue
        ns = argparse.Namespace(video=str(mp4), publish_at=pa, title=None, description=None)
        up.cmd_upload(ns)
        with open(UPLOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"scenario": sid, "publishAt": pa,
                                "at": datetime.now(timezone.utc).isoformat()}) + "\n")
        log.append(f"yükleme  + {sid} → {pa}")
    if len(plan) > limit:
        log.append(f"yükleme  {len(plan) - limit} video sıraya kaldı (kota)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=6, help="kaç gün ileriye kadar senaryo hazır olsun")
    ap.add_argument("--window", type=int, default=8, help="kaç gün içinde yayınlanacakları render et")
    ap.add_argument("--quota", type=int, default=int(C.get("quota_uploads_per_day", 6)),
                    help="günlük yükleme kotası (Google: 10.000 birim / 1.600 = 6)")
    ap.add_argument("--per-day", type=int, default=C["videos_per_day"], help="ramp yoksa varsayılan kadans")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    log: list[str] = []
    OUT.mkdir(parents=True, exist_ok=True)
    used = 0 if a.dry_run else uploads_today()
    budget = max(0, a.quota - used)
    log.append(f"kota     bugün {used}/{a.quota} kullanıldı, bu turda en fazla {budget} video")
    fill_calendar(a.horizon, a.per_day, log)
    render_pending(a.window, budget, log)
    run_qc(log)
    do_upload(budget, a.dry_run, log)
    print("\n=== KITTY GENIUS — günlük tur " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC") + " ===")
    for l in log:
        print(" ", l)
    (OUT / "daily_report.txt").write_text("\n".join(log), "utf-8")
    step = os.environ.get("GITHUB_STEP_SUMMARY")
    if step:
        Path(step).write_text("## Kitty Genius — günlük tur\n\n```\n" + "\n".join(log) + "\n```\n", "utf-8")


if __name__ == "__main__":
    main()
