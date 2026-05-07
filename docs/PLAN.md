# Video Downloader - Proje Planı

## Amaç
Güçlü, çok platformlu bir video indirici. Tek bir site veya servisle sınırlı değil — yt-dlp'nin desteklediği 1800+ siteden indirme yapabilen bir sistem.

## Genel Mimari

```
┌─────────────────────┐         ┌─────────────────────┐
│   Desktop App       │         │   Android App       │
│   (CustomTkinter)   │         │   (Kotlin+Compose)  │
│   LOKAL ÇALIŞIR     │         └──────────┬──────────┘
└──────────┬──────────┘                    │ HTTPS
           │ direkt                        │
           ▼                               ▼
    ┌─────────────┐              ┌─────────────────┐
    │ core modülü │              │  FastAPI Backend│
    │  (yt-dlp)   │              │  (VPS'te)       │
    └─────────────┘              │  + yt-dlp       │
                                 │  + auth         │
                                 │  + queue        │
                                 └─────────────────┘
```

**Önemli:** `core/` modülü hem desktop hem backend tarafından kullanılır. Tek kaynak, iki tüketici. Tekrar kod yazmıyoruz.

## Teknoloji Seçimleri

| Bileşen | Teknoloji | Sebep |
|---------|-----------|-------|
| İndirme motoru | yt-dlp | 1800+ site desteği, aktif geliştiriliyor |
| Medya işleme | ffmpeg | Video+ses birleştirme, format dönüşümü |
| Desktop UI | CustomTkinter | Basit, modern görünümlü, Python native |
| Backend | FastAPI | Modern, hızlı, async, otomatik dokümantasyon |
| Görev kuyruğu | Celery + Redis | Uzun süren indirmeleri arka planda yapmak için |
| Mobil | Kotlin + Jetpack Compose | Native Android, modern UI, paylaş menüsü entegrasyonu kolay |
| Deploy | Docker + Docker Compose | Tek komutla kurulum, taşınabilir |
| Reverse proxy | Caddy | Otomatik HTTPS, basit yapılandırma |

## Proje Yapısı

```
video-downloader/
├── core/                       # Ortak yt-dlp wrapper modülü
│   ├── __init__.py
│   ├── downloader.py           # Ana indirme mantığı
│   ├── extractor.py            # Video bilgisi çekme
│   ├── formats.py              # Format seçim mantığı
│   └── exceptions.py           # Özel hata sınıfları
│
├── desktop/                    # CustomTkinter masaüstü uygulaması
│   ├── main.py                 # Giriş noktası
│   ├── app.py                  # Ana pencere
│   ├── ui/
│   │   ├── url_input.py        # URL giriş bileşeni
│   │   ├── format_picker.py    # Format seçici
│   │   ├── download_list.py    # İndirme kuyruğu görünümü
│   │   └── settings.py         # Ayarlar penceresi
│   └── requirements.txt
│
├── backend/                    # FastAPI sunucu (VPS'e deploy edilecek)
│   ├── main.py                 # FastAPI app
│   ├── api/
│   │   ├── routes.py           # Endpoint'ler
│   │   └── auth.py             # API key kimlik doğrulama
│   ├── tasks/
│   │   ├── celery_app.py       # Celery yapılandırması
│   │   └── download_task.py    # Async indirme görevleri
│   ├── utils/
│   │   └── cleanup.py          # Eski dosyaları temizleme
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── Caddyfile               # Caddy yapılandırması
│   └── requirements.txt
│
├── android/                    # Android Studio projesi
│   └── (Faz 4'te oluşturulacak)
│
├── docs/                       # Faz dokümantasyonları
│   ├── PLAN.md                 # Bu dosya
│   ├── PHASE_1.md              # Core modül
│   ├── PHASE_2.md              # Desktop app
│   ├── PHASE_3.md              # Backend
│   ├── PHASE_4.md              # Android
│   └── PHASE_5.md              # VPS deploy
│
├── .gitignore
├── README.md
└── LICENSE
```

## Yol Haritası

### Faz 1: Core Modül
Hem desktop hem backend tarafından kullanılacak ortak yt-dlp wrapper'ını yaz. URL'den video bilgisi çekme, format listeleme, indirme, ilerleme callback'leri, hata yönetimi. **Bu modül CLI test edilebilir olmalı.**

### Faz 2: Desktop Uygulaması
CustomTkinter ile masaüstü arayüzü. Core modülünü kullanır. URL yapıştır, format seç, indir, ilerleme gör. İndirme kuyruğu, geçmiş, ayarlar.

### Faz 3: Backend (FastAPI)
Aynı core modülü kullanan REST API. Endpoint'ler: video bilgisi çek, indirme başlat, ilerleme sorgula, dosya indir. Celery ile arka plan görevleri. Redis ile kuyruk. API key auth. Otomatik dosya temizleme cron'u.

### Faz 4: Android Uygulaması
Kotlin + Jetpack Compose. Backend API'sine bağlanır. **Paylaş menüsü entegrasyonu** (TikTok, YouTube, Instagram'dan paylaş → uygulamamıza düşsün). İndirilen dosyayı Downloads klasörüne kaydet. Bildirim ile ilerleme.

### Faz 5: VPS Deploy
Docker Compose ile FastAPI + Celery + Redis + Caddy paketi. Domain bağlama, otomatik HTTPS, systemd ile auto-start, log rotation, yt-dlp otomatik güncelleme cron'u.

## Genel Prensipler (Her Faz İçin Geçerli)

- **Tip ipuçları (type hints) zorunlu** — tüm fonksiyonlarda
- **Docstring zorunlu** — tüm public fonksiyonlarda
- **Hata yönetimi** — bare `except:` yasak, spesifik exception'lar
- **Logging** — `print` yerine `logging` modülü
- **Config dosyaları** — hardcoded değerler yok, `.env` veya `config.py`
- **Test edilebilirlik** — her modül kendi başına çalıştırılabilir olmalı
- **Cross-platform** — Windows/Linux/Mac uyumlu (desktop için)

## Özellik Listesi

### Olmazsa olmaz (MVP)
- [x] Tek URL'den indirme
- [x] Format/kalite seçimi (144p–4K, sadece ses)
- [x] İlerleme göstergesi
- [x] Hata yönetimi (private video, geçersiz URL, ağ hatası)

### Önemli
- [ ] Toplu indirme (playlist, çoklu URL)
- [ ] Altyazı indirme (otomatik dahil)
- [ ] Metadata gömme (başlık, kapak, sanatçı)
- [ ] İndirme kuyruğu
- [ ] Hız limiti
- [ ] Devam ettirme (kesilen indirmeler)

### Lüks
- [ ] Login/cookie desteği (özel videolar için)
- [ ] Format dönüştürme sonrası (mp4 → mkv, vb.)
- [ ] Otomatik altyazı çevirisi
- [ ] Akıllı dosya isimlendirme (template)

## Bir Sonraki Adım

`PHASE_1.md` dosyasını Claude Code'a ver. Faz 1 tamamlanınca `PHASE_2.md`'yi al.
