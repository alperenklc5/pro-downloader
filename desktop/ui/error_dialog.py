"""Kullanıcı dostu hata gösterme bileşeni."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from core.error_messages import FriendlyError
from desktop.ui import theme


class ErrorDialog(ctk.CTkToplevel):
    """Yapılandırılmış hata penceresi."""

    def __init__(
        self,
        master,
        error: FriendlyError,
        on_open_settings: Callable[[], None] | None = None,
    ):
        super().__init__(master)
        self.error = error
        self.on_open_settings = on_open_settings
        self._details_frame: ctk.CTkFrame | None = None

        self.title(error.title)
        self.geometry("500x380")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self._build()

        # Pencereyi merkeze al
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - 500) // 2
        y = master.winfo_y() + (master.winfo_height() - 380) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self) -> None:
        # İkon + başlık
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))

        icon = self._get_icon()
        ctk.CTkLabel(
            header, text=icon,
            font=(theme.FONT_FAMILY, 32),
        ).pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            header, text=self.error.title,
            font=theme.FONT_TITLE,
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        # Mesaj
        ctk.CTkLabel(
            self, text=self.error.message,
            font=theme.FONT_BODY,
            wraplength=440,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=20, pady=10)

        # Öneri (varsa)
        if self.error.suggestion:
            ctk.CTkFrame(self, height=1, fg_color=theme.COLOR_TEXT_MUTED).pack(
                fill="x", padx=20, pady=10
            )

            ctk.CTkLabel(
                self, text="💡 Çözüm Önerisi:",
                font=theme.FONT_SUBTITLE,
                anchor="w",
            ).pack(fill="x", padx=20, pady=(0, 5))

            ctk.CTkLabel(
                self, text=self.error.suggestion,
                font=theme.FONT_BODY,
                wraplength=440,
                justify="left",
                anchor="w",
                text_color=theme.COLOR_TEXT_MUTED,
            ).pack(fill="x", padx=20, pady=(0, 10))

        # Butonlar
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(10, 20), side="bottom")

        if self.error.category in ("auth", "cookie") and self.on_open_settings:
            ctk.CTkButton(
                btn_frame, text="Cookie Ayarlarını Aç",
                command=self._open_settings,
                fg_color=theme.COLOR_ACCENT,
                hover_color=theme.COLOR_ACCENT_HOVER,
            ).pack(side="left", padx=(0, 5))

        ctk.CTkButton(
            btn_frame, text="Detayları Göster",
            command=self._toggle_details,
            fg_color="transparent",
            border_width=1,
            text_color=theme.COLOR_TEXT_MUTED,
            border_color=theme.COLOR_TEXT_MUTED,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="Kapat",
            command=self.destroy,
        ).pack(side="right")

    def _get_icon(self) -> str:
        icons = {
            "auth": "🔒",
            "cookie": "🍪",
            "network": "🌐",
            "format": "❓",
            "geo": "🌍",
            "generic": "⚠️",
        }
        return icons.get(self.error.category, "⚠️")

    def _toggle_details(self) -> None:
        if self._details_frame is None:
            self.geometry("500x520")
            self._details_frame = ctk.CTkFrame(self, fg_color=theme.COLOR_BG_SECONDARY)
            self._details_frame.pack(fill="x", padx=20, pady=(0, 10))

            details_text = ctk.CTkTextbox(
                self._details_frame, height=120,
                font=(theme.FONT_FAMILY, 10),
            )
            details_text.pack(fill="both", expand=True, padx=10, pady=10)
            details_text.insert("1.0", self.error.raw_error or "(detay yok)")
            details_text.configure(state="disabled")
        else:
            self._details_frame.destroy()
            self._details_frame = None
            self.geometry("500x380")

    def _open_settings(self) -> None:
        self.destroy()
        if self.on_open_settings:
            self.on_open_settings()
