# Faz 2.12: Altyazı Butonu + Log Penceresi

## Hedef
1. Torrent indirme tamamlandığında "Altyazı İndir" butonu göster
2. Subdl + OpenSubtitles ile Türkçe/İngilizce altyazı indir
3. Uygulama genelinde log penceresi (sağ alt köşe, toggle edilebilir)

## Görev 1: `core/torrent/subdl.py` — Yeni Dosya

```python
"""Subdl.com API ile altyazı arama ve indirme."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import requests

SUBDL_BASE = "https://api.subdl.com/api/v1"
SUBDL_DL_BASE = "https://dl.subdl.com"
REQUEST_TIMEOUT = 10


def search_subdl(
    title: str,
    api_key: str,
    imdb_id: str | None = None,
    season: int | None = None,
    episode: int | None = None,
    language: str = "TR",
) -> list[dict]:
    """Subdl API'de altyazı ara."""
    params: dict = {"api_key": api_key, "languages": language}

    if imdb_id:
        params["imdb_id"] = imdb_id.replace("tt", "")
    else:
        params["query"] = title

    if season is not None:
        params["season_number"] = season
    if episode is not None:
        params["episode_number"] = episode

    try:
        r = requests.get(
            f"{SUBDL_BASE}/subtitles",
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        return r.json().get("subtitles", [])
    except Exception as e:
        return []


def download_subdl(subtitle_url: str, output_path: Path) -> bool:
    """Subdl'den altyazıyı indir ve zip'ten .srt çıkar."""
    try:
        url = f"{SUBDL_DL_BASE}{subtitle_url}"
        r = requests.get(url, timeout=30)
        r.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Zip içinden en büyük .srt dosyasını çıkar
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            srt_files = [n for n in z.namelist() if n.lower().endswith(".srt")]
            if not srt_files:
                return False
            # En büyük .srt'yi al
            best = max(srt_files, key=lambda n: z.getinfo(n).file_size)
            output_path.write_bytes(z.read(best))
            return True

    except Exception:
        return False


def auto_subtitle_subdl(
    title: str,
    video_path: Path,
    api_key: str,
    imdb_id: str | None = None,
    season: int | None = None,
    episode: int | None = None,
    languages: list[str] | None = None,
    log_callback=None,
) -> list[Path]:
    """Film/dizi için Subdl'den altyazı indir.
    
    log_callback: opsiyonel, str mesaj alır (UI log için)
    """
    if languages is None:
        languages = ["TR", "EN"]

    def log(msg: str):
        if log_callback:
            log_callback(msg)

    downloaded: list[Path] = []
    video_stem = video_path.stem

    for lang in languages:
        log(f"[Subdl] {lang} altyazı aranıyor: {title}")
        results = search_subdl(
            title=title,
            api_key=api_key,
            imdb_id=imdb_id,
            season=season,
            episode=episode,
            language=lang,
        )

        if not results:
            log(f"[Subdl] {lang} için altyazı bulunamadı")
            continue

        log(f"[Subdl] {len(results)} altyazı bulundu, en iyi seçiliyor...")
        best = results[0]
        subtitle_url = best.get("url", "")

        if not subtitle_url:
            log(f"[Subdl] İndirme URL'si yok, atlanıyor")
            continue

        output_path = video_path.parent / f"{video_stem}.{lang.lower()}.srt"
        log(f"[Subdl] İndiriliyor: {output_path.name}")
        success = download_subdl(subtitle_url, output_path)

        if success:
            log(f"[Subdl] ✓ {lang} altyazı indirildi: {output_path.name}")
            downloaded.append(output_path)
        else:
            log(f"[Subdl] ✗ {lang} altyazı indirilemedi")

    return downloaded
```

## Görev 2: `desktop/ui/log_window.py` — Log Penceresi

