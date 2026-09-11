# Kitty Genius — tam otomatik kurulum

Bu repo GitHub Actions ile her gün kendi kendine: senaryo üretir → video render eder →
QC'den geçirir → YouTube'a zamanlanmış (private + publishAt) yükler → durumu commit'ler.
Kurulumdan sonra **senin hiçbir şey çalıştırman gerekmez**.

---

## 1. OAuth'u "Üretim" moduna al (ZORUNLU — yoksa 7 günde bozulur)

Google Cloud Console → **API'ler ve Hizmetler → OAuth izin ekranı**
→ Yayınlama durumu **"Test"** ise **"Uygulamayı YAYINLA" / "PUBLISH APP"** butonuna bas → onayla.

Neden: Test modundaki uygulamaların refresh token'ı **7 gün** sonra ölür ve otomasyon durur.
Üretim modunda süresiz çalışır. Doğrulama (verification) gerekmez — kendi kanalın olduğu için
"doğrulanmamış uygulama" uyarısını bir kez geçmen yeterli.

## 2. Taze token üret

Proje klasöründe:

```
del token.json
.venv\Scripts\python.exe upload.py auth
```

Tarayıcı açılır, Kitty Genius kanalının Google hesabıyla izin ver. `token.json` yazılır.

## 3. Repoyu GitHub'a gönder

```
cd C:\Users\PC1\Downloads\kitty-genius-v0.4\kitty-genius
git init -b main
git add -A
git commit -m "Kitty Genius pipeline"
git remote add origin https://github.com/phaLdour/kitty-genius.git
git push -u origin main
```

Repoyu önce github.com/new adresinden **public** olarak aç (adı: `kitty-genius`, README ekleme).
Public olması önemli: Actions dakikaları sınırsız olur.

> `token.json` ve `client_secret.json` `.gitignore`'da — repoya **gitmez**, doğrusu bu.

## 4. İki secret ekle

GitHub'da repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret adı | İçeriği |
|---|---|
| `KG_TOKEN_JSON` | `token.json` dosyasının **tüm içeriği** (Not Defteri'nde aç, hepsini kopyala) |
| `KG_CLIENT_SECRET_JSON` | `client_secret.json` dosyasının **tüm içeriği** |

## 5. İlk turu elle başlat

Repo → **Actions → "Kitty Genius — günlük video" → Run workflow**.

İlk tur ~25 dk sürer: 6 video render eder ve yükler. Sonrasında her gün **09:00 UTC (12:00 TR)**
kendiliğinden çalışır.

---

## Ne zaman ne olur

| Ne | Nerede | Ne sıklıkla |
|---|---|---|
| Senaryo üretimi | Actions | her gün, takvim 6 gün ileriye dolu tutulur |
| Render + QC + yükleme | Actions | her gün, en fazla 6 video (API kotası) |
| Yayın saati | YouTube | 23:00 UTC = **02:00 TR** |
| Kadans | `config/pipeline.yaml` → `cadence.ramp` | 12 Eyl'den 2/gün, 20 Eyl'den 3/gün |

Kadansı değiştirmek için `config/pipeline.yaml` içindeki `ramp` listesine satır ekle:

```yaml
  ramp:
    - {from: "2026-09-12", per_day: 2}
    - {from: "2026-09-20", per_day: 3}
```

## Sorun çıkarsa

- **Actions kırmızı yanıyorsa** → repo → Actions → son çalıştırma → hangi adımda patladığına bak.
- **"KG_TOKEN_JSON geçersiz"** → 1. ve 2. adımı tekrarla, secret'ı güncelle.
- **TTS hatası** → `KG_REQUIRE_TTS: "1"` yüzünden sessiz video üretilmesin diye bilerek patlatıyor.
- **Yükleme kotası** → günde 6 video sınırı Google'ın 10.000 birimlik kotasından geliyor.

## Görsel kütüphanesi

`assets/hero/lib/<SAHNE>.png` — her dosya bir sahne. `kg/scenario.py` **sadece görseli olan
sahneleri** seçer, yani eksik görsel videoyu bozmaz, sadece o sahne kullanılmaz.

Eksik sahnelerin promptunu görmek için:

```
.venv\Scripts\python.exe tools\hero_queue.py --limit 10
```
