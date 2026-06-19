"""Oyun indirici sekmesi — sonuçlar inline gösterilir, popup yok."""
from __future__ import annotations

import threading

import customtkinter as ctk

from core.torrent import TorrentResult, search_games, ContentInfo
from desktop.ui import theme


class GamePage(ctk.CTkFrame):
    """Oyun indirme sayfası — inline sonuçlar."""

    def __init__(self, master: ctk.CTkBaseClass, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._content_info: ContentInfo | None = None
        self._searching = False
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self._build()

    # ------------------------------------------------------------------
    # UI inşası
    # ------------------------------------------------------------------

    def _build(self) -> None:
        # ── Başlık ──────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(
            row=0, column=0, sticky="ew",
            padx=theme.PADDING_XL,
            pady=(theme.PADDING_XL, theme.PADDING_LARGE),
        )
        ctk.CTkLabel(
            header,
            text="🎮 Oyun İndirici",
            font=theme.FONT_TITLE,
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")
        ctk.CTkLabel(
            header,
            text="FitGirl, DODI ve diğer repack'ler",
            font=theme.FONT_SMALL,
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=(14, 0))

        # ── Arama kartı ─────────────────────────────────────────────────
        card = ctk.CTkFrame(
            self,
            fg_color=theme.BG_SECONDARY,
            corner_radius=theme.CORNER_RADIUS_LARGE,
            border_width=1,
            border_color=theme.BORDER_DEFAULT,
        )
        card.grid(row=1, column=0, sticky="ew", padx=theme.PADDING_XL)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=theme.PADDING_LARGE, pady=theme.PADDING_LARGE)

        self._search_entry = ctk.CTkEntry(
            inner,
            placeholder_text="Oyun adı yaz... (ör: Forza Horizon 5, GTA V)",
            font=theme.FONT_BODY,
            height=44,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER_DEFAULT,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.CORNER_RADIUS,
        )
        self._search_entry.pack(fill="x", pady=(0, theme.PADDING_MEDIUM))
        self._search_entry.bind("<Return>", lambda _e: self._on_manual_search())

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x")

        self._platform_var = ctk.StringVar(value="PC")
        ctk.CTkSegmentedButton(
            btn_row,
            values=["PC"],
            variable=self._platform_var,
            font=theme.FONT_SMALL,
            fg_color=theme.BG_TERTIARY,
            selected_color=theme.ACCENT_GREEN,
            selected_hover_color=theme.ACCENT_GREEN_HOVER,
            unselected_color=theme.BG_TERTIARY,
            unselected_hover_color=theme.BG_ELEVATED,
        ).pack(side="left")

        self._search_btn = ctk.CTkButton(
            btn_row,
            text="🔍  Ara",
            font=theme.FONT_BODY_BOLD,
            width=110,
            height=36,
            fg_color=theme.ACCENT_GREEN,
            hover_color=theme.ACCENT_GREEN_HOVER,
            corner_radius=theme.CORNER_RADIUS,
            command=self._on_manual_search,
        )
        self._search_btn.pack(side="right")

        # ── Sonuç alanı ─────────────────────────────────────────────────
        results_outer = ctk.CTkFrame(self, fg_color="transparent")
        results_outer.grid(
            row=2, column=0, sticky="nsew",
            padx=theme.PADDING_XL,
            pady=(theme.PADDING_MEDIUM, theme.PADDING_MEDIUM),
        )
        results_outer.columnconfigure(0, weight=1)
        results_outer.rowconfigure(1, weight=1)

        self._status_frame = ctk.CTkFrame(results_outer, fg_color="transparent")
        self._status_frame.grid(row=0, column=0, sticky="ew")

        self._results_frame = ctk.CTkScrollableFrame(
            results_outer,
            fg_color="transparent",
            label_text="Sonuçlar",
            label_font=theme.FONT_SUBTITLE,
            label_text_color=theme.TEXT_SECONDARY,
        )
        self._results_frame.grid(row=1, column=0, sticky="nsew")

        self._hint_label = ctk.CTkLabel(
            self._results_frame,
            text=(
                "🎮  Oyun arayarak başlayın\n\n"
                "💡  FitGirl Repack'ler otomatik önce sıralanır\n"
                "📦  Çok parçalı arşivler tek klasör olarak indirilir"
            ),
            font=theme.FONT_BODY,
            text_color=theme.TEXT_MUTED,
            justify="center",
        )
        self._hint_label.pack(pady=40)

    # ------------------------------------------------------------------
    # Dışarıdan çağrılan API
    # ------------------------------------------------------------------

    def start_game_search(self, query: str) -> None:
        """App tarafından çağrılır — verilen query ile oyun araması başlatır."""
        self._search_entry.delete(0, "end")
        self._search_entry.insert(0, query)
        self._content_info = ContentInfo(
            name=query, content_type="game", original_url=query
        )
        self._clear_and_load()
        self._run_search(query)

    # ------------------------------------------------------------------
    # Arama akışı
    # ------------------------------------------------------------------

    def _on_manual_search(self) -> None:
        if self._searching:
            return
        query = self._search_entry.get().strip()
        if not query:
            return
        self._content_info = ContentInfo(
            name=query, content_type="game", original_url=query
        )
        self._clear_and_load()
        self._run_search(query)

    def _clear_and_load(self) -> None:
        for w in self._status_frame.winfo_children():
            w.destroy()
        for w in self._results_frame.winfo_children():
            w.destroy()

        self._search_btn.configure(state="disabled")
        self._searching = True

        self._loading_label = ctk.CTkLabel(
            self._status_frame,
            text="Aranıyor...",
            font=theme.FONT_SMALL,
            text_color=theme.TEXT_MUTED,
        )
        self._loading_label.pack(side="left", pady=(0, 6))

        self._progress = ctk.CTkProgressBar(
            self._status_frame, mode="indeterminate", height=4
        )
        self._progress.pack(fill="x", pady=(0, 6))
        self._progress.start()

    def _run_search(self, query: str) -> None:
        def task() -> None:
            results = search_games(
                query,
                jackett_url=self.app.config_obj.jackett_url,
                jackett_key=self.app.config_obj.jackett_api_key,
            )
            self.after(0, lambda: self._show_results(results))

        threading.Thread(target=task, daemon=True).start()

    def _show_results(self, results: list[TorrentResult]) -> None:
        self._searching = False
        self._search_btn.configure(state="normal")

        for w in self._status_frame.winfo_children():
            w.destroy()

        if not results:
            ctk.CTkLabel(
                self._status_frame,
                text="✗  Oyun bulunamadı — farklı bir arama terimi deneyin.",
                font=theme.FONT_SMALL,
                text_color=theme.ACCENT_RED,
            ).pack(anchor="w", pady=6)
            return

        ctk.CTkLabel(
            self._status_frame,
            text=f"✓  {len(results)} sonuç bulundu",
            font=theme.FONT_SMALL,
            text_color=theme.ACCENT_GREEN,
        ).pack(anchor="w", pady=(0, 6))

        for result in results:
            self._add_result_row(result)

    def _add_result_row(self, result: TorrentResult) -> None:
        row = ctk.CTkFrame(
            self._results_frame,
            fg_color=theme.BG_SECONDARY,
            corner_radius=theme.CORNER_RADIUS,
            border_width=1,
            border_color=theme.BORDER_SUBTLE,
        )
        row.pack(fill="x", padx=4, pady=3)

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, padx=12, pady=10)

        title_short = result.title[:70] + "…" if len(result.title) > 70 else result.title
        ctk.CTkLabel(
            info,
            text=title_short,
            font=theme.FONT_BODY,
            anchor="w",
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        seed_color = theme.ACCENT_GREEN if result.seeds > 5 else (
            theme.ACCENT_ORANGE if result.seeds > 0 else theme.TEXT_MUTED
        )
        meta_parts = [
            result.quality or "?",
            result.size_formatted(),
            f"🌱 {result.seeds} seed",
            f"[{result.source}]",
        ]
        ctk.CTkLabel(
            info,
            text="  ·  ".join(meta_parts),
            font=theme.FONT_SMALL,
            text_color=seed_color,
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkButton(
            row,
            text="⬇  İndir",
            width=90,
            height=34,
            font=theme.FONT_SMALL,
            fg_color=theme.ACCENT_GREEN,
            hover_color=theme.ACCENT_GREEN_HOVER,
            corner_radius=theme.CORNER_RADIUS,
            command=lambda r=result: self._start_download(r),
        ).pack(side="right", padx=12, pady=10)

    def _start_download(self, result: TorrentResult) -> None:
        content_info = self._content_info or ContentInfo(
            name=result.title, content_type="game", original_url=""
        )
        self.app._start_torrent_download(result, content_info)
        self.app._go_to_page("video")