```python
"""Uygulama log penceresi - sağ alt köşede toggle edilebilir."""
from __future__ import annotations

import tkinter as tk
import customtkinter as ctk
from desktop.ui import theme


class LogWindow(ctk.CTkToplevel):
    """Uygulama loglarını gösteren yüzer pencere."""

    def __init__(self, master):
        super().__init__(master)
        self.title("Log")
        self.geometry("600x300")
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.hide)

        # Ana pencereye göre konumlandır
        self._position_window()
        self._build()
        self.withdraw()  # Başta gizli

    def _position_window(self):
        """Sağ alt köşeye konumlandır."""
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"600x300+{sw - 620}+{sh - 380}")

    def _build(self):
        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color="transparent", height=32)
        toolbar.pack(fill="x", padx=8, pady=(6, 0))
        toolbar.pack_propagate(False)

        ctk.CTkLabel(
            toolbar,
            text="📋 Uygulama Logları",
            font=theme.FONT_BODY,
        ).pack(side="left")

        ctk.CTkButton(
            toolbar,
            text="Temizle",
            width=70,
            height=24,
            command=self.clear,
            fg_color=theme.COLOR_BG_SECONDARY,
            text_color=theme.COLOR_TEXT_MUTED,
            hover_color=theme.COLOR_BG_TERTIARY,
        ).pack(side="right")

        # Log metin alanı
        self.text = ctk.CTkTextbox(
            self,
            font=("Consolas", 11),
            wrap="word",
            state="disabled",
        )
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        # Renk tag'leri
        self.text._textbox.tag_config("info", foreground="#aaaaaa")
        self.text._textbox.tag_config("success", foreground="#4caf50")
        self.text._textbox.tag_config("warning", foreground="#ff9800")
        self.text._textbox.tag_config("error", foreground="#f44336")

    def log(self, message: str, level: str = "info"):
        """Mesaj ekle."""
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {message}\n"

        self.text.configure(state="normal")
        self.text._textbox.insert("end", line, level)
        self.text.configure(state="disabled")
        self.text._textbox.see("end")  # Otomatik scroll

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("0.0", "end")
        self.text.configure(state="disabled")

    def show(self):
        self.deiconify()
        self.lift()
        self.focus()

    def hide(self):
        self.withdraw()

    def toggle(self):
        if self.winfo_viewable():
            self.hide()
        else:
            self.show()
```

## Görev 3: `desktop/ui/download_item.py` — Altyazı Butonu Ekle

`mark_complete` metodundan sonra "Altyazı İndir" butonu göster:

```python
def mark_complete(self, video_path=None) -> None:
    """İndirme tamamlandı."""
    self._video_path = video_path
    self.progress_bar.set(1.0)
    self.status_label.configure(
        text="✓ Tamamlandı",
        text_color=theme.COLOR_SUCCESS,
    )
    self.cancel_btn.pack_forget()

    # Altyazı butonu göster
    self._show_subtitle_btn()


def _show_subtitle_btn(self):
    """Altyazı indirme butonu göster."""
    if hasattr(self, "_subtitle_btn"):
        return  # Zaten var

    self._subtitle_btn = ctk.CTkButton(
        self.frame,
        text="🔤 Altyazı",
        width=90,
        height=28,
        command=self._on_subtitle_click,
        fg_color="#1565c0",
        hover_color="#0d47a1",
        font=theme.FONT_SMALL,
    )
    self._subtitle_btn.pack(side="right", padx=(4, 8))


def _on_subtitle_click(self):
    """Altyazı butonuna basıldı."""
    if self._on_subtitle:
        self._subtitle_btn.configure(text="⏳ Aranıyor...", state="disabled")
        self._on_subtitle(self._video_path)


def set_subtitle_result(self, found: bool, count: int = 0):
    """Altyazı sonucunu göster."""
    if not hasattr(self, "_subtitle_btn"):
        return
    if found:
        self._subtitle_btn.configure(
            text=f"✓ {count} altyazı",
            fg_color=theme.COLOR_SUCCESS,
            state="disabled",
        )
    else:
        self._subtitle_btn.configure(
            text="✗ Bulunamadı",
            fg_color=theme.COLOR_ERROR,
            state="normal",  # Tekrar denenebilsin
        )
```

