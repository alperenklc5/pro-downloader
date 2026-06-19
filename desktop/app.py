"""
Ana uygulama penceresi.

Tüm UI bileşenlerini birleştirir ve uygulama state'ini yönetir.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import traceback
import uuid
from pathlib import Path

import customtkinter as ctk

from core import DownloadOptions, ProgressInfo, VideoInfo
from core.cookie_cache import get_metadata, is_cache_valid, sync_from_browser
from core.error_messages import humanize_error
from core.exceptions import AuthenticationRequiredError
from core.torrent import (
    detect_from_url, ContentInfo, TorrentResult,
    TorrentDownloader, TorrentProgress,
)
from core.torrent.power_manager import prevent_sleep, allow_sleep
from desktop.config import AppConfig
from desktop.ui import theme
from desktop.ui.download_item import DownloadItem
from desktop.ui.error_dialog import ErrorDialog
from desktop.ui.log_window import LogWindow
from desktop.ui.pages import VideoPage, TorrentPage, GamePage, ActiveDownloadsPage, SettingsPage, HostingPage
from desktop.ui.sidebar import Sidebar
from desktop.ui.status_bar import StatusBar
from desktop.utils.threading_helper import run_on_ui
from desktop.workers.download_worker import DownloadWorker
from desktop.workers.extract_worker import ExtractWorker

logger = logging.getLogger(__name__)


class App(ctk.CTk):
    """Video Downloader ana penceresi."""

    def __init__(self) -> None:
        super().__init__()

        self.config_obj = AppConfig.load()
        os.environ["JACKETT_URL"] = self.config_obj.jackett_url or ""
        os.environ["JACKETT_API_KEY"] = self.config_obj.jackett_api_key or ""
        os.environ["OPENSUBTITLES_API_KEY"] = self.config_obj.opensubtitles_api_key or ""
        print(f"DEBUG Jackett URL: {os.environ.get('JACKETT_URL')}")
        print(f"DEBUG Jackett KEY: {os.environ.get('JACKETT_API_KEY')[:10] if os.environ.get('JACKETT_API_KEY') else 'BOS'}")
        ctk.set_appearance_mode("dark")          # Midnight Ocean her zaman koyu
        ctk.set_default_color_theme("blue")

        self.title("Pro Downloader")
        self.geometry(f"{theme.WINDOW_DEFAULT_WIDTH}x{theme.WINDOW_DEFAULT_HEIGHT}")
        self.minsize(theme.WINDOW_MIN_WIDTH, theme.WINDOW_MIN_HEIGHT)

        # State
        self.current_info: VideoInfo | None = None
        self._extract_generation: int = 0          # eski worker sonuçlarını yok say
        self.active_workers: dict[DownloadItem, DownloadWorker] = {}
        self._active_torrent_downloaders: list[TorrentDownloader] = []
        self.current_page: str = "video"

        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        self._build_ui()
        self.log_window = LogWindow(self)

        # Yarım kalan indirmeleri kontrol et (UI hazır olduktan sonra)
        self.after(500, self._check_pending_downloads)
        self.after(2000, self._tick_status_bar)

    # ------------------------------------------------------------------
    # UI inşası
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Ana grid: sidebar (sütun 0) + içerik (sütun 1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.configure(fg_color=theme.BG_PRIMARY)

        # --- Sol Sidebar ---
        self.sidebar = Sidebar(self, on_navigate=self._navigate)
        self.sidebar.grid(row=0, column=0, sticky="ns")

        # --- Sağ İçerik Alanı ---
        content = ctk.CTkFrame(self, fg_color=theme.BG_PRIMARY, corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        # --- Sayfalar ---
        self.pages: dict[str, ctk.CTkFrame] = {}
        self.pages["video"]    = VideoPage(content, self)
        self.pages["torrent"]  = TorrentPage(content, self)
        self.pages["game"]     = GamePage(content, self)
        self.pages["hosting"]  = HostingPage(content, self)
        self.pages["active"]   = ActiveDownloadsPage(content, self)
        self.pages["settings"] = SettingsPage(content, self)

        # VideoPage bileşenlerine kısayollar — iş mantığı değişmeden çalışır
        self.url_input      = self.pages["video"].url_input
        self.format_picker  = self.pages["video"].format_picker
        self.download_list  = self.pages["video"].download_list

        # Tüm indirmeler Aktif İndirmeler sayfasına gider
        self.active_download_list = self.pages["active"].download_list

        # Varsayılan sayfa: Video
        self.current_page = "video"
        self.pages["video"].grid(row=0, column=0, sticky="nsew")

        # --- Alt Durum Çubuğu ---
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")

    def _navigate(self, page_key: str) -> None:
        """Sidebar navigasyonu — sayfa değiştir."""
        if page_key == "log":
            self.log_window.toggle()
            return

        if self.current_page in self.pages:
            self.pages[self.current_page].grid_forget()

        if page_key in self.pages:
            self.pages[page_key].grid(row=0, column=0, sticky="nsew")
            self.current_page = page_key

    def _go_to_page(self, page_key: str) -> None:
        """Programatik sayfa geçişi — sidebar aktif durumunu da günceller."""
        self._navigate(page_key)
        self.sidebar.set_active(page_key)

    def _tick_status_bar(self) -> None:
        """Status bar'ı 2 saniyede bir güncelle."""
        active_count = sum(
            1 for item in self.active_workers if item.completed_path is None
        ) + len(self._active_torrent_downloaders)
        self.status_bar.update(active_count=active_count, total_speed=0)
        self.pages["active"].refresh_stats()
        self.after(2000, self._tick_status_bar)

    # ------------------------------------------------------------------
    # Callback: URL bilgi alma
    # ------------------------------------------------------------------

    def _on_fetch(self, url: str) -> None:
        """Kullanıcı 'Bilgi Al' butonuna bastı."""
        # Mega/Pixeldrain link kontrolü
        from core.hosting import SmartDownloader
        if url and SmartDownloader.is_supported(url):
            service = SmartDownloader.detect_service(url)
            self._log(f"{'Mega.nz' if service == 'mega' else 'Pixeldrain'} linki algılandı", "info")
            self._start_hosting_download(url)
            return

        # Düz metin (URL değil) → yt-dlp'ye göndermeden direkt torrent araması
        if url and not url.lower().startswith(("http://", "https://", "ftp://")):
            from core.torrent.detector import ContentInfo
            content_info = ContentInfo(name=url.strip(), original_url=url)
            self._open_torrent_dialog(content_info)
            return

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

        # Düz metin girişi (URL değil) → direkt torrent araması
        is_plain_text = url and not url.lower().startswith(("http://", "https://", "ftp://"))
        if is_plain_text:
            from core.torrent.detector import ContentInfo
            content_info = ContentInfo(name=url.strip(), original_url=url)
            self._open_torrent_dialog(content_info)
            return

        # URL girişi — her hata türünde detect_from_url ile içerik adı çıkar
        if url:
            content_info = detect_from_url(url)
            if content_info.name:
                self._open_torrent_dialog(content_info)
                return

        ErrorDialog(self, friendly, on_open_settings=self._open_cookies_settings)

    def _open_torrent_dialog(self, content_info: ContentInfo, show_games: bool = False) -> None:
        """Torrent veya oyun sayfasına geçip arama başlat."""
        if show_games:
            self.pages["game"].start_game_search(content_info.name)
            self._go_to_page("game")
        else:
            self.pages["torrent"].start_search(content_info)
            self._go_to_page("torrent")

    def _open_game_search(self, query: str) -> None:
        """Oyun sayfasına geçip arama başlat."""
        if not query:
            return
        self.pages["game"].start_game_search(query)
        self._go_to_page("game")

    def _start_hosting_download(self, url: str) -> None:
        """Mega/Pixeldrain indirme başlat."""
        from core.hosting import SmartDownloader
        from core.hosting.mega_downloader import DownloadProgress

        service = SmartDownloader.detect_service(url)
        if not service:
            self._log(f"[Hosting] Desteklenmeyen URL: {url}", "error")
            return

        safe_name = f"{service}_{uuid.uuid4().hex[:8]}"
        output_dir = Path(self.config_obj.download_dir) / "hosting" / safe_name
        output_dir.mkdir(parents=True, exist_ok=True)

        vps_url = getattr(self.config_obj, "api_base_url", None)
        downloader = SmartDownloader(output_dir=output_dir, vps_url=vps_url)

        item = DownloadItem(
            self.active_download_list,
            title=f"[{service.capitalize()}] İndiriliyor...",
            on_cancel=downloader.cancel,
            on_pause=downloader.pause,
            on_resume=downloader.resume,
        )
        self.active_download_list.add_item(item)
        self._go_to_page("active")

        def on_progress(progress: DownloadProgress) -> None:
            tp = TorrentProgress(
                status=progress.status,
                progress_percent=progress.percent,
                download_speed=progress.speed,
                upload_speed=0,
                seeds=0,
                peers=0,
                eta_seconds=progress.eta_seconds,
                name=progress.current_ip_source,
                downloaded_bytes=progress.downloaded_bytes,
                total_bytes=progress.total_bytes,
            )
            run_on_ui(self, item.update_torrent_progress, tp)

        def task() -> None:
            prevent_sleep()
            try:
                self._log(f"İndirme başlıyor: {url[:60]}...", "info")
                run_on_ui(self, self.log_window.show)
                result = downloader.download(
                    url,
                    progress_callback=on_progress,
                    log_callback=lambda msg: self._log(msg, "info"),
                )
                if result:
                    self._log(f"✓ İndirme tamamlandı: {result.name}", "success")
                    run_on_ui(self, item.mark_complete, result)
                else:
                    self._log("✗ İndirme başarısız", "error")
                    run_on_ui(self, item.mark_error, Exception("İndirme başarısız"))
            except Exception as e:
                self._log(f"✗ Hata: {e}", "error")
                run_on_ui(self, item.mark_error, e)
            finally:
                allow_sleep()

        threading.Thread(target=task, daemon=True).start()

    def _start_torrent_download(
        self,
        result: TorrentResult,
        content_info: ContentInfo,
    ) -> None:
        """Torrent indirme başlat."""
        safe_name = re.sub(r'[<>:"/\\|?*]', "", result.title)
        safe_name = safe_name[:40].strip()
        safe_name = f"{safe_name}_{uuid.uuid4().hex[:6]}"
        base_subdir = "games" if content_info.content_type == "game" else "torrents"
        output_dir = Path(self.config_obj.download_dir) / base_subdir / safe_name
        output_dir.mkdir(parents=True, exist_ok=True)
        downloader = TorrentDownloader(output_dir)
        self._active_torrent_downloaders.append(downloader)

        def on_subtitle_request(video_path: Path) -> None:
            """Altyazı butonu tıklandı."""

            def subtitle_task():
                from core.torrent.subdl import auto_subtitle_subdl, parse_video_filename

                # Video dosya adından parse et
                parsed = parse_video_filename(video_path.name) if video_path else {}
                clean_title = parsed.get("title") or result.title
                season = parsed.get("season") or content_info.season
                episode = parsed.get("episode") or content_info.episode
                content_type = parsed.get("content_type", "movie")

                self._log(f"Altyazı aranıyor: {clean_title} S{season}E{episode}", "info")
                if video_path:
                    run_on_ui(self, self.log_window.show)

                subtitles = auto_subtitle_subdl(
                    title=clean_title,
                    video_path=video_path,
                    api_key=self.config_obj.subdl_api_key,
                    imdb_id=result.imdb_id,
                    season=season,
                    episode=episode,
                    content_type=content_type,
                    languages=["TR", "EN"],
                    log_callback=lambda msg: self._log(msg, "info"),
                    opensubtitles_api_key=self.config_obj.opensubtitles_api_key,
                )

                found = len(subtitles) > 0
                run_on_ui(self, item.set_subtitle_result, found, len(subtitles))

                if found:
                    self._log(f"\u2713 {len(subtitles)} altyazı indirildi", "success")
                else:
                    self._log("\u2717 Altyazı bulunamadı", "warning")

            threading.Thread(target=subtitle_task, daemon=True).start()

        item = DownloadItem(
            self.active_download_list,
            title=f"[Torrent] {result.title} {result.quality}",
            on_cancel=downloader.cancel,
            on_subtitle=on_subtitle_request,
            on_pause=downloader.pause,
            on_resume=downloader.resume,
        )
        self.active_download_list.add_item(item)
        self._go_to_page("active")

        def on_progress(progress: TorrentProgress) -> None:
            run_on_ui(self, item.update_torrent_progress, progress)

        def task() -> None:
            prevent_sleep()
            try:
                if downloader.load_resume_json():
                    self._log(f"⏩ Kaldığı yerden devam ediliyor: {result.title}", "info")
                else:
                    self._log(f"▶ İndirme başlıyor: {result.title}", "info")
                video_path = downloader.download(
                    magnet=result.magnet or "",
                    torrent_url=result.torrent_url or "",
                    progress_callback=on_progress,
                )

                # None dönerse önce iptal kontrolü yap
                if video_path is None:
                    if downloader._cancel_flag:
                        self._log("İndirme iptal edildi", "warning")
                        run_on_ui(self, item.mark_cancelled)
                        return

                    # İptal değil — output_dir içinde en büyük video dosyasını manuel ara
                    logger.warning("downloader.download() None döndü, output_dir taranıyor...")
                    found_videos = []
                    for ext in [".mkv", ".mp4", ".avi", ".mov"]:
                        for f in output_dir.rglob("*"):
                            try:
                                if f.is_file() and f.suffix.lower() == ext:
                                    found_videos.append(f)
                            except Exception:
                                continue
                    video_path = max(found_videos, key=lambda f: f.stat().st_size) if found_videos else None

                if video_path is None:
                    raise Exception("İndirme başarısız")

                self._log(f"\u2713 İndirme tamamlandı: {video_path.name}", "success")
                run_on_ui(self, item.mark_complete, video_path)

            except Exception as e:
                self._log(f"\u2717 İndirme hatası: {e}", "error")
                logger.error(traceback.format_exc())
                run_on_ui(self, item.mark_error, e)
            finally:
                allow_sleep()
                try:
                    self._active_torrent_downloaders.remove(downloader)
                except ValueError:
                    pass

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
            self.active_download_list,
            title=title,
            on_cancel=lambda: self._on_cancel(item),
        )
        self.active_download_list.add_item(item)
        self._go_to_page("active")

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
    # Log
    # ------------------------------------------------------------------

    def _log(self, message: str, level: str = "info") -> None:
        """Log penceresine ve Python logger'a mesaj yaz."""
        log_level = {
            "info": logging.INFO,
            "success": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
        }.get(level, logging.INFO)
        logger.log(log_level, message)
        if hasattr(self, "log_window"):
            self.after(0, lambda: self.log_window.log(message, level))

    # ------------------------------------------------------------------
    # Ayarlar
    # ------------------------------------------------------------------

    def _open_settings(self, focus_tab: str | None = None) -> None:
        """Ayarlar sayfasına geç (popup açmaz)."""
        self.pages["settings"].load_config(self.config_obj)
        if focus_tab:
            self.pages["settings"].set_focus_tab(focus_tab)
        self._go_to_page("settings")

    def _on_settings_saved(self, config: AppConfig) -> None:
        self.config_obj = config
        ctk.set_appearance_mode(config.theme_mode)
        self.format_picker.apply_defaults(
            quality=config.default_quality,
            video_format=config.default_video_format,
            audio_format=config.default_audio_format,
        )
        # Jackett/API key env var'larını güncelle
        os.environ["JACKETT_URL"] = config.jackett_url or ""
        os.environ["JACKETT_API_KEY"] = config.jackett_api_key or ""
        os.environ["OPENSUBTITLES_API_KEY"] = config.opensubtitles_api_key or ""

    # ------------------------------------------------------------------
    # UI yardımcıları
    # ------------------------------------------------------------------

    def _show_video_info(self, info: VideoInfo) -> None:
        self.pages["video"].show_video_info(info)

    def _hide_video_info(self) -> None:
        self.pages["video"].hide_video_info()

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
        self.pages["video"].show_error(message)

    def _hide_error(self) -> None:
        self.pages["video"].hide_error()

    # ------------------------------------------------------------------
    # Uygulama kapatma & resume
    # ------------------------------------------------------------------

    def _on_closing(self) -> None:
        """Uygulama kapanırken aktif torrent indirmelerini duraklat (resume kaydeder)."""
        for dl in list(self._active_torrent_downloaders):
            try:
                dl.pause()
            except Exception:
                pass
        self.destroy()

    def _check_pending_downloads(self) -> None:
        """Uygulama açılınca yarım kalan torrent indirmelerini bildir."""
        pending = []
        for base in ("torrents", "games"):
            base_dir = Path(self.config_obj.download_dir) / base
            if not base_dir.exists():
                continue
            for d in base_dir.iterdir():
                if d.is_dir() and (d / ".resume_data").exists():
                    pending.append(d)

        if not pending:
            return

        self._log(
            f"⚠ {len(pending)} yarım kalan indirme bulundu. "
            "Aynı torrent'i tekrar seçerek kaldığı yerden devam edebilirsiniz.",
            "warning",
        )
