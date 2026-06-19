"""Sol sidebar navigasyon."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from desktop.ui import theme


class SidebarItem:
    """Tek bir sidebar menü öğesi."""

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        icon: str,
        label: str,
        command: Callable[[], None] | None = None,
        is_active: bool = False,
    ) -> None:
        self._active = is_active
        self.frame = ctk.CTkFrame(
            parent,
            fg_color=theme.BG_TERTIARY if is_active else "transparent",
            corner_radius=theme.CORNER_RADIUS_SMALL,
            cursor="hand2",
        )
        self.frame.pack(fill="x", padx=8, pady=2)

        inner = ctk.CTkFrame(self.frame, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=8)

        ctk.CTkLabel(
            inner,
            text=icon,
            font=("", 18),
            width=24,
        ).pack(side="left")

        self._label_widget = ctk.CTkLabel(
            inner,
            text=label,
            font=theme.FONT_BODY,
            text_color=theme.TEXT_PRIMARY if is_active else theme.TEXT_SECONDARY,
        )
        self._label_widget.pack(side="left", padx=(12, 0))

        # Hover efekti
        def _on_enter(_e=None) -> None:
            self.frame.configure(fg_color=theme.BG_TERTIARY)

        def _on_leave(_e=None) -> None:
            self.frame.configure(
                fg_color=theme.BG_TERTIARY if self._active else "transparent"
            )

        for widget in (self.frame, inner, *inner.winfo_children()):
            widget.bind("<Enter>", _on_enter)
            widget.bind("<Leave>", _on_leave)
            if command:
                widget.bind("<Button-1>", lambda _e, c=command: c())

    def set_active(self, active: bool) -> None:
        self._active = active
        self.frame.configure(
            fg_color=theme.BG_TERTIARY if active else "transparent"
        )
        self._label_widget.configure(
            text_color=theme.TEXT_PRIMARY if active else theme.TEXT_SECONDARY
        )


class Sidebar(ctk.CTkFrame):
    """Sol navigasyon sidebar."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_navigate: Callable[[str], None],
    ) -> None:
        super().__init__(
            master,
            width=theme.SIDEBAR_WIDTH,
            fg_color=theme.BG_SECONDARY,
            corner_radius=0,
        )
        self.pack_propagate(False)
        self.on_navigate = on_navigate
        self.items: dict[str, SidebarItem] = {}
        self._build()

    def _build(self) -> None:
        # Logo / Başlık
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(20, 24))

        ctk.CTkLabel(
            header,
            text="🚀",
            font=("", 26),
            text_color=theme.ACCENT_BLUE,
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text="Pro Downloader",
            font=(theme.FONT_FAMILY, 14, "bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left", padx=(10, 0))

        # Üst separator
        ctk.CTkFrame(self, height=1, fg_color=theme.BORDER_SUBTLE).pack(
            fill="x", padx=16, pady=(0, 12)
        )

        # Ana menü
        nav_items = [
            ("video",    "🎬", "Video İndirici"),
            ("torrent",  "🧲", "Torrent"),
            ("game",     "🎮", "Oyun İndirici"),
            ("hosting",  "☁",  "Dosya İndirici"),
            ("active",   "📥", "Aktif İndirmeler"),
        ]

        for key, icon, label in nav_items:
            item = SidebarItem(
                self, icon, label,
                command=lambda k=key: self._on_click(k),
                is_active=(key == "video"),
            )
            self.items[key] = item

        # Boşluk doldurucu
        ctk.CTkFrame(self, fg_color="transparent").pack(fill="both", expand=True)

        # Alt separator
        ctk.CTkFrame(self, height=1, fg_color=theme.BORDER_SUBTLE).pack(
            fill="x", padx=16, pady=(0, 8)
        )

        # Alt menü
        bottom_items = [
            ("log",      "📋", "Log"),
            ("settings", "⚙",  "Ayarlar"),
        ]
        for key, icon, label in bottom_items:
            item = SidebarItem(
                self, icon, label,
                command=lambda k=key: self._on_click(k),
            )
            self.items[key] = item

        # Versiyon
        ctk.CTkLabel(
            self,
            text="v1.0.0",
            font=theme.FONT_TINY,
            text_color=theme.TEXT_MUTED,
        ).pack(pady=(8, 12))

    def _on_click(self, key: str) -> None:
        # Log sayfaya geçmez — aktif durumu değişmez
        if key != "log":
            for k, item in self.items.items():
                item.set_active(k == key)
        self.on_navigate(key)

    def set_active(self, key: str) -> None:
        """Dışarıdan aktif sekmeyi güncelle (programatik navigasyon için)."""
        if key != "log":
            for k, item in self.items.items():
                item.set_active(k == key)
