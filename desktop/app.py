"""
Ana uygulama penceresi.

Tüm UI bileşenlerini birleştirir ve uygulama state'ini yönetir.
"""

from __future__ import annotations

import logging
import os
import threading
import tkinter.messagebox as msgbox
from pathlib import Path

import customtkinter as ctk

from core import DownloadOptions, ProgressInfo, VideoInfo
from core.cookie_cache import get_metadata, is_cache_valid, sync_from_browser
from core.error_messages import clean_ansi, humanize_error
from core.exceptions import AuthenticationRequiredError, CookieError
from core.torrent import (
    detect_from_url, ContentInfo, TorrentResult,
    TorrentDownloader, TorrentProgress, auto_subtitle,
)
from desktop.config import AppConfig
from desktop.ui import theme
from desktop.ui.error_dialog import ErrorDialog
from desktop.ui.download_item import DownloadItem
from desktop.ui.torrent_results import TorrentResultsDialog
from desktop.ui.download_list import DownloadList
from desktop.ui.format_picker import FormatPickerFrame
from desktop.ui.settings_window import SettingsWindow
from desktop.ui.url_input import UrlInputFrame
from desktop.ui.video_info import VideoInfoFrame
from desktop.utils.threading_helper import run_on_ui
from desktop.workers.download_worker import DownloadWorker
from desktop.workers.extract_worker import ExtractWorker

logger = logging.getLogger(__name__)


