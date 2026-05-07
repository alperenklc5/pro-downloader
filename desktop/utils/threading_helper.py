"""Thread-safe UI güncelleme yardımcısı."""

from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk


def run_on_ui(widget: ctk.CTkBaseClass, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """
    Background thread'den UI güncellemesi yapar.

    widget.after(0, ...) ile Tkinter'ın event loop'unda çalışır,
    thread güvenliğini sağlar.

    Args:
        widget: Herhangi bir CustomTkinter widget.
        func: UI thread'inde çağrılacak fonksiyon.
        *args: Fonksiyona geçirilecek argümanlar.
        **kwargs: Fonksiyona geçirilecek keyword argümanlar.
    """
    widget.after(0, lambda: func(*args, **kwargs))
