# Kitty Genius 🧠 — otomatik quiz-Shorts hattı (v0.1, Gün 1)

Durum: **compositor + SFX + zaman çizelgesi çalışıyor.** Hero görselleri ve seçenek nesneleri şimdilik placeholder
(Noto emoji); PC'de Fluent Emoji 3D indirilince ve SD render'ları `assets/hero/` içine düşünce otomatik olarak onları kullanır.

## Klasörler
```
config/brand.yaml      marka + düzen + zamanlama (tek kaynak; renk/font/ölçü buradan)
config/pipeline.yaml   yollar, kadans, benzersizlik kuralları, YouTube meta verisi, yasaklı liste
kg/                    layout.py (Pillow kart çizimi) · assets.py (emoji/hero) · audio.py (SFX, edge-tts, miks) · video.py (ffmpeg)
render.py              tek senaryodan mp4 üretir
scenarios/             senaryo JSON'ları (6 turluk mini hikâye)
tools/fetch_fluent_emoji.py   Fluent Emoji 3D indirici (PC'de bir kez)
assets/emoji|hero|music|sfx   varlıklar (git'e girmez)
out/                   mp4 + .log.json (üretim kanıtı)
```

## PC kurulumu (Windows, PowerShell)
```powershell
winget install Python.Python.3.12 Gyan.FFmpeg Git.Git
cd kitty-genius
py -3.12 -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python tools\fetch_fluent_emoji.py          # ~150 MB, bir kez
python render.py scenarios\sample_kittys_day.json   # out\sample-kittys-day-001.mp4
```
Montserrat ExtraBold istersen: fonts.google.com → Montserrat → indir → `Montserrat-ExtraBold.ttf` dosyasını `fonts/` içine at
(yoksa Poppins-Bold kullanılır; ikisi de OFL lisanslı, ticari kullanım serbest).

## Senaryo formatı
`scenarios/sample_kittys_day.json`: `rounds[]` → `type`, `question` (BÜYÜK HARF, ≤2 satır), `narration` (TTS metni),
`hero_prompt` (SD için), `options[4]` → `name` (Fluent emoji adı, ör. "glass of milk"), `emoji` (yedek karakter), `correct`.

## Zamanlama (brand.yaml → timing)
punch-in 0,4 s → soru 1,0 s → geri sayım 4 s (4-3-2-1) → reveal pop 0,3 s → reveal 2,2 s = **7,9 s/tur × 6 = 47,4 s**.

## Sıradaki adımlar
- Gün 2: maskot prompt şablonu + ComfyUI/Amuse ile hero render'ları → `assets/hero/<senaryo_id>_r<N>.png`
- Gün 3: müzik yatağı (`assets/music/*.mp3`, YouTube Audio Library) + `--music` ile miks; TTS ses rotasyonu
- Gün 5: senaryo motoru (hikâye iskeleti × tur şablonu × seçenek seti + 90 gün benzersizlik bekçisi + yasaklı liste)
- Gün 6: QC modülü · Gün 8: uploader (Data API, madeForKids=true, publishAt)