`DownloadItem.__init__` parametrelerine `on_subtitle` ekle:

```python
def __init__(
    self,
    master,
    title: str,
    on_cancel=None,
    on_subtitle=None,  # ← YENİ
):
    self._on_subtitle = on_subtitle
    self._video_path = None
    # ... geri kalanı aynı
```

## Görev 4: `desktop/app.py` — Log Penceresi + Altyazı Entegrasyonu

### App.__init__'e log penceresi ekle:

```python
from desktop.ui.log_window import LogWindow

# __init__ içinde (UI kurulduktan sonra)
self.log_window = LogWindow(self)
```

### TopBar'a log butonu ekle:

```python
# Ayarlar butonunun yanına
ctk.CTkButton(
    topbar,
    text="📋",
    width=36,
    command=self.log_window.toggle,
    fg_color="transparent",
    hover_color=theme.COLOR_BG_SECONDARY,
).pack(side="right", padx=2)
```

### Log helper metodu ekle:

```python
def _log(self, message: str, level: str = "info"):
    """Log penceresine mesaj yaz."""
    import logging
    logger.log(
        {"info": logging.INFO, "success": logging.INFO,
         "warning": logging.WARNING, "error": logging.ERROR}.get(level, logging.INFO),
        message
    )
    if hasattr(self, "log_window"):
        self.after(0, lambda: self.log_window.log(message, level))
```

### `_start_torrent_download` güncelle:

```python
def _start_torrent_download(self, result, content_info):
    safe_name = re.sub(r'[<>:"/\\|?*]', "", result.title)[:40].strip()
    safe_name = f"{safe_name}_{uuid.uuid4().hex[:6]}"
    output_dir = Path(self.config_obj.download_dir) / "torrents" / safe_name
    output_dir.mkdir(parents=True, exist_ok=True)
    downloader = TorrentDownloader(output_dir)

    def on_subtitle_request(video_path):
        """Altyazı butonu tıklandı."""
        self._log(f"Altyazı aranıyor: {content_info.name}", "info")

        def subtitle_task():
            from core.torrent.subdl import auto_subtitle_subdl

            def log_cb(msg):
                self._log(msg, "info" if "✓" not in msg else "success")
                run_on_ui(self, self.log_window.show)  # Log penceresi aç

            subtitles = auto_subtitle_subdl(
                title=content_info.name,
                video_path=video_path,
                api_key=self.config_obj.subdl_api_key,
                imdb_id=result.imdb_id,
                season=content_info.season,
                episode=content_info.episode,
                languages=["TR", "EN"],
                log_callback=log_cb,
            )

            found = len(subtitles) > 0
            run_on_ui(self, item.set_subtitle_result, found, len(subtitles))

            if found:
                self._log(f"✓ {len(subtitles)} altyazı indirildi", "success")
            else:
                self._log("✗ Altyazı bulunamadı", "warning")

        threading.Thread(target=subtitle_task, daemon=True).start()

    item = DownloadItem(
        self.download_list,
        title=f"[Torrent] {result.title} {result.quality}",
        on_cancel=downloader.cancel,
        on_subtitle=on_subtitle_request,  # ← YENİ
    )
    self.download_list.add_item(item)

    def on_progress(progress):
        run_on_ui(self, item.update_torrent_progress, progress)

    def task():
        try:
            self._log(f"İndirme başlıyor: {result.title}", "info")
            video_path = downloader.download(
                magnet=result.magnet or "",
                torrent_url=result.torrent_url or "",
                progress_callback=on_progress,
            )

            # video_path None ise output_dir içinde ara
            if video_path is None:
                found_videos = []
                for ext in [".mkv", ".mp4", ".avi", ".mov"]:
                    for f in output_dir.rglob("*"):
                        try:
                            if f.is_file() and f.suffix.lower() == ext:
                                found_videos.append(f)
                        except Exception:
                            continue
                if found_videos:
                    video_path = max(found_videos, key=lambda f: f.stat().st_size)

            if video_path is None:
                raise Exception("İndirme başarısız veya iptal edildi")

            self._log(f"✓ İndirme tamamlandı: {video_path.name}", "success")
            run_on_ui(self, item.mark_complete, video_path)

        except Exception as e:
            self._log(f"✗ İndirme hatası: {e}", "error")
            run_on_ui(self, item.mark_error, e)

    threading.Thread(target=task, daemon=True).start()
```

