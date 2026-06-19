"""Scrollable indirme kuyruğu bileşeni."""

from __future__ import annotations

import customtkinter as ctk

from desktop.ui import theme
from desktop.ui.download_item import DownloadItem


class DownloadList(ctk.CTkScrollableFrame):
    """Aktif ve tamamlanmış indirme öğelerini listeler."""

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        super().__init__(
            master,
            corner_radius=theme.CORNER_RADIUS,
            label_text="İndirmeler",
            label_font=theme.FONT_BODY,
        )
        self._items: list[DownloadItem] = []

    def add_item(self, item: DownloadItem) -> None:
        """Listeye yeni bir indirme öğesi ekler."""
        item.pack(fill="x", padx=theme.PADDING_SMALL, pady=theme.PADDING_SMALL)
        self._items.append(item)

    def remove_item(self, item: DownloadItem) -> None:
        """Öğeyi listeden kaldırır."""
        if item in self._items:
            item.destroy()
            self._items.remove(item)

    def clear_completed(self) -> None:
        """Tamamlanmış öğeleri temizler."""
        completed = [i for i in self._items if i.completed_path is not None]
        for item in completed:
            self.remove_item(item)

    def has_items(self) -> bool:
        """Listede herhangi bir öğe var mı?"""
        return len(self._items) > 0

    def get_stats(self) -> tuple[int, int, int, int]:
        """(active, paused, complete, error) sayılarını döndür."""
        active = paused = complete = error = 0
        for item in self._items:
            if item.completed_path is not None:
                complete += 1
            elif item._error_flag:
                error += 1
            elif item._is_paused:
                paused += 1
            else:
                active += 1
        return active, paused, complete, error
