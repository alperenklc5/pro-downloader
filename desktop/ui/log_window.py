"""Uygulama log penceresi - sağ alt köşede toggle edilebilir."""
from __future__ import annotations

import datetime

import customtkinter as ctk

from desktop.ui import theme


class LogWindow(ctk.CTkToplevel):
    """Uygulama loglarını gösteren yüzer pencere."""

    def __init__(self, master):
        super().__init__(master)
        self.title("Log")
        self.geometry("600x300")
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.hide)

        self._position_window()
        self._build()
        self.withdraw()  # Başta gizli

    def _position_window(self):
        """Sağ alt köşeye konumlandır."""
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"600x300+{sw - 620}+{sh - 380}")

    def _build(self):
        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color="transparent", height=32)
        toolbar.pack(fill="x", padx=8, pady=(6, 0))
        toolbar.pack_propagate(False)

        ctk.CTkLabel(
            toolbar,
            text="Uygulama Logları",
            font=theme.FONT_BODY,
        ).pack(side="left")

        ctk.CTkButton(
            toolbar,
            text="Temizle",
            width=70,
            height=24,
            command=self.clear,
            fg_color=theme.COLOR_BG_SECONDARY,
            text_color=theme.COLOR_TEXT_MUTED,
            hover_color=theme.COLOR_BG,
        ).pack(side="right")

        # Log metin alanı
        self.text = ctk.CTkTextbox(
            self,
            font=("Consolas", 11),
            wrap="word",
            state="disabled",
        )
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        # Renk tag'leri
        self.text._textbox.tag_config("info", foreground="#aaaaaa")
        self.text._textbox.tag_config("success", foreground="#4caf50")
        self.text._textbox.tag_config("warning", foreground="#ff9800")
        self.text._textbox.tag_config("error", foreground="#f44336")

    def log(self, message: str, level: str = "info"):
        """Mesaj ekle."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {message}\n"

        self.text.configure(state="normal")
        self.text._textbox.insert("end", line, level)
        self.text.configure(state="disabled")
        self.text._textbox.see("end")

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("0.0", "end")
        self.text.configure(state="disabled")

    def show(self):
        self.deiconify()
        self.lift()
        self.focus()

    def hide(self):
        self.withdraw()

    def toggle(self):
        if self.winfo_viewable():
            self.hide()
        else:
            self.show()
