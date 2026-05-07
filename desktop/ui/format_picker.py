"""Format ve kalite seçici bileşeni."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from desktop.ui import theme

VIDEO_QUALITIES = ["best", "1080p", "720p", "480p", "360p", "240p"]
AUDIO_QUALITIES = ["best", "320kbps", "192kbps", "128kbps"]
VIDEO_FORMATS = ["mp4", "mkv", "webm"]
AUDIO_FORMATS = ["mp3", "m4a", "opus"]

# "best" kalitesi için yt-dlp'ye geçilecek değer
_QUALITY_MAP = {
    "best": "best",
    "320kbps": "best",
    "192kbps": "best",
    "128kbps": "best",
}


class FormatPickerFrame(ctk.CTkFrame):
    """
    Mod (video/ses), kalite ve format seçimini yönetir.
    İndir butonunu içerir.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_download: Callable[[str, bool, str], None],
        default_quality: str = "720p",
        default_video_format: str = "mp4",
        default_audio_format: str = "mp3",
    ) -> None:
        """
        Args:
            master: Üst widget.
            on_download: (quality, audio_only, format_ext) ile çağrılır.
            default_quality: Başlangıç kalitesi.
            default_video_format: Başlangıç video formatı.
            default_audio_format: Başlangıç ses formatı.
        """
        super().__init__(master, corner_radius=theme.CORNER_RADIUS)
        self.on_download = on_download
        self._default_video_format = default_video_format
        self._default_audio_format = default_audio_format
        self._default_quality = default_quality
        self._build()

    def _build(self) -> None:
        # Sol grup: mod + kalite + format
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True, padx=theme.PADDING_MEDIUM, pady=theme.PADDING_MEDIUM)

        # Mod seçimi
        mode_label = ctk.CTkLabel(left, text="Mod:", font=theme.FONT_BODY)
        mode_label.grid(row=0, column=0, padx=(0, theme.PADDING_SMALL), sticky="w")

        self.mode_btn = ctk.CTkSegmentedButton(
            left,
            values=["Video", "Sadece Ses"],
            command=self._on_mode_change,
            font=theme.FONT_BODY,
        )
        self.mode_btn.set("Video")
        self.mode_btn.grid(row=0, column=1, padx=(0, theme.PADDING_LARGE), sticky="w")

        # Kalite dropdown
        quality_label = ctk.CTkLabel(left, text="Kalite:", font=theme.FONT_BODY)
        quality_label.grid(row=0, column=2, padx=(0, theme.PADDING_SMALL), sticky="w")

        self.quality_var = ctk.StringVar(value=self._default_quality)
        self.quality_menu = ctk.CTkOptionMenu(
            left,
            variable=self.quality_var,
            values=VIDEO_QUALITIES,
            font=theme.FONT_BODY,
            width=110,
        )
        self.quality_menu.grid(row=0, column=3, padx=(0, theme.PADDING_LARGE), sticky="w")

        # Format dropdown
        format_label = ctk.CTkLabel(left, text="Format:", font=theme.FONT_BODY)
        format_label.grid(row=0, column=4, padx=(0, theme.PADDING_SMALL), sticky="w")

        self.format_var = ctk.StringVar(value=self._default_video_format)
        self.format_menu = ctk.CTkOptionMenu(
            left,
            variable=self.format_var,
            values=VIDEO_FORMATS,
            font=theme.FONT_BODY,
            width=100,
        )
        self.format_menu.grid(row=0, column=5, sticky="w")

        # Sağ: İndir butonu
        self.download_btn = ctk.CTkButton(
            self,
            text="⬇  İndir",
            width=140,
            height=42,
            font=theme.FONT_SUBTITLE,
            fg_color=theme.COLOR_SUCCESS,
            hover_color="#1d7a52",
            command=self._on_download_click,
            state="disabled",
        )
        self.download_btn.pack(
            side="right",
            padx=theme.PADDING_MEDIUM,
            pady=theme.PADDING_MEDIUM,
        )

    def _on_mode_change(self, value: str) -> None:
        if value == "Sadece Ses":
            self.quality_var.set("best")
            self.quality_menu.configure(values=AUDIO_QUALITIES)
            self.format_var.set(self._default_audio_format)
            self.format_menu.configure(values=AUDIO_FORMATS)
        else:
            self.quality_var.set(self._default_quality)
            self.quality_menu.configure(values=VIDEO_QUALITIES)
            self.format_var.set(self._default_video_format)
            self.format_menu.configure(values=VIDEO_FORMATS)

    def _on_download_click(self) -> None:
        audio_only = self.mode_btn.get() == "Sadece Ses"
        quality = self.quality_var.get()
        fmt = self.format_var.get()

        # "192kbps" gibi değerleri yt-dlp'nin anlayacağı hale çevir
        if audio_only and quality in ("320kbps", "192kbps", "128kbps"):
            quality = "audio"

        self.on_download(quality, audio_only, fmt)

    def set_enabled(self, enabled: bool) -> None:
        """İndir butonunu aktif/pasif yapar."""
        self.download_btn.configure(state="normal" if enabled else "disabled")

    def apply_defaults(
        self,
        quality: str,
        video_format: str,
        audio_format: str,
    ) -> None:
        """Config'den gelen default değerleri uygular."""
        self._default_quality = quality
        self._default_video_format = video_format
        self._default_audio_format = audio_format

        if self.mode_btn.get() == "Video":
            self.quality_var.set(quality)
            self.format_var.set(video_format)
        else:
            self.format_var.set(audio_format)
