"""Alt durum çubuğu — aktif indirme sayısı, hız, boş alan."""
from __future__ import annotations

import shutil

import customtkinter as ctk

from desktop.ui import theme


class StatusBar(ctk.CTkFrame):
    """Alt durum çubuğu."""

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        super().__init__(
            master,
            height=theme.STATUS_BAR_HEIGHT,
            fg_color=theme.BG_SECONDARY,
            corner_radius=0,
        )
        self.pack_propagate(False)
        self._build()

    def _build(self) -> None:
        # Soldan ince bir üst kenarlık çizgisi
        ctk.CTkFrame(self, height=1, fg_color=theme.BORDER_SUBTLE).pack(
            fill="x", side="top"
        )

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True)

        # Sol: aktif indirme sayısı
        self.active_label = ctk.CTkLabel(
            content,
            text="0 aktif indirme",
            font=theme.FONT_TINY,
            text_color=theme.TEXT_MUTED,
        )
        self.active_label.pack(side="left", padx=16)

        # Orta: hız
        self.speed_label = ctk.CTkLabel(
            content,
            text="⬇ 0 B/s",
            font=theme.FONT_TINY,
            text_color=theme.TEXT_MUTED,
        )
        self.speed_label.pack(side="left", padx=8)

        # Sağ: disk alanı
        self.disk_label = ctk.CTkLabel(
            content,
            text="",
            font=theme.FONT_TINY,
            text_color=theme.TEXT_MUTED,
        )
        self.disk_label.pack(side="right", padx=16)
        self._refresh_disk()

    def _refresh_disk(self) -> None:
        try:
            usage = shutil.disk_usage("C:\\")
            free_gb = usage.free / (1024 ** 3)
            self.disk_label.configure(text=f"💾 {free_gb:.0f} GB boş")
        except Exception:
            pass

    def update(self, active_count: int = 0, total_speed: float = 0) -> None:
        """Aktif indirme sayısı ve toplam hızı güncelle."""
        count_text = f"{active_count} aktif indirme" if active_count else "Boşta"
        self.active_label.configure(text=count_text)

        if total_speed >= 1_000_000:
            speed_str = f"⬇ {total_speed / 1_000_000:.1f} MB/s"
        elif total_speed >= 1_000:
            speed_str = f"⬇ {total_speed / 1_000:.0f} KB/s"
        else:
            speed_str = f"⬇ {total_speed:.0f} B/s"

        self.speed_label.configure(
            text=speed_str,
            text_color=theme.ACCENT_BLUE if total_speed > 0 else theme.TEXT_MUTED,
        )
        self._refresh_disk()
