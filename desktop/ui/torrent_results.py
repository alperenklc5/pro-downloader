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
        self._results: list[TorrentResult] = []

        self.title("Torrent Alternatifleri")
        self.geometry("600x500")
        self.transient(master)
        self.grab_set()

        self._build()
        self._search()

        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - 600) // 2
        y = master.winfo_y() + (master.winfo_height() - 500) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self) -> None:
        # Başlık
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            header,
            text="Torrent Alternatifleri",
            font=theme.FONT_SUBTITLE,
        ).pack(side="left")

        # İçerik bilgisi
        info_text = self.content_info.name
        if self.content_info.year:
            info_text += f" ({self.content_info.year})"
        ctk.CTkLabel(
            self,
            text=f"Aranan: {info_text}",
            font=theme.FONT_BODY,
            text_color=theme.COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=20, pady=(0, 5))

        ctk.CTkLabel(
            self,
            text=(
                "Bu içerik doğrudan indirilemedi.\n"
                "Aşağıdaki torrent alternatifleri bulundu:"
            ),
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_WARNING,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 10))

        # Loading
        self.loading_label = ctk.CTkLabel(
            self, text="Aranıyor...", font=theme.FONT_BODY
        )
        self.loading_label.pack(pady=20)

        self.progress_bar = ctk.CTkProgressBar(self, mode="indeterminate")
        self.progress_bar.pack(padx=20, fill="x")
        self.progress_bar.start()

        # Sonuç listesi (başta gizli)
        self.results_frame = ctk.CTkScrollableFrame(self, label_text="Sonuçlar")

        # Butonlar
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(10, 20), side="bottom")
        ctk.CTkButton(btn_frame, text="Kapat", command=self.destroy).pack(side="right")

    def _search(self) -> None:
        """Background'da torrent ara."""
        def task():
            results = search_all(
                query=self.content_info.name,
                year=self.content_info.year,
                season=self.content_info.season,
                episode=self.content_info.episode,
                content_type=self.content_info.content_type,
                jackett_url=self.jackett_url,
                jackett_key=self.jackett_key,
            )
            self.after(0, lambda: self._show_results(results))

        threading.Thread(target=task, daemon=True).start()

    def _show_results(self, results: list[TorrentResult]) -> None:
        """Sonuçları göster."""
        self.loading_label.destroy()
        self.progress_bar.stop()
        self.progress_bar.destroy()

        if not results:
            ctk.CTkLabel(
                self,
                text="Torrent bulunamadı.\nFarklı bir arama terimi deneyin.",
                font=theme.FONT_BODY,
                text_color=theme.COLOR_ERROR,
            ).pack(pady=20)
            return

        self.results_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

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

        title_short = result.title[:50] + "..." if len(result.title) > 50 else result.title
        ctk.CTkLabel(
            info, text=title_short,
            font=theme.FONT_BODY,
            anchor="w",
        ).pack(anchor="w")

        seed_color = theme.COLOR_SUCCESS if result.seeds > 0 else theme.COLOR_ERROR
        meta_parts = [
            f"{result.quality}",
            f"{result.size_formatted()}",
            f"{result.seeds} seed",
            f"[{result.source}]",
        ]
        ctk.CTkLabel(
            info,
            text="  |  ".join(meta_parts),
            font=theme.FONT_SMALL,
            text_color=seed_color if result.seeds > 0 else theme.COLOR_TEXT_MUTED,
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