## Görev 5: `desktop/config.py` — Subdl Key Ekle

```python
@dataclass
class AppConfig:
    # ... mevcut alanlar ...
    subdl_api_key: str = ""  # ← YENİ
```

## Görev 6: `desktop/ui/settings_window.py` — Subdl Key UI

"Torrent & Altyazı" sekmesine ekle:

```python
ctk.CTkLabel(parent, text="Subdl API Key (Türkçe altyazı):").pack(
    anchor="w", padx=10, pady=(10, 2)
)
self.subdl_key_entry = ctk.CTkEntry(
    parent, placeholder_text="Subdl API Key..."
)
self.subdl_key_entry.pack(fill="x", padx=10, pady=(0, 4))
self.subdl_key_entry.insert(0, self.config_obj.subdl_api_key)

ctk.CTkLabel(
    parent,
    text="ℹ Subdl: https://subdl.com/setting/api (ücretsiz)",
    font=theme.FONT_SMALL,
    text_color=theme.COLOR_TEXT_MUTED,
).pack(anchor="w", padx=10)
```

`_save()` metoduna ekle:
```python
self.config_obj.subdl_api_key = self.subdl_key_entry.get()
```

## Kabul Kriterleri

1. ✅ Torrent indirme tamamlandığında "🔤 Altyazı" butonu görünür
2. ✅ Butona basınca log penceresi otomatik açılır
3. ✅ Log'da "Subdl TR altyazı aranıyor...", "✓ indirildi" mesajları görünür
4. ✅ Video ile aynı klasörde `.tr.srt` ve `.en.srt` dosyaları oluşur
5. ✅ Bulunamazsa "✗ Bulunamadı" gösterir, tekrar denenebilir
6. ✅ Sağ üstte 📋 butonu ile log penceresi toggle edilebilir
7. ✅ Log penceresinde tüm uygulama logları (indirme başladı, tamamlandı, hatalar) görünür
8. ✅ Ayarlar → Torrent & Altyazı → Subdl API Key girilebilir

## Subdl API Key

Test edilen çalışan key: `iGLjkQwljs6TpCjqVpIztDGXSiebpr7v`

Ayarlardan gir: Torrent & Altyazı → Subdl API Key

## Sonuç

```
[İndirme Listesi]
─────────────────────────────────────────────
[Torrent] Game of Thrones S03E07  1080p
████████████████████ %100  ✓ Tamamlandı    [🔤 Altyazı]
─────────────────────────────────────────────

[📋 Log Penceresi - sağ alt]
[11:23:45] İndirme başlıyor: Game of Thrones S03E07...
[11:45:12] ✓ İndirme tamamlandı: Game.of.Thrones.S03E07.mkv
[11:45:13] [Subdl] TR altyazı aranıyor: Game of Thrones
[11:45:14] [Subdl] 4 altyazı bulundu, en iyi seçiliyor...
[11:45:15] [Subdl] ✓ TR altyazı indirildi: ...tr.srt
[11:45:16] [Subdl] ✓ EN altyazı indirildi: ...en.srt
```
