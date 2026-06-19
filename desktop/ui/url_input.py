"""URL giriş alanı ve 'Bilgi Al' butonu bileşeni."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from desktop.ui import theme


class UrlInputFrame(ctk.CTkFrame):
    """URL girişi, yapıştır butonu ve bilgi alma butonu."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_fetch: Callable[[str], None],
        on_game_search: Callable[[str], None] | None = None,
    ) -> None:
        """
        Args:
            master: Üst widget.
            on_fetch: Geçerli URL ile çağrılır.
            on_game_search: 🎮 butonuna basılınca sorgu string'i ile çağrılır.
        """
        super().__init__(master, corner_radius=theme.CORNER_RADIUS)
        self.on_fetch = on_fetch
        self.on_game_search = on_game_search
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            self,
            placeholder_text="Video URL'sini buraya yapıştır... (YouTube, TikTok, Instagram, ...)",
            font=theme.FONT_BODY,
            height=42,
        )
        self.url_entry.grid(
            row=0, column=0,
            padx=(theme.PADDING_MEDIUM, theme.PADDING_SMALL),
            pady=theme.PADDING_MEDIUM,
            sticky="ew",
        )
        self.url_entry.bind("<Return>", lambda _e: self._fetch())

        self.paste_btn = ctk.CTkButton(
            self,
            text="Yapıştır",
            width=90,
            height=42,
            command=self._paste,
        )
        self.paste_btn.grid(
            row=0, column=1,
            padx=(0, theme.PADDING_SMALL),
            pady=theme.PADDING_MEDIUM,
        )

        if self.on_game_search:
            self.game_btn = ctk.CTkButton(
                self,
                text="🎮",
                width=42,
                height=42,
                command=self._game_search,
                fg_color=theme.COLOR_BG_SECONDARY,
                hover_color=theme.COLOR_BG_TERTIARY,
                font=("", 18),
            )
            self.game_btn.grid(
                row=0, column=2,
                padx=(0, theme.PADDING_SMALL),
                pady=theme.PADDING_MEDIUM,
            )

        self.fetch_btn = ctk.CTkButton(
            self,
            text="Bilgi Al",
            width=120,
            height=42,
            command=self._fetch,
            fg_color=theme.COLOR_ACCENT,
            hover_color=theme.COLOR_ACCENT_HOVER,
        )
        fetch_col = 3 if self.on_game_search else 2
        self.fetch_btn.grid(
            row=0, column=fetch_col,
            padx=(0, theme.PADDING_MEDIUM),
            pady=theme.PADDING_MEDIUM,
        )

    def _paste(self) -> None:
        try:
            text = self.clipboard_get()
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, text.strip())
        except Exception:
            pass

    def _fetch(self) -> None:
        url = self.url_entry.get().strip()
        if url:
            self.on_fetch(url)

    def _game_search(self) -> None:
        query = self.url_entry.get().strip()
        if query and self.on_game_search:
            self.on_game_search(query)

    def set_loading(self, loading: bool) -> None:
        """Yükleniyor durumunu ayarlar (butonları disable/enable eder)."""
        state: str = "disabled" if loading else "normal"
        text = "Yükleniyor..." if loading else "Bilgi Al"
        self.fetch_btn.configure(state=state, text=text)
        self.paste_btn.configure(state=state)
        self.url_entry.configure(state=state)
        if self.on_game_search:
            self.game_btn.configure(state=state)

    def clear(self) -> None:
        """URL alanını temizler."""
        self.url_entry.configure(state="normal")
        self.url_entry.delete(0, "end")

    def get_url(self) -> str:
        """Giriş alanındaki URL'yi döndürür."""
        return self.url_entry.get().strip()
