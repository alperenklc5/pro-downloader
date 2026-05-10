"""Torrent arama sonuçları dialog'u."""
from __future__ import annotations

import threading
import customtkinter as ctk
from typing import Callable
from core.torrent import TorrentResult, search_all, ContentInfo
from desktop.ui import theme


class TorrentResultsDialog(ctk.CTkToplevel):
    """yt-dlp başarısız olduğunda torrent alternatifleri gösterir."""

    def __init__(
        self,
        master,
        content_info: ContentInfo,
        on_download: Callable[[TorrentResult], None],
        jackett_url: str = "",
        jackett_key: str = "",
    ):
        super().__init__(master)
        self.content_info = content_info
        self.on_download = on_download
        self.jackett_url = jackett_url
        self.jackett_key = jackett_key
        self._searching = False

        self.title("Torrent Alternatifleri")
        self.geometry("620x560")
        self.transient(master)
        self.grab_set()

        self._build()
        self._search()

        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - 620) // 2
        y = master.winfo_y() + (master.winfo_height() - 560) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self) -> None:
        # Başlık
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 6))
        ctk.CTkLabel(
            header,
            text="Torrent Alternatifleri",
            font=theme.FONT_SUBTITLE,
        ).pack(side="left")

        # Uyarı
        ctk.CTkLabel(
            self,
            text="Bu içerik doğrudan indirilemedi. Torrent alternatifleri aranıyor.",
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_WARNING,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 10))

        # Arama kutusu
        search_frame = ctk.CTkFrame(self, fg_color=theme.COLOR_BG_SECONDARY, corner_radius=theme.CORNER_RADIUS)
        search_frame.pack(fill="x", padx=20, pady=(0, 10))
        search_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            search_frame,
            text="Arama:",
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_TEXT_MUTED,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 2))

        self._query_var = ctk.StringVar(value=self.content_info.name)
        self._search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self._query_var,
            font=theme.FONT_BODY,
            placeholder_text="Film veya dizi adı girin...",
        )
        self._search_entry.grid(row=1, column=0, sticky="ew", padx=(10, 6), pady=(0, 10))
        self._search_entry.bind("<Return>", lambda _: self._on_search())

        self._search_btn = ctk.CTkButton(
            search_frame,
            text="Yeniden Ara",
            width=110,
            font=theme.FONT_BODY,
            fg_color=theme.COLOR_ACCENT,
            hover_color=theme.COLOR_ACCENT_HOVER,
            command=self._on_search,
        )
        self._search_btn.grid(row=1, column=1, sticky="e", padx=(0, 10), pady=(0, 10))

        # Durum / yükleme alanı
        self._status_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._status_frame.pack(fill="x", padx=20)

        self.loading_label = ctk.CTkLabel(
            self._status_frame, text="Aranıyor...", font=theme.FONT_BODY
        )
        self.loading_label.pack(pady=(10, 4))

        self.progress_bar = ctk.CTkProgressBar(self._status_frame, mode="indeterminate")
        self.progress_bar.pack(fill="x", pady=(0, 10))
        self.progress_bar.start()

        # Sonuç listesi
        self.results_frame = ctk.CTkScrollableFrame(self, label_text="Sonuçlar")

        # Alt buton
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(8, 16), side="bottom")
        ctk.CTkButton(btn_frame, text="Kapat", command=self.destroy).pack(side="right")

    def _on_search(self) -> None:
        """Yeniden Ara butonuna basıldı."""
        if self._searching:
            return
        query = self._query_var.get().strip()
        if not query:
            return
        self._clear_results()
        self._show_loading()
        self._search(query=query)

    def _search(self, query: str | None = None) -> None:
        """Background'da torrent ara."""
        self._searching = True
        self._search_btn.configure(state="disabled")

        effective_query = query or self.content_info.name

        def task():
            results = search_all(
                query=effective_query,
                year=self.content_info.year if query is None else None,
                season=self.content_info.season if query is None else None,
                episode=self.content_info.episode if query is None else None,
                content_type=self.content_info.content_type if query is None else "unknown",
                jackett_url=self.jackett_url,
                jackett_key=self.jackett_key,
            )
            self.after(0, lambda: self._show_results(results))

        threading.Thread(target=task, daemon=True).start()

    def _show_loading(self) -> None:
        """Yükleme göstergesini göster."""
        self.loading_label = ctk.CTkLabel(
            self._status_frame, text="Aranıyor...", font=theme.FONT_BODY
        )
        self.loading_label.pack(pady=(10, 4))
        self.progress_bar = ctk.CTkProgressBar(self._status_frame, mode="indeterminate")
        self.progress_bar.pack(fill="x", pady=(0, 10))
        self.progress_bar.start()

    def _clear_results(self) -> None:
        """Önceki sonuçları ve yükleme göstergesini temizle."""
        # Yükleme widget'larını kaldır
        for w in self._status_frame.winfo_children():
            w.destroy()
        # Sonuç listesini temizle
        self.results_frame.pack_forget()
        for w in self.results_frame.winfo_children():
            w.destroy()

    def _show_results(self, results: list[TorrentResult]) -> None:
        """Sonuçları göster."""
        self._searching = False
        self._search_btn.configure(state="normal")

        # Yükleme widget'larını kaldır
        for w in self._status_frame.winfo_children():
            w.destroy()

        if not results:
            ctk.CTkLabel(
                self._status_frame,
                text="Torrent bulunamadı. Farklı bir arama terimi deneyin.",
                font=theme.FONT_BODY,
                text_color=theme.COLOR_ERROR,
            ).pack(pady=16)
            return

        self.results_frame.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        for result in results:
            self._add_result_row(result)

    def _add_result_row(self, result: TorrentResult) -> None:
        """Tek bir torrent sonucu satırı."""
        row = ctk.CTkFrame(
            self.results_frame,
            fg_color=theme.COLOR_BG_SECONDARY,
            corner_radius=theme.CORNER_RADIUS,
        )
        row.pack(fill="x", padx=5, pady=4)

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, padx=10, pady=8)

        title_short = result.title[:52] + "..." if len(result.title) > 52 else result.title
        ctk.CTkLabel(
            info, text=title_short,
            font=theme.FONT_BODY,
            anchor="w",
        ).pack(anchor="w")

        meta_parts = [
            result.quality,
            result.size_formatted(),
            f"{result.seeds} seed",
            f"[{result.source}]",
        ]
        ctk.CTkLabel(
            info,
            text="  |  ".join(meta_parts),
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_SUCCESS if result.seeds > 0 else theme.COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkButton(
            row,
            text="Indir",
            width=80,
            command=lambda r=result: self._start_download(r),
            fg_color=theme.COLOR_ACCENT,
            hover_color=theme.COLOR_ACCENT_HOVER,
        ).pack(side="right", padx=10, pady=8)

    def _start_download(self, result: TorrentResult) -> None:
        """İndirme başlat."""
        self.destroy()
        self.on_download(result)
