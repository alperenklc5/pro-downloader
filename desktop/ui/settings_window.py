"""Ayarlar penceresi — üç sekme: Genel, İndirme, Cookies & Login."""

from __future__ import annotations

import threading
import tkinter.filedialog as fd
from typing import Callable

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


class SettingsWindow(ctk.CTkToplevel):
    """Kullanıcı ayarlarını düzenleme penceresi (sekmeli)."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        config: AppConfig,
        on_save: Callable[[AppConfig], None],
        focus_tab: str | None = None,
    ) -> None:
        """
        Args:
            master: Ana pencere.
            config: Mevcut ayar nesnesi.
            on_save: Kaydet butonuna basılınca çağrılır.
            focus_tab: Açılışta odaklanılacak sekme adı (opsiyonel).
        """
        super().__init__(master)
        self.config = config
        self.on_save = on_save

        self.title("Ayarlar")
        self.geometry("600x560")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self._build(focus_tab)

    def _build(self, focus_tab: str | None) -> None:
        pad = theme.PADDING_MEDIUM

        # Sekme görünümü
        self.tabs = ctk.CTkTabview(self, corner_radius=theme.CORNER_RADIUS)
        self.tabs.pack(fill="both", expand=True, padx=pad, pady=(pad, 0))

        self.tabs.add("Genel")
        self.tabs.add("İndirme")
        self.tabs.add("Cookies & Login")
        self.tabs.add("Torrent & Altyazı")

        self._build_general_tab(self.tabs.tab("Genel"))
        self._build_download_tab(self.tabs.tab("İndirme"))
        self._build_cookies_tab(self.tabs.tab("Cookies & Login"))
        self._build_torrent_tab(self.tabs.tab("Torrent & Altyazı"))

        if focus_tab:
            try:
                self.tabs.set(focus_tab)
            except Exception:
                pass

        # Butonlar
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=pad, pady=pad)

        ctk.CTkButton(
            btn_frame, text="İptal", width=100,
            fg_color="transparent", border_width=1,
            command=self.destroy,
        ).pack(side="right", padx=(pad, 0))

        ctk.CTkButton(
            btn_frame, text="Kaydet", width=100,
            fg_color=theme.COLOR_ACCENT,
            hover_color=theme.COLOR_ACCENT_HOVER,
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

        # İndirme klasörü
        self._label(scroll, "İndirme Klasörü", row); row += 1
        self._dir_var = ctk.StringVar(value=self.config.download_dir)
        ctk.CTkEntry(scroll, textvariable=self._dir_var, font=theme.FONT_SMALL).grid(
            row=row, column=0, columnspan=2, sticky="ew",
            padx=theme.PADDING_MEDIUM, pady=(0, 4),
        ); row += 1
        ctk.CTkButton(scroll, text="Gözat...", width=100, command=self._browse_dir).grid(
            row=row, column=0, sticky="w",
            padx=theme.PADDING_MEDIUM, pady=(0, theme.PADDING_MEDIUM),
        ); row += 1

        # Maksimum eş zamanlı indirme
        self._label(scroll, "Maksimum Eş Zamanlı İndirme", row); row += 1
        self._concurrent_var = ctk.StringVar(value=str(self.config.max_concurrent_downloads))
        ctk.CTkOptionMenu(
            scroll, variable=self._concurrent_var,
            values=["1", "2", "3", "4", "5"],
            font=theme.FONT_BODY, width=80,
        ).grid(row=row, column=0, columnspan=2, sticky="w",
               padx=theme.PADDING_MEDIUM, pady=(0, theme.PADDING_MEDIUM)); row += 1

        # Tema
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

        # Varsayılan kalite
        self._label(scroll, "Varsayılan Kalite", row); row += 1
        self._quality_var = ctk.StringVar(value=self.config.default_quality)
        ctk.CTkOptionMenu(
            scroll, variable=self._quality_var,
            values=QUALITY_OPTIONS, font=theme.FONT_BODY,
        ).grid(row=row, column=0, columnspan=2, sticky="w",
               padx=theme.PADDING_MEDIUM, pady=(0, theme.PADDING_MEDIUM)); row += 1

        # Video format
        self._label(scroll, "Varsayılan Video Formatı", row); row += 1
        self._vfmt_var = ctk.StringVar(value=self.config.default_video_format)
        ctk.CTkOptionMenu(
            scroll, variable=self._vfmt_var,
            values=VIDEO_FORMAT_OPTIONS, font=theme.FONT_BODY,
        ).grid(row=row, column=0, columnspan=2, sticky="w",
               padx=theme.PADDING_MEDIUM, pady=(0, theme.PADDING_MEDIUM)); row += 1

        # Ses format
        self._label(scroll, "Varsayılan Ses Formatı", row); row += 1
        self._afmt_var = ctk.StringVar(value=self.config.default_audio_format)
        ctk.CTkOptionMenu(
            scroll, variable=self._afmt_var,
            values=AUDIO_FORMAT_OPTIONS, font=theme.FONT_BODY,
        ).grid(row=row, column=0, columnspan=2, sticky="w",
               padx=theme.PADDING_MEDIUM, pady=(0, theme.PADDING_MEDIUM)); row += 1

        # Checkbox'lar
        self._label(scroll, "Gömme Seçenekleri", row); row += 1
        self._embed_thumb = self._checkbox(scroll, "Thumbnail göm", self.config.embed_thumbnail, row); row += 1
        self._embed_meta  = self._checkbox(scroll, "Metadata göm (başlık, sanatçı)", self.config.embed_metadata, row); row += 1
        self._embed_subs  = self._checkbox(scroll, "Altyazı göm (mp4 gerektirir)", self.config.embed_subtitles, row); row += 1
        self._dl_subs     = self._checkbox(scroll, "Altyazı dosyası indir (.srt)", self.config.download_subtitles, row); row += 1

        # Hız limiti
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

        # --- Jackett bölümü ---
        ctk.CTkLabel(
            scroll,
            text="Jackett Ayarları",
            font=theme.FONT_SUBTITLE,
            anchor="w",
        ).pack(anchor="w", padx=pad, pady=(pad, 5))

        ctk.CTkLabel(
            scroll,
            text=(
                "Jackett, BTK engelini aşarak 500+ torrent sitesini sorgular.\n"
                "VPS'te çalışır; URL ve API key'i buraya girin."
            ),
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_TEXT_MUTED,
            justify="left",
        ).pack(anchor="w", padx=pad, pady=(0, 8))

        ctk.CTkLabel(scroll, text="Jackett URL:", font=theme.FONT_BODY, anchor="w").pack(
            anchor="w", padx=pad, pady=(0, 2)
        )
        self._jackett_url_var = ctk.StringVar(value=self.config.jackett_url)
        ctk.CTkEntry(
            scroll,
            textvariable=self._jackett_url_var,
            placeholder_text="http://your-vps:9117",
            font=theme.FONT_BODY,
        ).pack(fill="x", padx=pad, pady=(0, 8))

        ctk.CTkLabel(scroll, text="Jackett API Key:", font=theme.FONT_BODY, anchor="w").pack(
            anchor="w", padx=pad, pady=(0, 2)
        )
        self._jackett_key_var = ctk.StringVar(value=self.config.jackett_api_key)
        ctk.CTkEntry(
            scroll,
            textvariable=self._jackett_key_var,
            placeholder_text="Jackett API key...",
            font=theme.FONT_BODY,
            show="*",
        ).pack(fill="x", padx=pad, pady=(0, 4))

        # Separator
        ctk.CTkFrame(scroll, height=1, fg_color=theme.COLOR_TEXT_MUTED).pack(
            fill="x", padx=pad, pady=12
        )

        # --- Altyazı bölümü ---
        ctk.CTkLabel(
            scroll,
            text="Altyazı Ayarları",
            font=theme.FONT_SUBTITLE,
            anchor="w",
        ).pack(anchor="w", padx=pad, pady=(0, 5))

        ctk.CTkLabel(scroll, text="OpenSubtitles API Key:", font=theme.FONT_BODY, anchor="w").pack(
            anchor="w", padx=pad, pady=(0, 2)
        )
        self._os_key_var = ctk.StringVar(value=self.config.opensubtitles_api_key)
        ctk.CTkEntry(
            scroll,
            textvariable=self._os_key_var,
            placeholder_text="OpenSubtitles API key...",
            font=theme.FONT_BODY,
            show="*",
        ).pack(fill="x", padx=pad, pady=(0, 4))

        ctk.CTkLabel(
            scroll,
            text="opensubtitles.com/en/consumers adresinden ucretsiz alabilirsiniz.",
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=pad, pady=(0, theme.PADDING_LARGE))

        # TMDB (ileride kullanım için)
        ctk.CTkLabel(scroll, text="TMDB API Key:", font=theme.FONT_BODY, anchor="w").pack(
            anchor="w", padx=pad, pady=(0, 2)
        )
        self._tmdb_key_var = ctk.StringVar(value=self.config.tmdb_api_key)
        ctk.CTkEntry(
            scroll,
            textvariable=self._tmdb_key_var,
            placeholder_text="TMDB API key...",
            font=theme.FONT_BODY,
            show="*",
        ).pack(fill="x", padx=pad, pady=(0, 4))
        ctk.CTkLabel(
            scroll,
            text="themoviedb.org/settings/api adresinden ucretsiz alabilirsiniz.",
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=pad, pady=(0, pad))

    # ------------------------------------------------------------------
    # Cookies & Login sekmesi
    # ------------------------------------------------------------------

    def _build_cookies_tab(self, parent: ctk.CTkFrame) -> None:
        pad = theme.PADDING_MEDIUM

        # Açıklama
        ctk.CTkLabel(
            parent,
            text=(
                "Login gerektiren videoları (özel Twitter/X, Instagram,\n"
                "üye-only YouTube vb.) indirebilmek için cookie ayarlayın."
            ),
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_TEXT_MUTED,
            justify="left",
        ).pack(anchor="w", padx=pad, pady=(pad, theme.PADDING_LARGE))

        # Mod seçimi
        self._cookie_mode_var = ctk.StringVar(value=self.config.cookies_mode)

        ctk.CTkRadioButton(
            parent, text="Cookie kullanma",
            variable=self._cookie_mode_var, value="none",
            font=theme.FONT_BODY,
            command=self._update_cookie_ui,
        ).pack(anchor="w", padx=pad, pady=(0, theme.PADDING_SMALL))

        ctk.CTkRadioButton(
            parent, text="Tarayıcıdan otomatik oku  (Önerilen)",
            variable=self._cookie_mode_var, value="browser",
            font=theme.FONT_BODY,
            command=self._update_cookie_ui,
        ).pack(anchor="w", padx=pad, pady=(0, theme.PADDING_SMALL))

        # --- Tarayıcı seçim alanı ---
        self._browser_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._browser_frame.pack(anchor="w", padx=pad * 3, fill="x")
        self._browser_frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self._browser_frame, text="Tarayıcı:", font=theme.FONT_BODY,
        ).grid(row=0, column=0, sticky="w", padx=(0, pad), pady=2)

        installed = detect_installed_browsers()
        browser_options = installed if installed else ["Tarayıcı bulunamadı"]

        self._browser_var = ctk.StringVar()
        self._browser_menu = ctk.CTkOptionMenu(
            self._browser_frame,
            variable=self._browser_var,
            values=browser_options,
            font=theme.FONT_BODY,
            command=self._on_browser_change,
        )
        self._browser_menu.grid(row=0, column=1, sticky="ew", pady=2)

        # Başlangıç değeri
        initial_browser = self.config.cookies_browser
        if initial_browser and initial_browser in browser_options:
            self._browser_var.set(initial_browser)
        elif installed:
            self._browser_var.set(installed[0])
        else:
            self._browser_var.set(browser_options[0])

        ctk.CTkLabel(
            self._browser_frame, text="Profil:", font=theme.FONT_BODY,
        ).grid(row=1, column=0, sticky="w", padx=(0, pad), pady=2)

        saved_profile = self.config.cookies_browser_profile
        self._profile_var = ctk.StringVar(
            value=saved_profile if saved_profile and saved_profile != "Default" else "Otomatik (önerilen)"
        )
        self._profile_menu = ctk.CTkOptionMenu(
            self._browser_frame,
            variable=self._profile_var,
            values=["Otomatik (önerilen)"],
            font=theme.FONT_BODY,
        )
        self._profile_menu.grid(row=1, column=1, sticky="ew", pady=2)

        # Profilleri yükle
        self._on_browser_change(self._browser_var.get())

        # --- Cookie Cache bölümü ---
        self._build_cache_section(parent)

        # --- Manuel dosya ---
        ctk.CTkRadioButton(
            parent, text="Manuel cookies.txt dosyası",
            variable=self._cookie_mode_var, value="file",
            font=theme.FONT_BODY,
            command=self._update_cookie_ui,
        ).pack(anchor="w", padx=pad, pady=(0, theme.PADDING_SMALL))

        self._file_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._file_frame.pack(anchor="w", padx=pad * 3, fill="x")

        self._file_path_var = ctk.StringVar(value=self.config.cookies_file_path or "")
        self._file_entry = ctk.CTkEntry(
            self._file_frame,
            textvariable=self._file_path_var,
            placeholder_text="cookies.txt dosyasını seçin...",
            font=theme.FONT_BODY,
        )
        self._file_entry.pack(side="left", fill="x", expand=True, padx=(0, theme.PADDING_SMALL))

        self._browse_cookie_btn = ctk.CTkButton(
            self._file_frame, text="Gözat", width=80,
            command=self._browse_cookie_file,
        )
        self._browse_cookie_btn.pack(side="left")

        ctk.CTkLabel(
            parent,
            text='ℹ  Nasıl oluşturulur: Chrome/Edge için "Get cookies.txt LOCALLY"\n'
                 "   eklentisini kur, siteye giriş yap, eklentiden dışa aktar.",
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_TEXT_MUTED,
            justify="left",
        ).pack(anchor="w", padx=pad * 3, pady=(theme.PADDING_SMALL, 0))

        self._update_cookie_ui()

    # ------------------------------------------------------------------
    # Cookie Cache bölümü
    # ------------------------------------------------------------------

    def _build_cache_section(self, parent: ctk.CTkFrame) -> None:
        """Cookie cache yönetim bölümü."""
        self._cache_frame = ctk.CTkFrame(parent, fg_color=theme.COLOR_BG_SECONDARY)
        self._cache_frame.pack(anchor="w", padx=30, pady=(theme.PADDING_SMALL, 15), fill="x")

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
            btn_frame, text="Senkronize Et",
            command=self._sync_cookies,
            fg_color=theme.COLOR_ACCENT,
            hover_color=theme.COLOR_ACCENT_HOVER,
            width=160,
        )
        self._sync_btn.pack(side="left", padx=(0, 5))

        self._clear_cache_btn = ctk.CTkButton(
            btn_frame, text="Cache'i Temizle",
            command=self._clear_cookie_cache,
            fg_color="transparent",
            border_width=1,
            text_color=theme.COLOR_TEXT_MUTED,
            border_color=theme.COLOR_TEXT_MUTED,
            width=130,
        )
        self._clear_cache_btn.pack(side="left", padx=5)

        ctk.CTkLabel(
            self._cache_frame,
            text=(
                "Cache sayesinde senkronizasyondan sonra tarayici acikken\n"
                "de indirme yapabilirsiniz. 7 gunden eski cache yenilenmelidir."
            ),
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_TEXT_MUTED,
            anchor="w", justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 10))

        self._update_cache_status()

    def _update_cache_status(self) -> None:
        """Cache durumunu UI'a yansıt."""
        meta = get_metadata()
        if meta is None:
            self._cache_status_label.configure(
                text="Henuz senkronize edilmedi",
                text_color=theme.COLOR_WARNING,
            )
        elif meta.is_stale():
            self._cache_status_label.configure(
                text=(
                    f"Eski senkron (>7 gun): {meta.age_human()}\n"
                    f"  Tarayici: {meta.browser} / {meta.profile or 'Default'}\n"
                    f"  Cookie sayisi: {meta.cookie_count}"
                ),
                text_color=theme.COLOR_WARNING,
            )
        else:
            self._cache_status_label.configure(
                text=(
                    f"Senkronize edildi: {meta.age_human()}\n"
                    f"  Tarayici: {meta.browser} / {meta.profile or 'Default'}\n"
                    f"  Cookie sayisi: {meta.cookie_count}"
                ),
                text_color=theme.COLOR_SUCCESS,
            )

    def _sync_cookies(self) -> None:
        """Senkron butonu — background thread'de çalışır."""
        browser = self._browser_var.get()
        profile = self._profile_var.get()
        # "Otomatik (önerilen)" ve "Default" → None
        if profile in ("Otomatik (önerilen)", "Default", ""):
            profile = None

        if browser not in SUPPORTED_BROWSERS:
            return

        self._sync_btn.configure(state="disabled", text="Senkronize ediliyor...")
        self._cache_status_label.configure(
            text="Tarayicidan cookie'ler okunuyor...",
            text_color=theme.COLOR_TEXT_MUTED,
        )

        def task():
            try:
                meta = sync_from_browser(
                    browser,
                    profile,
                )
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
            text=f"Hata: {error_msg}",
            text_color=theme.COLOR_ERROR,
        )

    def _clear_cookie_cache(self) -> None:
        """Cache'i sil."""
        clear_cache()
        self._update_cache_status()

    # ------------------------------------------------------------------
    # Cookies sekmesi yardımcıları
    # ------------------------------------------------------------------

    def _update_cookie_ui(self) -> None:
        """Seçili moda göre alt alanları etkinleştirir/devre dışı bırakır."""
        mode = self._cookie_mode_var.get()

        browser_state: str = "normal" if mode == "browser" else "disabled"
        for widget in self._browser_frame.winfo_children():
            try:
                widget.configure(state=browser_state)
            except Exception:
                pass  # CTkLabel gibi widget'lar state desteklemez

        file_state: str = "normal" if mode == "file" else "disabled"
        try:
            self._file_entry.configure(state=file_state)
            self._browse_cookie_btn.configure(state=file_state)
        except Exception:
            pass

    def _on_browser_change(self, browser: str) -> None:
        """Tarayıcı değişince profil dropdown'ını günceller."""
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
            # "Otomatik (önerilen)" → None olarak kaydet
            if profile in ("Otomatik (önerilen)", "Default"):
                self.config.cookies_browser_profile = None
            else:
                self.config.cookies_browser_profile = profile
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

        self.config.save()
        self.on_save(self.config)
        self.destroy()

    # ------------------------------------------------------------------
    # Yardımcılar
    # ------------------------------------------------------------------

    def _label(self, parent: ctk.CTkScrollableFrame, text: str, row: int) -> None:
        ctk.CTkLabel(
            parent, text=text,
            font=theme.FONT_SMALL, text_color=theme.COLOR_TEXT_MUTED, anchor="w",
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
