"""Mega.nz ve Pixeldrain indirme sekmesi."""
import customtkinter as ctk
from desktop.ui import theme


class HostingPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=theme.PADDING_XL, pady=(theme.PADDING_XL, theme.PADDING_LARGE))

        ctk.CTkLabel(
            header,
            text="☁ Mega.nz / Pixeldrain",
            font=theme.FONT_TITLE,
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        # Desteklenen siteler bilgisi
        info_card = ctk.CTkFrame(
            self,
            fg_color=theme.BG_SECONDARY,
            corner_radius=theme.CORNER_RADIUS_LARGE,
            border_width=1,
            border_color=theme.BORDER_DEFAULT,
        )
        info_card.pack(fill="x", padx=theme.PADDING_XL, pady=(0, theme.PADDING_MEDIUM))

        ctk.CTkLabel(
            info_card,
            text=(
                "Desteklenen siteler:\n"
                "• Mega.nz — Dosya ve klasör linkleri\n"
                "• Pixeldrain — Dosya linkleri\n\n"
                "IP limiti aşıldığında otomatik olarak VPS ve proxy rotasyonu yapılır."
            ),
            font=theme.FONT_SMALL,
            text_color=theme.TEXT_SECONDARY,
            justify="left",
        ).pack(padx=theme.PADDING_LARGE, pady=theme.PADDING_MEDIUM)

        # URL Input
        card = ctk.CTkFrame(
            self,
            fg_color=theme.BG_SECONDARY,
            corner_radius=theme.CORNER_RADIUS_LARGE,
            border_width=1,
            border_color=theme.BORDER_DEFAULT,
        )
        card.pack(fill="x", padx=theme.PADDING_XL, pady=(0, theme.PADDING_LARGE))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=theme.PADDING_LARGE, pady=theme.PADDING_LARGE)

        self.url_entry = ctk.CTkEntry(
            inner,
            placeholder_text="Mega.nz veya Pixeldrain linki yapıştır...",
            font=theme.FONT_BODY,
            height=44,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER_DEFAULT,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.CORNER_RADIUS,
        )
        self.url_entry.pack(fill="x", pady=(0, theme.PADDING_MEDIUM))
        self.url_entry.bind("<Return>", lambda e: self._download())

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x")

        ctk.CTkButton(
            btn_row,
            text="📋 Yapıştır",
            font=theme.FONT_BODY,
            width=120,
            height=38,
            fg_color=theme.BG_TERTIARY,
            hover_color=theme.BG_ELEVATED,
            command=self._paste,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row,
            text="⬇ İndir",
            font=theme.FONT_BODY_BOLD,
            width=140,
            height=38,
            fg_color=theme.ACCENT_GREEN,
            hover_color=theme.ACCENT_GREEN_HOVER,
            command=self._download,
        ).pack(side="left")

        # İndirme listesi
        ctk.CTkLabel(
            self,
            text="İndirmeler",
            font=theme.FONT_SUBTITLE,
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", padx=theme.PADDING_XL, pady=(theme.PADDING_LARGE, theme.PADDING_SMALL))

        self.download_list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.download_list.pack(
            fill="both", expand=True,
            padx=theme.PADDING_XL, pady=(0, theme.PADDING_MEDIUM)
        )

    def _paste(self):
        try:
            text = self.clipboard_get()
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, text)
        except Exception:
            pass

    def _download(self):
        url = self.url_entry.get().strip()
        if url:
            self.app._start_hosting_download(url)
