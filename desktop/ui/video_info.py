"""Video önizleme kartı bileşeni."""

from __future__ import annotations

import threading
from io import BytesIO

import customtkinter as ctk
import requests
from PIL import Image

from core import VideoInfo
from desktop.ui import theme
from desktop.utils.threading_helper import run_on_ui

# Thumbnail gösterilecek boyut
THUMB_W = 213
THUMB_H = 120


class VideoInfoFrame(ctk.CTkFrame):
    """Thumbnail, başlık, uploader ve süreyi gösteren önizleme kartı."""

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        super().__init__(master, corner_radius=theme.CORNER_RADIUS)
        self._info: VideoInfo | None = None
        self._thumbnail_image: ctk.CTkImage | None = None  # GC'den korumak için
        self._build()

    def _build(self) -> None:
        # Thumbnail (sol)
        self.thumbnail_label = ctk.CTkLabel(
            self, text="", width=THUMB_W, height=THUMB_H,
            fg_color=theme.COLOR_BG_SECONDARY, corner_radius=theme.CORNER_RADIUS,
        )
        self.thumbnail_label.pack(
            side="left",
            padx=theme.PADDING_MEDIUM,
            pady=theme.PADDING_MEDIUM,
        )

        # Bilgi alanı (sağ)
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(
            side="left", fill="both", expand=True,
            padx=(0, theme.PADDING_MEDIUM),
            pady=theme.PADDING_MEDIUM,
        )

        self.title_label = ctk.CTkLabel(
            info_frame,
            text="",
            font=theme.FONT_SUBTITLE,
            anchor="w",
            justify="left",
            wraplength=560,
        )
        self.title_label.pack(anchor="w", fill="x")

        self.uploader_label = ctk.CTkLabel(
            info_frame,
            text="",
            font=theme.FONT_BODY,
            text_color=theme.COLOR_TEXT_MUTED,
            anchor="w",
        )
        self.uploader_label.pack(anchor="w", fill="x", pady=(6, 0))

        self.meta_label = ctk.CTkLabel(
            info_frame,
            text="",
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_TEXT_MUTED,
            anchor="w",
        )
        self.meta_label.pack(anchor="w", fill="x", pady=(4, 0))

    def show_info(self, info: VideoInfo) -> None:
        """Video bilgilerini karta yazar ve thumbnail'i arka planda indirir."""
        self._info = info

        title = info.title or "Başlıksız"
        self.title_label.configure(text=title)
        self.uploader_label.configure(text=info.uploader or "Bilinmeyen kanal")

        duration_str = _format_duration(info.duration) if info.duration else "?"
        self.meta_label.configure(
            text=f"{info.extractor.capitalize()} • {duration_str} • "
                 f"{len(info.video_formats)} video / {len(info.audio_formats)} ses formatı"
        )

        # Thumbnail placeholder (önceki resim temizlenir)
        self._thumbnail_image = None
        try:
            self.thumbnail_label.configure(image="", text="⏳")
        except Exception:
            self.thumbnail_label.configure(text="⏳")

        if info.thumbnail:
            threading.Thread(
                target=self._load_thumbnail,
                args=(info.thumbnail,),
                daemon=True,
                name="ThumbnailLoader",
            ).start()

    def _load_thumbnail(self, url: str) -> None:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content))
            img = img.convert("RGB")
            ctk_img = ctk.CTkImage(
                light_image=img,
                dark_image=img,
                size=(THUMB_W, THUMB_H),
            )

            def _apply() -> None:
                try:
                    if self.winfo_exists():
                        self._thumbnail_image = ctk_img  # GC'den koru
                        self.thumbnail_label.configure(image=ctk_img, text="")
                except Exception:
                    pass

            run_on_ui(self, _apply)
        except Exception:
            def _fallback() -> None:
                try:
                    if self.winfo_exists():
                        self.thumbnail_label.configure(text="🎬")
                except Exception:
                    pass
            run_on_ui(self, _fallback)

    def clear(self) -> None:
        """Kartı sıfırlar, image referanslarını güvenli şekilde kaldırır."""
        self._info = None
        self._thumbnail_image = None
        try:
            self.thumbnail_label.configure(image="", text="")
        except Exception:
            try:
                self.thumbnail_label.configure(text="")
            except Exception:
                pass
        self.title_label.configure(text="")
        self.uploader_label.configure(text="")
        self.meta_label.configure(text="")


def _format_duration(seconds: int | float) -> str:
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
