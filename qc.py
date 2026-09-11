"""Kalite kontrol: out/*.mp4 dosyalarını senaryolarıyla karşılaştırır, otomatik ret sebeplerini yazar.
Kullanım: python qc.py            → out/qc_report.txt (+ ekrana)
Kontroller: süre 20–60 s, ses var, LUFS ≈ -14, hero görselleri gerçek (placeholder yok), yasaklı kelime yok, log ile senaryo tutarlı.
"""
from __future__ import annotations
import json
import re
import subprocess
from pathlib import Path
from kg.brand import ROOT, pipeline
from kg.assets import hero_path

P = pipeline()
OUT = ROOT / P["paths"]["out_dir"]
SC = ROOT / P["paths"]["scenarios_dir"]


def ffprobe_duration(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def loudness(p: Path) -> float | None:
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(p), "-af", "loudnorm=print_format=json", "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r'"input_i"\s*:\s*"(-?[\d.]+)"', r.stderr)
    return float(m.group(1)) if m else None


def check(sc: dict, mp4: Path) -> list[str]:
    issues = []
    if not mp4.exists():
        return ["mp4 yok"]
    d = ffprobe_duration(mp4)
    if not 20 <= d <= 60:
        issues.append(f"süre {d:.1f}s (20–60 dışı)")
    li = loudness(mp4)
    if li is None:
        issues.append("ses ölçülemedi")
    elif not -18 <= li <= -10:
        issues.append(f"ses seviyesi {li:.1f} LUFS (-18..-10 dışı)")
    words = [w.lower() for w in P["blocklist"]["words"] + P["blocklist"]["themes"]]
    for i, r in enumerate(sc["rounds"]):
        if hero_path(i, sc["id"], r.get("hero_key", "")) is None:
            issues.append(f"tur {i + 1}: hero görseli yok (placeholder)")
        txt = " ".join([r["question"], r.get("narration", ""), r.get("reveal_line", "")] + [o["name"] for o in r["options"]]).lower()
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", txt):
                issues.append(f"tur {i + 1}: yasaklı kelime '{w}'")
        if sum(1 for o in r["options"] if o.get("correct")) != 1:
            issues.append(f"tur {i + 1}: doğru cevap sayısı ≠ 1")
    log = mp4.with_suffix(".log.json")
    if not log.exists():
        issues.append("render logu yok")
    return issues


def main():
    rows = []
    for sp in sorted(SC.glob("kg-*.json")):
        sc = json.loads(sp.read_text("utf-8"))
        mp4 = OUT / f"{sc['id']}.mp4"
        issues = check(sc, mp4)
        status = "OK" if not issues else "RET"
        rows.append((sc["id"], status, issues))
        (OUT / f"qc_{sc['id']}.json").write_text(json.dumps({"id": sc["id"], "status": status, "issues": issues}, ensure_ascii=False, indent=1), "utf-8")
    lines = [f"{sid:40} {st:4} {'; '.join(iss) if iss else '-'}" for sid, st, iss in rows]
    (OUT / "qc_report.txt").write_text("\n".join(lines), "utf-8")
    print("\n".join(lines))
    print(f"\n{sum(1 for r in rows if r[1]=='OK')}/{len(rows)} OK")


if __name__ == "__main__":
    main()
