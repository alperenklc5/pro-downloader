"""Ayarlar sayfası — ana içerik alanında gösterilir, ayrı pencere yok."""
from __future__ import annotations

import threading
import tkinter.filedialog as fd

import customtkinter as ctk

from core.auth import SUPPORTED_BROWSERS, detect_installed_browsers, list_browser_profiles
from core.cookie_cache import clear_cache, get_metadata, sync_from_browser
from core.exceptions import CookieError
from desktop.config import AppConfig
from desktop.ui import theme

QUALITY_OPTIONS = ["best", "1080p", "720p", "480p", "360p", "240p"]
VIDEO_FORMAT_OPTIONS = ["mp4", "mkv", "webm"]
AUDIO_FORMAT_OPTIONS = ["mp3", "m4a", "opus"]
THEME_OPTIONS = ["dark", "light", "system"]


class SettingsPage(ctk.CTkFrame):
    """Ayarlar sayfası — sekmeli, popup yok."""

    def __init__(self, master: ctk.CTkBaseClass, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.config = app.config_obj
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self._build()

    # ------------------------------------------------------------------
    # Dışarıdan çağrılan API
    # ------------------------------------------------------------------

    def load_config(self, config: AppConfig) -> None:
        """Sayfaya gelindiğinde çağrılır — formu güncel config ile doldurur."""
        self.config = config
        self._dir_var.set(config.download_dir)
        self._concurrent_var.set(str(config.max_concurrent_downloads))
        self._theme_var.set(config.theme_mode)
        self._quality_var.set(config.default_quality)
        self._vfmt_var.set(config.default_video_format)
        self._afmt_var.set(config.default_audio_format)
        self._embed_thumb.set(config.embed_thumbnail)
        self._embed_meta.set(config.embed_metadata)
        self._embed_subs.set(config.embed_subtitles)
        self._dl_subs.set(config.download_subtitles)
        self._rate_var.set(config.rate_limit or "")
        self._cookie_mode_var.set(config.cookies_mode)
        self._file_path_var.set(config.cookies_file_path or "")
        self._jackett_url_var.set(config.jackett_url or "")
        self._jackett_key_var.set(config.jackett_api_key or "")
        self._os_key_var.set(config.opensubtitles_api_key or "")
        self._tmdb_key_var.set(config.tmdb_api_key or "")
        self._subdl_key_var.set(config.subdl_api_key or "")
        # Tarayıcı
        initial_browser = config.cookies_browser
        installed = detect_installed_browsers()
        if initial_browser and initial_browser in installed:
            self._browser_var.set(initial_browser)
            self._on_browser_change(initial_browser)
        elif installed:
            self._browser_var.set(installed[0])
        saved_profile = config.cookies_browser_profile
        self._profile_var.set(
            saved_profile if saved_profile and saved_profile != "Default"
            else "Otomatik (önerilen)"
        )
        self._update_cookie_ui()
        self._update_cache_status()
        self._save_status_label.configure(text="")

    def set_focus_tab(self, tab_name: str) -> None:
        """Belirtilen sekmeye odaklan."""
        try:
            self.tabs.set(tab_name)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI inşası
    # ------------------------------------------------------------------

    def _build(self) -> None:
        # ── Başlık ──────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(
            row=0, column=0, sticky="ew",
            padx=theme.PADDING_XL,
            pady=(theme.PADDING_XL, theme.PADDING_MEDIUM),
        )
        ctk.CTkLabel(
            header,
            text="⚙  Ayarlar",
            font=theme.FONT_TITLE,
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        # ── Sekmeli içerik ───────────────────────────────────────────────
        self.tabs = ctk.CTkTabview(
            self,
            corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.BG_SECONDARY,
            segmented_button_fg_color=theme.BG_TERTIARY,
            segmented_button_selected_color=theme.ACCENT_BLUE,
            segmented_button_selected_hover_color=theme.ACCENT_BLUE_HOVER,
            segmented_button_unselected_hover_color=theme.BG_ELEVATED,
        )
        self.tabs.grid(
            row=1, column=0, sticky="nsew",
            padx=theme.PADDING_XL,
            pady=(0, 0),
        )
        self.tabs.add("Genel")
        self.tabs.add("İndirme")
        self.tabs.add("Cookies & Login")
        self.tabs.add("Torrent & Altyazı")

        self._build_general_tab(self.tabs.tab("Genel"))
        self._build_download_tab(self.tabs.tab("İndirme"))
        self._build_cookies_tab(self.tabs.tab("Cookies & Login"))
        self._build_torrent_tab(self.tabs.tab("Torrent & Altyazı"))

        # ── Alt buton çubuğu ─────────────────────────────────────────────
        btn_bar = ctk.CTkFrame(
            self,
            fg_color=theme.BG_SECONDARY,
            corner_radius=0,
            height=52,
        )
        btn_bar.grid(row=2, column=0, sticky="ew", padx=theme.PADDING_XL)
        btn_bar.pack_propagate(False)

        inner = ctk.CTkFrame(btn_bar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=theme.PADDING_LARGE, pady=theme.PADDING_SMALL)

        self._save_status_label = ctk.CTkLabel(
            inner,
            text="",
            font=theme.FONT_SMALL,
            text_color=theme.ACCENT_GREEN,
        )
        self._save_status_label.pack(side="left")

        ctk.CTkButton(
            inner,
            text="💾  Kaydet",
            width=120,
            height=36,
            font=theme.FONT_BODY_BOLD,
            fg_color=theme.ACCENT_BLUE,
            hover_color=theme.ACCENT_BLUE_HOVER,
            corner_radius=theme.CORNER_RADIUS,
            command=self._save,
        ).pack(side="right")

    # ------------------------------------------------------------------
    # Genel sekmesi
    # ------------------------------------------------------------------

    def _build_general_tab(self, parent: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(parent, corner_radius=0, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        scroll.columnconfigure(1, weight=1)
        row = 0

        self._label(scroll, "İndirme Klasörü", row); row += 1
        self._dir_var = ctk.StringVar(value=self.config.download_dir)
        ctk.CTkEntry(scroll, textvariable=self._dir_var, font=theme.FONT_SMALL).grid(
            row=row, column=0, columnspan=2, sticky="ew",
            padx=theme.PADDING_MEDIUM, pady=(0, 4),
        ); row += 1
        ctk.CTkButton(scroll, text="Gözat…", width=100, command=self._browse_dir).grid(
            row=row, column=0, sticky="w",
            padx=theme.PADDING_MEDIUM, pady=(0, theme.PADDING_MEDIUM),
        ); row += 1

        self._label(scroll, "Maksimum Eş Zamanlı İndirme", row); row += 1
        self._concurrent_var = ctk.StringVar(value=str(self.config.max_concurrent_downloads))
        ctk.CTkOptionMenu(
            scroll, variable=self._concurrent_var,
            values=["1", "2", "3", "4", "5"],
            font=theme.FONT_BODY, width=80,
        ).grid(row=row, column=0, columnspan=2, sticky="w",
               padx=theme.PADDING_MEDIUM, pady=(0, theme.PADDING_MEDIUM)); row += 1

        self._label(scroll, "Tema", row); row += 1
        self._theme_var = ctk.StringVar(value=self.config.theme_mode)
        ctk.CTkOptionMenu(
            scroll, variable=self._theme_var,
            values=THEME_OPTIONS, font=theme.FONT_BODY,
        ).grid(row=row, column=0, columnspan=2, sticky="w",
               padx=theme.PADDING_MEDIUM, pady=(0, theme.PADDING_MEDIUM)); row += 1

    # ------------------------------------------------------------------
    # İndirme sekmesi
    # ------------------------------------------------------------------

    def _build_download_tab(self, parent: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(parent, corner_radius=0, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        scroll.columnconfigure(1, weight=1)
        row = 0

        self._label(scroll, "Varsayılan Kalite", row); row += 1
        self._quality_var = ctk.StringVar(value=self.config.default_quality)
        ctk.CTkOptionMenu(
            scroll, variable=self._quality_var,
            values=QUALITY_OPTIONS, font=theme.FONT_BODY,
        ).grid(row=row, column=0, columnspan=2, sticky="w",
               padx=theme.PADDING_MEDIUM, pady=(0, theme.PADDING_MEDIUM)); row += 1

        self._label(scroll, "Varsayılan Video Formatı", row); row += 1
        self._vfmt_var = ctk.StringVar(value=self.config.default_video_format)
        ctk.CTkOptionMenu(
            scroll, variable=self._vfmt_var,
            values=VIDEO_FORMAT_OPTIONS, font=theme.FONT_BODY,
        ).grid(row=row, column=0, columnspan=2, sticky="w",
               padx=theme.PADDING_MEDIUM, pady=(0, theme.PADDING_MEDIUM)); row += 1

        self._label(scroll, "Varsayılan Ses Formatı", row); row += 1
        self._afmt_var = ctk.StringVar(value=self.config.default_audio_format)
        ctk.CTkOptionMenu(
            scroll, variable=self._afmt_var,
            values=AUDIO_FORMAT_OPTIONS, font=theme.FONT_BODY,
        ).grid(row=row, column=0, columnspan=2, sticky="w",
               padx=theme.PADDING_MEDIUM, pady=(0, theme.PADDING_MEDIUM)); row += 1

        self._label(scroll, "Gömme Seçenekleri", row); row += 1
        self._embed_thumb = self._checkbox(scroll, "Thumbnail göm", self.config.embed_thumbnail, row); row += 1
        self._embed_meta  = self._checkbox(scroll, "Metadata göm (başlık, sanatçı)", self.config.embed_metadata, row); row += 1
        self._embed_subs  = self._checkbox(scroll, "Altyazı göm (mp4 gerektirir)", self.config.embed_subtitles, row); row += 1
        self._dl_subs     = self._checkbox(scroll, "Altyazı dosyası indir (.srt)", self.config.download_subtitles, row); row += 1

        self._label(scroll, "Hız Limiti (örn: 1M, 500K — boş = limitsiz)", row); row += 1
        self._rate_var = ctk.StringVar(value=self.config.rate_limit or "")
        ctk.CTkEntry(
            scroll, textvariable=self._rate_var,
            font=theme.FONT_BODY, width=140,
        ).grid(row=row, column=0, columnspan=2, sticky="w",
               padx=theme.PADDING_MEDIUM, pady=(0, theme.PADDING_MEDIUM)); row += 1

    # ------------------------------------------------------------------
    # Torrent & Altyazı sekmesi
    # ------------------------------------------------------------------

    def _build_torrent_tab(self, parent: ctk.CTkFrame) -> None:
        pad = theme.PADDING_MEDIUM
        scroll = ctk.CTkScrollableFrame(parent, corner_radius=0, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(scroll, text="Jackett Ayarları", font=theme.FONT_SUBTITLE, anchor="w").pack(
            anchor="w", padx=pad, pady=(pad, 5)
        )
        ctk.CTkLabel(
            scroll,
            text=(
                "Jackett, BTK engelini aşarak 500+ torrent sitesini sorgular.\n"
                "VPS'te çalışır; URL ve API key'i buraya girin."
            ),
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED, justify="left",
        ).pack(anchor="w", padx=pad, pady=(0, 8))

        ctk.CTkLabel(scroll, text="Jackett URL:", font=theme.FONT_BODY, anchor="w").pack(
            anchor="w", padx=pad, pady=(0, 2)
        )
        self._jackett_url_var = ctk.StringVar(value=self.config.jackett_url or "")
        ctk.CTkEntry(
            scroll, textvariable=self._jackett_url_var,
            placeholder_text="http://your-vps:9117", font=theme.FONT_BODY,
        ).pack(fill="x", padx=pad, pady=(0, 8))

        ctk.CTkLabel(scroll, text="Jackett API Key:", font=theme.FONT_BODY, anchor="w").pack(
            anchor="w", padx=pad, pady=(0, 2)
        )
        self._jackett_key_var = ctk.StringVar(value=self.config.jackett_api_key or "")
        ctk.CTkEntry(
            scroll, textvariable=self._jackett_key_var,
            placeholder_text="Jackett API key…", font=theme.FONT_BODY, show="*",
        ).pack(fill="x", padx=pad, pady=(0, 4))

        ctk.CTkFrame(scroll, height=1, fg_color=theme.BORDER_SUBTLE).pack(fill="x", padx=pad, pady=12)

        ctk.CTkLabel(scroll, text="Altyazı Ayarları", font=theme.FONT_SUBTITLE, anchor="w").pack(
            anchor="w", padx=pad, pady=(0, 5)
        )

        ctk.CTkLabel(scroll, text="OpenSubtitles API Key:", font=theme.FONT_BODY, anchor="w").pack(
            anchor="w", padx=pad, pady=(0, 2)
        )
        self._os_key_var = ctk.StringVar(value=self.config.opensubtitles_api_key or "")
        ctk.CTkEntry(
            scroll, textvariable=self._os_key_var,
            placeholder_text="OpenSubtitles API key…", font=theme.FONT_BODY, show="*",
        ).pack(fill="x", padx=pad, pady=(0, 4))
        ctk.CTkLabel(
            scroll, text="opensubtitles.com/en/consumers — ücretsiz",
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=pad, pady=(0, theme.PADDING_LARGE))

        ctk.CTkLabel(scroll, text="TMDB API Key:", font=theme.FONT_BODY, anchor="w").pack(
            anchor="w", padx=pad, pady=(0, 2)
        )
        self._tmdb_key_var = ctk.StringVar(value=self.config.tmdb_api_key or "")
        ctk.CTkEntry(
            scroll, textvariable=self._tmdb_key_var,
            placeholder_text="TMDB API key…", font=theme.FONT_BODY, show="*",
        ).pack(fill="x", padx=pad, pady=(0, 4))
        ctk.CTkLabel(
            scroll, text="themoviedb.org/settings/api — ücretsiz",
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=pad, pady=(0, pad))

        ctk.CTkLabel(scroll, text="Subdl API Key:", font=theme.FONT_BODY, anchor="w").pack(
            anchor="w", padx=pad, pady=(0, 2)
        )
        self._subdl_key_var = ctk.StringVar(value=self.config.subdl_api_key or "")
        ctk.CTkEntry(
            scroll, textvariable=self._subdl_key_var,
            placeholder_text="Subdl API key…", font=theme.FONT_BODY, show="*",
        ).pack(fill="x", padx=pad, pady=(0, 4))
        ctk.CTkLabel(
            scroll, text="subdl.com — ücretsiz. OpenSubtitles'ta Türkçe bulunamazsa kullanılır.",
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=pad, pady=(0, pad))

    # ------------------------------------------------------------------
    # Cookies & Login sekmesi
    # ------------------------------------------------------------------

    def _build_cookies_tab(self, parent: ctk.CTkFrame) -> None:
        pad = theme.PADDING_MEDIUM

        ctk.CTkLabel(
            parent,
            text=(
                "Login gerektiren videoları (özel Twitter/X, Instagram,\n"
                "üye-only YouTube vb.) indirebilmek için cookie ayarlayın."
            ),
            font=theme.FONT_SMALL,
            text_color=theme.TEXT_MUTED,
            justify="left",
        ).pack(anchor="w", padx=pad, pady=(pad, theme.PADDING_LARGE))

        self._cookie_mode_var = ctk.StringVar(value=self.config.cookies_mode)

        ctk.CTkRadioButton(
            parent, text="Cookie kullanma",
            variable=self._cookie_mode_var, value="none",
            font=theme.FONT_BODY, command=self._update_cookie_ui,
        ).pack(anchor="w", padx=pad, pady=(0, theme.PADDING_SMALL))

        ctk.CTkRadioButton(
            parent, text="Tarayıcıdan otomatik oku  (Önerilen)",
            variable=self._cookie_mode_var, value="browser",
            font=theme.FONT_BODY, command=self._update_cookie_ui,
        ).pack(anchor="w", padx=pad, pady=(0, theme.PADDING_SMALL))

        # Tarayıcı seçim alanı
        self._browser_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._browser_frame.pack(anchor="w", padx=pad * 3, fill="x")
        self._browser_frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(self._browser_frame, text="Tarayıcı:", font=theme.FONT_BODY).grid(
            row=0, column=0, sticky="w", padx=(0, pad), pady=2
        )
        installed = detect_installed_browsers()
        browser_options = installed if installed else ["Tarayıcı bulunamadı"]

        self._browser_var = ctk.StringVar()
        self._browser_menu = ctk.CTkOptionMenu(
            self._browser_frame, variable=self._browser_var,
            values=browser_options, font=theme.FONT_BODY,
            command=self._on_browser_change,
        )
        self._browser_menu.grid(row=0, column=1, sticky="ew", pady=2)

        initial_browser = self.config.cookies_browser
        if initial_browser and initial_browser in browser_options:
            self._browser_var.set(initial_browser)
        elif installed:
            self._browser_var.set(installed[0])
        else:
            self._browser_var.set(browser_options[0])

        ctk.CTkLabel(self._browser_frame, text="Profil:", font=theme.FONT_BODY).grid(
            row=1, column=0, sticky="w", padx=(0, pad), pady=2
        )
        saved_profile = self.config.cookies_browser_profile
        self._profile_var = ctk.StringVar(
            value=saved_profile if saved_profile and saved_profile != "Default"
            else "Otomatik (önerilen)"
        )
        self._profile_menu = ctk.CTkOptionMenu(
            self._browser_frame, variable=self._profile_var,
            values=["Otomatik (önerilen)"], font=theme.FONT_BODY,
        )
        self._profile_menu.grid(row=1, column=1, sticky="ew", pady=2)
        self._on_browser_change(self._browser_var.get())

        # Cookie cache bölümü
        self._build_cache_section(parent)

        # Manuel dosya
        ctk.CTkRadioButton(
            parent, text="Manuel cookies.txt dosyası",
            variable=self._cookie_mode_var, value="file",
            font=theme.FONT_BODY, command=self._update_cookie_ui,
        ).pack(anchor="w", padx=pad, pady=(0, theme.PADDING_SMALL))

        self._file_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._file_frame.pack(anchor="w", padx=pad * 3, fill="x")

        self._file_path_var = ctk.StringVar(value=self.config.cookies_file_path or "")
        self._file_entry = ctk.CTkEntry(
            self._file_frame, textvariable=self._file_path_var,
            placeholder_text="cookies.txt dosyasını seçin…", font=theme.FONT_BODY,
        )
        self._file_entry.pack(side="left", fill="x", expand=True, padx=(0, theme.PADDING_SMALL))

        self._browse_cookie_btn = ctk.CTkButton(
            self._file_frame, text="Gözat", width=80, command=self._browse_cookie_file,
        )
        self._browse_cookie_btn.pack(side="left")

        ctk.CTkLabel(
            parent,
            text='ℹ  "Get cookies.txt LOCALLY" Chrome eklentisiyle siteye giriş yapıp dışa aktar.',
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED, justify="left",
        ).pack(anchor="w", padx=pad * 3, pady=(theme.PADDING_SMALL, 0))

        self._update_cookie_ui()

    def _build_cache_section(self, parent: ctk.CTkFrame) -> None:
        pad = theme.PADDING_MEDIUM
        self._cache_frame = ctk.CTkFrame(
            parent,
            fg_color=theme.BG_TERTIARY,
            corner_radius=theme.CORNER_RADIUS,
        )
        self._cache_frame.pack(anchor="w", padx=pad * 3, pady=(theme.PADDING_SMALL, 15), fill="x")

        ctk.CTkLabel(
            self._cache_frame, text="Cookie Cache",
            font=theme.FONT_SUBTITLE, anchor="w",
        ).pack(anchor="w", padx=10, pady=(10, 5))

        self._cache_status_label = ctk.CTkLabel(
            self._cache_frame, text="",
            font=theme.FONT_BODY, anchor="w", justify="left",
        )
        self._cache_status_label.pack(anchor="w", padx=10, pady=2)

        btn_frame = ctk.CTkFrame(self._cache_frame, fg_color="transparent")
        btn_frame.pack(anchor="w", padx=10, pady=10)

        self._sync_btn = ctk.CTkButton(
            btn_frame, text="Senkronize Et", command=self._sync_cookies,
            fg_color=theme.ACCENT_BLUE, hover_color=theme.ACCENT_BLUE_HOVER, width=160,
        )
        self._sync_btn.pack(side="left", padx=(0, 5))

        ctk.CTkButton(
            btn_frame, text="Cache'i Temizle", command=self._clear_cookie_cache,
            fg_color="transparent", border_width=1,
            text_color=theme.TEXT_MUTED, border_color=theme.TEXT_MUTED, width=130,
        ).pack(side="left", padx=5)

        ctk.CTkLabel(
            self._cache_frame,
            text=(
                "Cache sayesinde senkronizasyondan sonra tarayıcı açıkken\n"
                "de indirme yapabilirsiniz. 7 günden eski cache yenilenmelidir."
            ),
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED, anchor="w", justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 10))

        self._update_cache_status()

    # ------------------------------------------------------------------
    # Cookie cache helpers
    # ------------------------------------------------------------------

    def _update_cache_status(self) -> None:
        meta = get_metadata()
        if meta is None:
            self._cache_status_label.configure(
                text="Henüz senkronize edilmedi", text_color=theme.ACCENT_ORANGE,
            )
        elif meta.is_stale():
            self._cache_status_label.configure(
                text=(
                    f"Eski senkron (>7 gün): {meta.age_human()}\n"
                    f"  Tarayıcı: {meta.browser} / {meta.profile or 'Default'}\n"
                    f"  Cookie sayısı: {meta.cookie_count}"
                ),
                text_color=theme.ACCENT_ORANGE,
            )
        else:
            self._cache_status_label.configure(
                text=(
                    f"Senkronize edildi: {meta.age_human()}\n"
                    f"  Tarayıcı: {meta.browser} / {meta.profile or 'Default'}\n"
                    f"  Cookie sayısı: {meta.cookie_count}"
                ),
                text_color=theme.ACCENT_GREEN,
            )

    def _sync_cookies(self) -> None:
        browser = self._browser_var.get()
        profile = self._profile_var.get()
        if profile in ("Otomatik (önerilen)", "Default", ""):
            profile = None
        if browser not in SUPPORTED_BROWSERS:
            return
        self._sync_btn.configure(state="disabled", text="Senkronize ediliyor…")
        self._cache_status_label.configure(
            text="Tarayıcıdan cookie'ler okunuyor…", text_color=theme.TEXT_MUTED,
        )

        def task():
            try:
                meta = sync_from_browser(browser, profile)
                self.after(0, lambda: self._on_sync_success(meta))
            except CookieError as e:
                self.after(0, lambda: self._on_sync_error(str(e)))
            except Exception as e:
                self.after(0, lambda: self._on_sync_error(f"Beklenmeyen hata: {e}"))

        threading.Thread(target=task, daemon=True).start()

    def _on_sync_success(self, meta) -> None:
        self._sync_btn.configure(state="normal", text="Senkronize Et")
        self._update_cache_status()

    def _on_sync_error(self, error_msg: str) -> None:
        self._sync_btn.configure(state="normal", text="Senkronize Et")
        self._cache_status_label.configure(
            text=f"Hata: {error_msg}", text_color=theme.ACCENT_RED,
        )

    def _clear_cookie_cache(self) -> None:
        clear_cache()
        self._update_cache_status()

    # ------------------------------------------------------------------
    # Cookie UI helpers
    # ------------------------------------------------------------------

    def _update_cookie_ui(self) -> None:
        mode = self._cookie_mode_var.get()
        browser_state = "normal" if mode == "browser" else "disabled"
        for widget in self._browser_frame.winfo_children():
            try:
                widget.configure(state=browser_state)
            except Exception:
                pass
        file_state = "normal" if mode == "file" else "disabled"
        try:
            self._file_entry.configure(state=file_state)
            self._browse_cookie_btn.configure(state=file_state)
        except Exception:
            pass

    def _on_browser_change(self, browser: str) -> None:
        if browser in SUPPORTED_BROWSERS:
            try:
                profiles = list_browser_profiles(browser)
                display_profiles = ["Otomatik (önerilen)"] + profiles
                self._profile_menu.configure(values=display_profiles)
                current = self._profile_var.get()
                if current in profiles:
                    self._profile_menu.set(current)
                else:
                    self._profile_menu.set("Otomatik (önerilen)")
                    self._profile_var.set("Otomatik (önerilen)")
            except Exception:
                self._profile_menu.configure(values=["Otomatik (önerilen)"])
                self._profile_menu.set("Otomatik (önerilen)")

    def _browse_cookie_file(self) -> None:
        path = fd.askopenfilename(
            title="cookies.txt seçin",
            filetypes=[("Cookie dosyaları", "*.txt"), ("Tüm dosyalar", "*.*")],
        )
        if path:
            self._file_path_var.set(path)

    def _browse_dir(self) -> None:
        directory = fd.askdirectory(
            title="İndirme klasörü seç",
            initialdir=self._dir_var.get(),
        )
        if directory:
            self._dir_var.set(directory)

    # ------------------------------------------------------------------
    # Kaydet
    # ------------------------------------------------------------------

    def _save(self) -> None:
        self.config.download_dir = self._dir_var.get()
        self.config.max_concurrent_downloads = int(self._concurrent_var.get())
        self.config.theme_mode = self._theme_var.get()  # type: ignore[assignment]
        self.config.default_quality = self._quality_var.get()
        self.config.default_video_format = self._vfmt_var.get()
        self.config.default_audio_format = self._afmt_var.get()
        self.config.embed_thumbnail = self._embed_thumb.get()
        self.config.embed_metadata = self._embed_meta.get()
        self.config.embed_subtitles = self._embed_subs.get()
        self.config.download_subtitles = self._dl_subs.get()
        self.config.rate_limit = self._rate_var.get().strip() or None

        mode = self._cookie_mode_var.get()
        self.config.cookies_mode = mode  # type: ignore[assignment]
        if mode == "browser":
            self.config.cookies_browser = self._browser_var.get()
            profile = self._profile_var.get()
            self.config.cookies_browser_profile = (
                None if profile in ("Otomatik (önerilen)", "Default") else profile
            )
            self.config.cookies_file_path = None
        elif mode == "file":
            self.config.cookies_file_path = self._file_path_var.get() or None
            self.config.cookies_browser = None
            self.config.cookies_browser_profile = None
        else:
            self.config.cookies_browser = None
            self.config.cookies_browser_profile = None
            self.config.cookies_file_path = None

        self.config.opensubtitles_api_key = self._os_key_var.get().strip()
        self.config.tmdb_api_key = self._tmdb_key_var.get().strip()
        self.config.jackett_url = self._jackett_url_var.get().strip()
        self.config.jackett_api_key = self._jackett_key_var.get().strip()
        self.config.subdl_api_key = self._subdl_key_var.get().strip()

        self.config.save()
        self.app._on_settings_saved(self.config)
        self._save_status_label.configure(text="✓  Kaydedildi")
        self.after(3000, lambda: self._save_status_label.configure(text=""))

    # ------------------------------------------------------------------
    # Yardımcılar
    # ------------------------------------------------------------------

    def _label(self, parent: ctk.CTkScrollableFrame, text: str, row: int) -> None:
        ctk.CTkLabel(
            parent, text=text,
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED, anchor="w",
        ).grid(
            row=row, column=0, columnspan=2,
            sticky="w", padx=theme.PADDING_MEDIUM,
            pady=(theme.PADDING_MEDIUM, 2),
        )

    def _checkbox(
        self,
        parent: ctk.CTkScrollableFrame,
        text: str,
        initial: bool,
        row: int,
    ) -> ctk.BooleanVar:
        var = ctk.BooleanVar(value=initial)
        ctk.CTkCheckBox(parent, text=text, variable=var, font=theme.FONT_BODY).grid(
            row=row, column=0, columnspan=2,
            sticky="w", padx=theme.PADDING_MEDIUM, pady=2,
        )
        return var
