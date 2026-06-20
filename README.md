# 🚀 Pro Downloader

Evrensel video, torrent ve dosya indirme uygulaması. Desktop (Windows) + Android + VPS Backend.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Kotlin](https://img.shields.io/badge/Kotlin-Jetpack%20Compose-purple)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 📸 Ekran Görüntüleri

<img width="1530" alt="Video İndirici" src="https://github.com/user-attachments/assets/0a36efc2-e5ca-4dc2-97a4-60870c1eb503" />

<details>
<summary>Daha fazla ekran görüntüsü göster</summary>

<br>

<img width="1900" alt="Torrent Arama" src="https://github.com/user-attachments/assets/47d89c3d-4e22-4e65-a63b-3dedf0bd4b8d" />

<img width="1918" alt="Aktif İndirmeler" src="https://github.com/user-attachments/assets/28fabb51-d9ec-45f2-a897-f674bd7e7905" />

<img width="1908" alt="Oyun İndirici" src="https://github.com/user-attachments/assets/21b7408a-d8bd-4ce4-b9ed-aaf0abf6fd1a" />

<img width="1918" alt="Log Penceresi" src="https://github.com/user-attachments/assets/898245e0-1fbd-4b26-94f8-9ecdd0662d03" />

</details>

---

## ✨ Özellikler

### 🎬 Video İndirici
- **1800+ site desteği** — YouTube, Twitter/X, Instagram, TikTok, Reddit ve daha fazlası
- **Format seçimi** — 360p'den 4K'ya, MP4/MKV/WebM
- **Sadece ses** — MP3/M4A olarak müzik indirme
- **Cookie desteği** — Firefox cookie cache sistemi ile login gerektiren siteler
- **Batch indirme** — Playlist ve toplu URL desteği

### 🧲 Torrent İndirici
- **Akıllı arama** — Film/dizi/oyun adı yaz, Jackett üzerinden 500+ torrent sitesinden ara
- **Otomatik altyazı** — Subdl + OpenSubtitles ile Türkçe/İngilizce altyazı
- **Duraklat/Devam** — İndirmeyi istediğin zaman duraklat, kaldığı yerden devam et
- **Resume desteği** — Uygulama kapansa bile kaldığı yerden devam
- **Uyku engelleme** — İndirme varken bilgisayar uyumaz

### 🎮 Oyun İndirici
- **PC oyunları** — Jackett üzerinden oyun torrentleri
- **FitGirl/DODI** — Güvenilir repack grupları öncelikli sıralama
- **Büyük dosya desteği** — 50+ GB oyunlar sorunsuz

### ☁ Dosya İndirici (Mega.nz / Pixeldrain)
- **Mega.nz desteği** — megatools entegrasyonu
- **Pixeldrain desteği** — Direkt link indirme
- **IP limit bypass** — Proxy rotasyonu ile limit aşma
- **VPS fallback** — PC limiti dolunca VPS üzerinden devam

### 📱 Android Uygulaması
- **VPS backend** bağlantılı
- **Paylaş menüsü** — Herhangi bir uygulamadan "Paylaş" ile video indir
- **Material Design 3** arayüz

### 📋 Log Penceresi
- Gerçek zamanlı indirme logları
- Hata takibi ve debug bilgisi
- Renkli mesajlar (başarı, uyarı, hata)

---

## 🛠 Kurulum

### Gereksinimler
- Python 3.12+
- Windows 10/11
- Node.js (YouTube JS challenge için)
- [libtorrent](https://github.com/arvidn/libtorrent/releases) (torrent için)
- [megatools](https://xff.cz/megatools/) (Mega.nz için)

### Desktop Uygulaması

```bash
# Repo'yu klonla
git clone https://github.com/alperenklc5/pro-downloader.git
cd pro-downloader

# Bağımlılıkları kur
pip install -r requirements.txt

# libtorrent kur (Windows - manuel kurulum gerekli)
# https://github.com/arvidn/libtorrent/releases adresinden
# libtorrent-2.x.x-cp312-cp312-win_amd64.whl indir
pip install libtorrent-2.x.x-cp312-cp312-win_amd64.whl

# Uygulamayı başlat
python -m desktop.main
```

### İlk Ayarlar

Uygulama açılınca **⚙ Ayarlar** sekmesine git:

| Ayar | Değer |
|------|-------|
| Jackett URL | `http://VPS_IP:9117` |
| Jackett API Key | Jackett panelinden al |
| OpenSubtitles API Key | [opensubtitles.com](https://www.opensubtitles.com/en/consumers) |
| Subdl API Key | [subdl.com/setting/api](https://subdl.com/setting/api) |

### VPS Backend (Opsiyonel)

Android uygulaması için VPS backend gereklidir:

```bash
# VPS'te Docker ile deploy
docker compose up -d

# Jackett kur
docker run -d --name jackett -p 9117:9117 linuxserver/jackett

# FlareSolverr kur (1337x için)
docker run -d --name flaresolverr -p 8191:8191 ghcr.io/flaresolverr/flaresolverr
```

### Android

1. Android Studio'da `android/` klasörünü aç
2. Build → APK oluştur
3. Telefona yükle
4. Ayarlar → API URL ve Key gir

---

## 📁 Proje Yapısı

```
pro-downloader/
├── core/                       # Çekirdek modüller
│   ├── extractor.py            # yt-dlp wrapper
│   ├── downloader.py           # Video indirici
│   ├── torrent/                # Torrent modülü
│   │   ├── searcher.py         # Jackett API
│   │   ├── downloader.py       # libtorrent wrapper
│   │   ├── subtitle.py         # OpenSubtitles
│   │   └── subdl.py            # Subdl.com API
│   └── hosting/                # Dosya hosting
│       ├── mega_downloader.py  # Mega.nz
│       ├── pixeldrain_downloader.py
│       ├── proxy_pool.py       # Proxy rotasyonu
│       └── smart_downloader.py # Akıllı indirici
├── desktop/                    # Desktop uygulaması
│   ├── app.py                  # Ana uygulama
│   ├── config.py               # Ayar yönetimi
│   └── ui/                     # UI bileşenleri
│       ├── sidebar.py          # Sol navigasyon
│       ├── status_bar.py       # Alt durum çubuğu
│       ├── log_window.py       # Log penceresi
│       ├── download_item.py    # İndirme kartı
│       └── pages/              # Sayfa modülleri
├── backend/                    # FastAPI backend (VPS)
│   ├── main.py
│   ├── api/
│   ├── tasks/
│   └── Dockerfile
├── android/                    # Android uygulaması
├── docker-compose.yml
└── requirements.txt
```

---

## 🔧 Teknoloji Stack

| Bileşen | Teknoloji |
|---------|-----------|
| Desktop UI | CustomTkinter (Python) |
| Video İndirme | yt-dlp + Node.js |
| Torrent | libtorrent + Jackett |
| Altyazı | Subdl.com + OpenSubtitles |
| Mega.nz | megatools CLI |
| Backend | FastAPI + Celery + Redis |
| Android | Kotlin + Jetpack Compose |
| Deploy | Docker + Coolify |

---

## 📋 API Endpoints (Backend)

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/api/health` | GET | Sağlık kontrolü |
| `/api/extract` | POST | Video bilgisi çek |
| `/api/download` | POST | İndirme başlat |
| `/api/status/{id}` | GET | İndirme durumu |
| `/api/file/{id}` | GET | Dosya indir |

---

## 🤝 Katkıda Bulunma

1. Fork et
2. Feature branch oluştur (`git checkout -b feature/yeni-ozellik`)
3. Commit et (`git commit -m 'Yeni özellik ekle'`)
4. Push et (`git push origin feature/yeni-ozellik`)
5. Pull Request aç

---

## 📄 Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Detaylar için [LICENSE](LICENSE) dosyasına bakın.

---

## 🙏 Teşekkürler

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — Video indirme motoru
- [libtorrent](https://github.com/arvidn/libtorrent) — Torrent motoru
- [Jackett](https://github.com/Jackett/Jackett) — Torrent indexer API
- [Subdl.com](https://subdl.com) — Altyazı API
- [OpenSubtitles](https://www.opensubtitles.com) — Altyazı API
- [megatools](https://xff.cz/megatools/) — Mega.nz CLI
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — Modern Tkinter UI
- [FastAPI](https://fastapi.tiangolo.com) — Backend framework