class App(ctk.CTk):
    """Video Downloader ana penceresi."""

    def __init__(self) -> None:
        super().__init__()

        self.config_obj = AppConfig.load()
        # Jackett ve OpenSubtitles key'lerini environment'a yaz
        # (subtitle.py dışında başka modüller os.getenv ile okuyabilir)
        os.environ["JACKETT_URL"] = self.config_obj.jackett_url
        os.environ["JACKETT_API_KEY"] = self.config_obj.jackett_api_key
        os.environ["OPENSUBTITLES_API_KEY"] = self.config_obj.opensubtitles_api_key
        ctk.set_appearance_mode(self.config_obj.theme_mode)
        ctk.set_default_color_theme("blue")

        self.title("Video Downloader")
        self.geometry(f"{theme.WINDOW_DEFAULT_WIDTH}x{theme.WINDOW_DEFAULT_HEIGHT}")
        self.minsize(theme.WINDOW_MIN_WIDTH, theme.WINDOW_MIN_HEIGHT)

        # State
        self.current_info: VideoInfo | None = None
        self._extract_generation: int = 0          # eski worker sonuçlarını yok say
        self.active_workers: dict[DownloadItem, DownloadWorker] = {}

        self._build_ui()

    # ------------------------------------------------------------------
    # UI inşası
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.rowconfigure(4, weight=1)
        self.columnconfigure(0, weight=1)

        # --- Header ---
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=theme.PADDING_LARGE, pady=(theme.PADDING_LARGE, 0))
        header.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Video Downloader",
            font=theme.FONT_TITLE,
        ).grid(row=0, column=0, sticky="w")

        self.settings_btn = ctk.CTkButton(
            header,
            text="⚙  Ayarlar",
            width=110,
            height=32,
            font=theme.FONT_SMALL,
            fg_color="transparent",
            border_width=1,
            command=self._open_settings,
        )
        self.settings_btn.grid(row=0, column=1, sticky="e")

        # --- URL girişi ---
        self.url_input = UrlInputFrame(self, on_fetch=self._on_fetch)
        self.url_input.grid(
            row=1, column=0, sticky="ew",
            padx=theme.PADDING_LARGE,
            pady=(theme.PADDING_MEDIUM, 0),
        )

        # --- Hata bandı (gizli) ---
        self.error_frame = ctk.CTkFrame(self, fg_color=theme.COLOR_ERROR, corner_radius=theme.CORNER_RADIUS)
        self.error_label = ctk.CTkLabel(
            self.error_frame,
            text="",
            font=theme.FONT_SMALL,
            text_color="white",
            anchor="w",
        )
        self.error_label.pack(side="left", fill="x", expand=True, padx=theme.PADDING_MEDIUM, pady=6)
        ctk.CTkButton(
            self.error_frame,
            text="✕",
            width=28,
            height=28,
            fg_color="transparent",
            hover_color="#a00000",
            command=self._hide_error,
        ).pack(side="right", padx=(0, theme.PADDING_SMALL))
        # error_frame başta grid'e konmaz; _show_error / _hide_error yönetir

        # --- Video bilgisi kartı (başta gizli) ---
        self.video_info_frame = VideoInfoFrame(self)
        # grid ile konmaz; _show_video_info ile gösterilir

        # --- Format seçici ---
        self.format_picker = FormatPickerFrame(
            self,
            on_download=self._on_download,
            default_quality=self.config_obj.default_quality,
            default_video_format=self.config_obj.default_video_format,
            default_audio_format=self.config_obj.default_audio_format,
        )
        self.format_picker.grid(
            row=3, column=0, sticky="ew",
            padx=theme.PADDING_LARGE,
            pady=(theme.PADDING_MEDIUM, 0),
        )

        # --- İndirme listesi ---
        self.download_list = DownloadList(self)
        self.download_list.grid(
            row=4, column=0, sticky="nsew",
            padx=theme.PADDING_LARGE,
            pady=theme.PADDING_MEDIUM,
        )

    # ------------------------------------------------------------------
    # Callback: URL bilgi alma
    # ------------------------------------------------------------------

    def _on_fetch(self, url: str) -> None:
        """Kullanıcı 'Bilgi Al' butonuna bastı."""
        if not self._check_cookie_cache():
            return
        self._hide_error()
        self._hide_video_info()
        self.format_picker.set_enabled(False)
        self.url_input.set_loading(True)
        self.current_info = None

        # Generation counter: eski worker tamamlanırsa sonucunu yoksay
        self._extract_generation += 1
        generation = self._extract_generation

        cookie_config = self.config_obj.get_cookie_config()

        def on_success(info: VideoInfo) -> None:
            run_on_ui(self, self._on_extract_success, info, generation)

        def on_error(exc: Exception) -> None:
            if isinstance(exc, AuthenticationRequiredError):
                run_on_ui(self, self._on_auth_required, exc)
            else:
                run_on_ui(self, self._on_extract_error, exc, generation, url)

        ExtractWorker(url, on_success=on_success, on_error=on_error, cookies=cookie_config).start()

    def _on_extract_success(self, info: VideoInfo, generation: int) -> None:
        if generation != self._extract_generation:
            return  # Eski istek, yoksay

        self.url_input.set_loading(False)
        self.current_info = info
        self._show_video_info(info)
        self.format_picker.set_enabled(True)

    def _on_extract_error(self, exc: Exception, generation: int, url: str = "") -> None:
        if generation != self._extract_generation:
            return

        self.url_input.set_loading(False)
        friendly = humanize_error(str(exc))
        self._show_error(friendly.title + ": " + friendly.message)
        logger.warning("Bilgi çekme hatası: %s", exc)

        # URL'den içerik adı çıkar — torrent alternatifi öner
        if url:
            content_info = detect_from_url(url)
            if content_info.name:
                def on_torrent_download(result: TorrentResult) -> None:
                    self._start_torrent_download(result, content_info)

                TorrentResultsDialog(
                    self,
                    content_info=content_info,
                    on_download=on_torrent_download,
                    jackett_url=self.config_obj.jackett_url,
                    jackett_key=self.config_obj.jackett_api_key,
                )
                return

        ErrorDialog(self, friendly, on_open_settings=self._open_cookies_settings)

    def _start_torrent_download(
        self,
        result: TorrentResult,
        content_info: ContentInfo,
    ) -> None:
        """Torrent indirme başlat."""
        output_dir = Path(self.config_obj.download_dir) / "torrents"
        downloader = TorrentDownloader(output_dir)

        item = DownloadItem(
            self.download_list,
            title=f"[Torrent] {result.title} {result.quality}",
            on_cancel=downloader.cancel,
        )
        self.download_list.add_item(item)

        api_key = self.config_obj.opensubtitles_api_key

        def on_progress(progress: TorrentProgress) -> None:
            run_on_ui(self, item.update_torrent_progress, progress)

        def task() -> None:
            try:
                magnet = result.magnet or ""
                torrent_url = result.torrent_url or ""

                if magnet:
                    video_path = downloader.download_magnet(magnet, on_progress)
                elif torrent_url:
                    video_path = downloader.download_torrent_file(torrent_url, on_progress)
                else:
                    raise Exception("Magnet veya torrent URL bulunamadı")

                if video_path is None:
                    raise Exception("İndirme başarısız veya iptal edildi")

                run_on_ui(self, item.set_status_text, "Altyazı aranıyor...")
                subtitles = auto_subtitle(
                    title=content_info.name,
                    video_path=video_path,
                    api_key=api_key,
                    year=content_info.year,
                    imdb_id=result.imdb_id,
                    languages=self.config_obj.subtitle_languages,
                )

                run_on_ui(self, item.mark_complete, video_path)

                if subtitles:
                    run_on_ui(
                        self, item.set_status_text,
                        f"Tamamlandi + {len(subtitles)} altyazi",
                    )
            except Exception as e:
                run_on_ui(self, item.mark_error, e)

        threading.Thread(target=task, daemon=True).start()

    def _on_auth_required(self, exc: Exception) -> None:
        """Login gerektiren video için özel yönlendirme dialog'u."""
        self.url_input.set_loading(False)

        dialog = ctk.CTkToplevel(self)
        dialog.title("Login Gerekli")
        dialog.geometry("460x260")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="🔒  Bu video login gerektiriyor",
            font=theme.FONT_SUBTITLE,
        ).pack(pady=(theme.PADDING_LARGE, theme.PADDING_MEDIUM))

        ctk.CTkLabel(
            dialog,
            text=(
                "Bu video özel, üye-only veya yaş kısıtlı.\n"
                "İndirebilmek için cookie ayarlarını yapmanız gerekiyor.\n\n"
                "Önerilen: Tarayıcınızda siteye giriş yapın,\n"
                "ardından Ayarlar → Cookies & Login sekmesini açın."
            ),
            font=theme.FONT_BODY,
            justify="center",
            wraplength=400,
        ).pack(pady=theme.PADDING_MEDIUM, padx=theme.PADDING_LARGE)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=theme.PADDING_MEDIUM)

        def open_cookies_settings() -> None:
            dialog.destroy()
            self._open_settings(focus_tab="Cookies & Login")

        ctk.CTkButton(
            btn_frame,
            text="Ayarları Aç",
            fg_color=theme.COLOR_ACCENT,
            hover_color=theme.COLOR_ACCENT_HOVER,
            command=open_cookies_settings,
        ).pack(side="left", padx=theme.PADDING_SMALL)

        ctk.CTkButton(
            btn_frame,
            text="Kapat",
            fg_color="transparent",
            border_width=1,
            command=dialog.destroy,
        ).pack(side="left", padx=theme.PADDING_SMALL)

    # ------------------------------------------------------------------
    # Callback: İndirme
    # ------------------------------------------------------------------

    def _on_download(self, quality: str, audio_only: bool, fmt: str) -> None:
        """Kullanıcı 'İndir' butonuna bastı."""
        if self.current_info is None:
            return

        # Max eş zamanlı kontrol
        active_count = sum(1 for item in self.active_workers if item.completed_path is None)
        if active_count >= self.config_obj.max_concurrent_downloads:
            self._show_error(
                f"Maksimum {self.config_obj.max_concurrent_downloads} eş zamanlı indirme sınırına ulaşıldı."
            )
            return

        output_dir = Path(self.config_obj.download_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        options = DownloadOptions(
            output_dir=output_dir,
            quality=quality,
            audio_only=audio_only,
            audio_format=fmt if audio_only else self.config_obj.default_audio_format,
            video_format=fmt if not audio_only else self.config_obj.default_video_format,
            embed_thumbnail=self.config_obj.embed_thumbnail,
            embed_metadata=self.config_obj.embed_metadata,
            embed_subtitles=self.config_obj.embed_subtitles,
            download_subtitles=self.config_obj.download_subtitles,
            subtitle_languages=self.config_obj.subtitle_languages,
            rate_limit=self.config_obj.rate_limit,
            cookies=self.config_obj.get_cookie_config(),
        )

        title = self.current_info.title or self.url_input.get_url()
        item = DownloadItem(
            self.download_list,
            title=title,
            on_cancel=lambda: self._on_cancel(item),
        )
        self.download_list.add_item(item)

        url = self.url_input.get_url() or self.current_info.url

        def on_progress(info: ProgressInfo) -> None:
            run_on_ui(self, item.update_progress, info)

        def on_complete(path: Path) -> None:
            run_on_ui(self, self._on_download_complete, item, path)

        def on_error(exc: Exception) -> None:
            run_on_ui(self, self._on_download_error, item, exc)

        worker = DownloadWorker(
            url=url,
            options=options,
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error,
        )
        self.active_workers[item] = worker
        worker.start()

    def _on_cancel(self, item: DownloadItem) -> None:
        worker = self.active_workers.get(item)
        if worker:
            worker.cancel()
        item.mark_cancelled()
        self.active_workers.pop(item, None)

    def _on_download_complete(self, item: DownloadItem, path: Path) -> None:
        item.mark_complete(path)
        self.active_workers.pop(item, None)
        logger.info("İndirme tamamlandı: %s", path)

    def _on_download_error(self, item: DownloadItem, exc: Exception) -> None:
        friendly = humanize_error(str(exc))
        item.mark_error(Exception(friendly.title))
        self.active_workers.pop(item, None)

        # Auth/cookie hatalarında detaylı dialog göster
        if friendly.category in ("auth", "cookie"):
            ErrorDialog(self, friendly, on_open_settings=self._open_cookies_settings)

        logger.warning("İndirme hatası: %s", exc)

    # ------------------------------------------------------------------
    # Ayarlar
    # ------------------------------------------------------------------

    def _open_settings(self, focus_tab: str | None = None) -> None:
        SettingsWindow(
            self,
            config=self.config_obj,
            on_save=self._on_settings_saved,
            focus_tab=focus_tab,
        )

    def _on_settings_saved(self, config: AppConfig) -> None:
        self.config_obj = config
        ctk.set_appearance_mode(config.theme_mode)
        self.format_picker.apply_defaults(
            quality=config.default_quality,
            video_format=config.default_video_format,
            audio_format=config.default_audio_format,
        )

    # ------------------------------------------------------------------
    # UI yardımcıları
    # ------------------------------------------------------------------

    def _show_video_info(self, info: VideoInfo) -> None:
        self.video_info_frame.show_info(info)
        self.video_info_frame.grid(
            row=2, column=0, sticky="ew",
            padx=theme.PADDING_LARGE,
            pady=(theme.PADDING_MEDIUM, 0),
        )

    def _hide_video_info(self) -> None:
        self.video_info_frame.grid_remove()
        self.video_info_frame.clear()

    # ------------------------------------------------------------------
    # Cookie cache kontrol
    # ------------------------------------------------------------------

    def _check_cookie_cache(self) -> bool:
        """Cache durumunu kontrol et. True → devam et, False → durdur."""
        cookie_cfg = self.config_obj.get_cookie_config()
        if cookie_cfg.mode != "browser" or not cookie_cfg.browser:
            return True

        if is_cache_valid(cookie_cfg.browser, cookie_cfg.browser_profile):
            meta = get_metadata()
            if meta and meta.is_stale():
                self._show_toast(
                    f"Cookie cache eski ({meta.age_human()}). "
                    f"Sorun yasarsan ayarlardan yenile."
                )
            return True

        # Cache yok → senkron dialog'u göster
        return self._prompt_first_sync()

    def _prompt_first_sync(self) -> bool:
        """İlk kullanım dialog'u — senkron yap mı?"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Cookie Senkronizasyonu Gerekli")
        dialog.geometry("450x250")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="Ilk Kullanim",
            font=theme.FONT_SUBTITLE,
        ).pack(pady=(20, 10))

        ctk.CTkLabel(
            dialog,
            text=(
                "Tarayicidan cookie'leri okuyup cache'leyelim.\n"
                "Bu sayede tarayici acikken de indirme yapabilirsin.\n\n"
                "Onemli: Su an tarayicinin kapali olmasi gerekiyor.\n"
                "Lutfen tarayicini kapat ve devam'a bas."
            ),
            font=theme.FONT_BODY,
            justify="center",
            wraplength=400,
        ).pack(pady=10, padx=20)

        result = {"cont": False}

        def do_sync():
            result["cont"] = True
            dialog.destroy()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=15)

        ctk.CTkButton(
            btn_frame, text="Tarayici Kapali, Devam Et",
            command=do_sync,
            fg_color=theme.COLOR_ACCENT,
            hover_color=theme.COLOR_ACCENT_HOVER,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="Iptal",
            fg_color="transparent", border_width=1,
            command=dialog.destroy,
        ).pack(side="left", padx=5)

        self.wait_window(dialog)

        if result["cont"]:
            return self._do_sync_blocking()
        return False

    def _do_sync_blocking(self) -> bool:
        """Senkronu yap, progress dialog göster."""
        cookie_cfg = self.config_obj.get_cookie_config()

        progress = ctk.CTkToplevel(self)
        progress.title("Senkronize Ediliyor")
        progress.geometry("350x120")
        progress.resizable(False, False)
        progress.transient(self)
        progress.grab_set()

        ctk.CTkLabel(
            progress, text="Cookie'ler senkronize ediliyor...",
            font=theme.FONT_BODY,
        ).pack(pady=20)

        progressbar = ctk.CTkProgressBar(progress, mode="indeterminate")
        progressbar.pack(padx=20, pady=10, fill="x")
        progressbar.start()

        result = {"success": False, "error": None}

        def task():
            try:
                sync_from_browser(cookie_cfg.browser, cookie_cfg.browser_profile)
                result["success"] = True
            except Exception as e:
                result["error"] = str(e)
            finally:
                self.after(0, progress.destroy)

        threading.Thread(target=task, daemon=True).start()
        self.wait_window(progress)

        if result["error"]:
            friendly = humanize_error(result["error"])
            ErrorDialog(self, friendly, on_open_settings=self._open_cookies_settings)

        return result["success"]

    def _show_toast(self, message: str) -> None:
        """Üstte 3 saniye görünen mini bildirim."""
        toast = ctk.CTkLabel(
            self, text=message,
            fg_color=theme.COLOR_BG_SECONDARY,
            corner_radius=8,
        )
        toast.place(relx=0.5, y=10, anchor="n")
        self.after(4000, toast.destroy)

    def _open_cookies_settings(self) -> None:
        """Ayarlar penceresini Cookies sekmesi açık olarak aç."""
        self._open_settings(focus_tab="Cookies & Login")

    def _show_error(self, message: str) -> None:
        cleaned = clean_ansi(message)
        if len(cleaned) > 120:
            cleaned = cleaned[:120] + "..."
        self.error_label.configure(text=cleaned)
        self.error_frame.grid(
            row=1, column=0, sticky="ew",  # URL input'un altında
            padx=theme.PADDING_LARGE,
            pady=(theme.PADDING_SMALL, 0),
        )
        # Otomatik gizle (8sn sonra)
        self.after(8000, self._hide_error)

    def _hide_error(self) -> None:
        self.error_frame.grid_remove()
