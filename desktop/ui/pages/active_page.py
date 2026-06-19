"""Aktif indirmeler sayfası — tüm indirmeleri tek yerde göster."""
from __future__ import annotations

import customtkinter as ctk

from desktop.ui import theme
from desktop.ui.download_list import DownloadList


class ActiveDownloadsPage(ctk.CTkFrame):
    """Tüm aktif indirmelerin genel görünümü."""

    # İstatistik sayaçları; App bu attrs'ı günceller
    _stat_labels: dict[str, ctk.CTkLabel]

    def __init__(self, master: ctk.CTkBaseClass, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._stat_labels = {}
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # ── Başlık ──────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(
            row=0, column=0, sticky="ew",
            padx=theme.PADDING_XL,
            pady=(theme.PADDING_XL, theme.PADDING_LARGE),
        )

        ctk.CTkLabel(
            header,
            text="⬇ Aktif İndirmeler",
            font=theme.FONT_TITLE,
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        # ── İstatistik kartları ─────────────────────────────────────────
        stats_row = ctk.CTkFrame(self, fg_color="transparent")
        stats_row.grid(
            row=1, column=0, sticky="ew",
            padx=theme.PADDING_XL,
            pady=(0, theme.PADDING_LARGE),
        )

        stat_defs = [
            ("active",   "⬇",  "İndiriliyor",   theme.ACCENT_BLUE),
            ("paused",   "⏸",  "Duraklatılmış", theme.ACCENT_ORANGE),
            ("complete", "✓",  "Tamamlanan",    theme.ACCENT_GREEN),
            ("error",    "✗",  "Hatalı",        theme.ACCENT_RED),
        ]

        for key, icon, label, color in stat_defs:
            stat_card = ctk.CTkFrame(
                stats_row,
                fg_color=theme.BG_SECONDARY,
                corner_radius=theme.CORNER_RADIUS,
                border_width=1,
                border_color=theme.BORDER_DEFAULT,
            )
            stat_card.pack(side="left", fill="x", expand=True, padx=4)

            ctk.CTkLabel(
                stat_card,
                text=f"{icon}  {label}",
                font=theme.FONT_SMALL,
                text_color=theme.TEXT_SECONDARY,
            ).pack(padx=12, pady=(10, 0))

            count_lbl = ctk.CTkLabel(
                stat_card,
                text="0",
                font=theme.FONT_TITLE,
                text_color=color,
            )
            count_lbl.pack(padx=12, pady=(0, 10))
            self._stat_labels[key] = count_lbl

        # ── İndirme listesi ─────────────────────────────────────────────
        self.download_list = DownloadList(self)
        self.download_list.grid(
            row=2, column=0, sticky="nsew",
            padx=theme.PADDING_XL,
            pady=(0, theme.PADDING_MEDIUM),
        )

    def refresh_stats(self) -> None:
        """download_list'ten istatistik sayaçlarını güncelle."""
        active, paused, complete, error = self.download_list.get_stats()
        self._stat_labels["active"].configure(text=str(active))
        self._stat_labels["paused"].configure(text=str(paused))
        self._stat_labels["complete"].configure(text=str(complete))
        self._stat_labels["error"].configure(text=str(error))
