"""Video indirici sekmesi — URL yapıştır, bilgi al, indir."""
from __future__ import annotations

import customtkinter as ctk

from core import VideoInfo
from core.error_messages import clean_ansi
from desktop.ui import theme
from desktop.ui.download_list import DownloadList
from desktop.ui.format_picker import FormatPickerFrame
from desktop.ui.url_input import UrlInputFrame
from desktop.ui.video_info import VideoInfoFrame


class VideoPage(ctk.CTkFrame):
    """Video indirme sayfası.

    Mevcut bileşenleri (UrlInputFrame, VideoInfoFrame, FormatPickerFrame,
    DownloadList) kendi içinde barındırır; App bu bileşenlere kısayol olarak
    erişmeye devam eder.
    """

    def __init__(self, master: ctk.CTkBaseClass, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.columnconfigure(0, weight=1)
        self.rowconfigure(5, weight=1)
        self._build()

    def _build(self) -> None:
        # ── Satır 0: Sayfa başlığı ──────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(
            row=0, column=0, sticky="ew",
            padx=theme.PADDING_XL,
            pady=(theme.PADDING_XL, theme.PADDING_MEDIUM),
        )

        ctk.CTkLabel(
            header,
            text="🎬 Video İndirici",
            font=theme.FONT_TITLE,
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text="URL yapıştır, format seç, indir",
            font=theme.FONT_SMALL,
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=(14, 0))

        # ── Satır 1: URL kart alanı ─────────────────────────────────────
        url_card = ctk.CTkFrame(
            self,
            fg_color=theme.BG_SECONDARY,
            corner_radius=theme.CORNER_RADIUS_LARGE,
            border_width=1,
            border_color=theme.BORDER_DEFAULT,
        )
        url_card.grid(
            row=1, column=0, sticky="ew",
            padx=theme.PADDING_XL,
        )
        url_card.columnconfigure(0, weight=1)

        self.url_input = UrlInputFrame(
            url_card,
            on_fetch=self.app._on_fetch,
            on_game_search=None,          # Oyun için ayrı sekme var
        )
        self.url_input.grid(
            row=0, column=0, sticky="ew",
            padx=theme.PADDING_SMALL,
            pady=theme.PADDING_SMALL,
        )

        # ── Satır 2: Hata bandı (başta gizli) ──────────────────────────
        self.error_frame = ctk.CTkFrame(
            self,
            fg_color=theme.ACCENT_RED,
            corner_radius=theme.CORNER_RADIUS,
        )
        self.error_label = ctk.CTkLabel(
            self.error_frame,
            text="",
            font=theme.FONT_SMALL,
            text_color="white",
            anchor="w",
        )
        self.error_label.pack(
            side="left", fill="x", expand=True,
            padx=theme.PADDING_MEDIUM, pady=6,
        )
        ctk.CTkButton(
            self.error_frame,
            text="✕",
            width=28, height=28,
            fg_color="transparent",
            hover_color=theme.ACCENT_RED_HOVER,
            command=self.hide_error,
        ).pack(side="right", padx=(0, theme.PADDING_SMALL))
        # Grid'e konmaz — show_error tarafından yönetilir

        # ── Satır 3: Video bilgi kartı (başta gizli) ────────────────────
        self.video_info_frame = VideoInfoFrame(self)
        # Grid'e konmaz — show_video_info tarafından yönetilir

        # ── Satır 4: Format seçici ──────────────────────────────────────
        self.format_picker = FormatPickerFrame(
            self,
            on_download=self.app._on_download,
            default_quality=self.app.config_obj.default_quality,
            default_video_format=self.app.config_obj.default_video_format,
            default_audio_format=self.app.config_obj.default_audio_format,
        )
        self.format_picker.grid(
            row=4, column=0, sticky="ew",
            padx=theme.PADDING_XL,
            pady=(theme.PADDING_MEDIUM, 0),
        )

        # ── Satır 5: İndirme listesi (genişleyebilir) ───────────────────
        self.download_list = DownloadList(self)
        self.download_list.grid(
            row=5, column=0, sticky="nsew",
            padx=theme.PADDING_XL,
            pady=theme.PADDING_MEDIUM,
        )

    # ------------------------------------------------------------------
    # Hata yönetimi
    # ------------------------------------------------------------------

    def show_error(self, message: str) -> None:
        """Hata bantını göster ve 8 saniye sonra gizle."""
        cleaned = clean_ansi(message)
        if len(cleaned) > 120:
            cleaned = cleaned[:120] + "..."
        self.error_label.configure(text=cleaned)
        self.error_frame.grid(
            row=2, column=0, sticky="ew",
            padx=theme.PADDING_XL,
            pady=(theme.PADDING_SMALL, 0),
        )
        self.after(8000, self.hide_error)

    def hide_error(self) -> None:
        self.error_frame.grid_remove()

    # ------------------------------------------------------------------
    # Video bilgisi yönetimi
    # ------------------------------------------------------------------

    def show_video_info(self, info: VideoInfo) -> None:
        self.video_info_frame.show_info(info)
        self.video_info_frame.grid(
            row=3, column=0, sticky="ew",
            padx=theme.PADDING_XL,
            pady=(theme.PADDING_MEDIUM, 0),
        )

    def hide_video_info(self) -> None:
        self.video_info_frame.grid_remove()
        self.video_info_frame.clear()
