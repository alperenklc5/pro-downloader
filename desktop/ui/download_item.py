"""Tek bir indirme satırı bileşeni."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import customtkinter as ctk

from core import ProgressInfo
from core.torrent.downloader import TorrentProgress
from desktop.ui import theme
from desktop.utils import file_utils


class DownloadItem(ctk.CTkFrame):
    """
    İndirme kuyruğundaki tek bir öğeyi gösterir.

    Durumlar: bekliyor → indiriliyor → tamamlandı / hata / iptal edildi
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        title: str,
        on_cancel: Callable[[], None],
        on_subtitle=None,
        on_pause=None,
        on_resume=None,
    ) -> None:
        super().__init__(
            master,
            corner_radius=theme.CORNER_RADIUS,
            fg_color=theme.COLOR_BG_SECONDARY,
        )
        self.title = title
        self.on_cancel = on_cancel
        self._on_subtitle = on_subtitle
        self._on_pause = on_pause
        self._on_resume = on_resume
        self._is_paused = False
        self._error_flag = False
        self._video_path: Path | None = None
        self.completed_path: Path | None = None
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)

        # Başlık
        self.title_label = ctk.CTkLabel(
            self,
            text=self.title,
            font=theme.FONT_BODY,
            anchor="w",
            justify="left",
            wraplength=580,
        )
        self.title_label.grid(
            row=0, column=0,
            sticky="ew",
            padx=theme.PADDING_MEDIUM,
            pady=(theme.PADDING_MEDIUM, 0),
        )

        # İlerleme çubuğu
        self.progress = ctk.CTkProgressBar(self, height=8, corner_radius=4)
        self.progress.set(0)
        self.progress.grid(
            row=1, column=0,
            sticky="ew",
            padx=theme.PADDING_MEDIUM,
            pady=(theme.PADDING_SMALL, 0),
        )

        # Durum metni
        self.status_label = ctk.CTkLabel(
            self,
            text="Bekliyor...",
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_TEXT_MUTED,
            anchor="w",
        )
        self.status_label.grid(
            row=2, column=0,
            sticky="ew",
            padx=theme.PADDING_MEDIUM,
            pady=(theme.PADDING_SMALL, theme.PADDING_MEDIUM),
        )

        # Aksiyon butonları (sağ sütun)
        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.grid(
            row=0, column=1,
            rowspan=3,
            padx=theme.PADDING_MEDIUM,
            pady=theme.PADDING_MEDIUM,
        )

        # Pause butonu (yalnızca torrent indirmelerde kullanılır)
        self._pause_btn = ctk.CTkButton(
            self.action_frame,
            text="⏸ Duraklat",
            width=90,
            height=32,
            fg_color="#1565c0",
            hover_color="#0d47a1",
            font=theme.FONT_SMALL,
            command=self._toggle_pause,
        )
        # Başta gizli; update_torrent_progress ilk çağrısında gösterilir
        self._pause_btn_visible = False

        self.cancel_btn = ctk.CTkButton(
            self.action_frame,
            text="İptal",
            width=80,
            height=32,
            fg_color=theme.COLOR_ERROR,
            hover_color="#a00000",
            command=self._handle_cancel,
        )
        self.cancel_btn.pack()

    # ------------------------------------------------------------------
    # Durum güncellemeleri
    # ------------------------------------------------------------------

    def update_progress(self, info: ProgressInfo) -> None:
        """İlerleme çubuğunu ve durum metnini günceller."""
        self.progress.set(info.percent / 100)
        speed_mb = info.speed / 1024 / 1024 if info.speed else 0.0
        eta_str = f"{info.eta}s" if info.eta is not None else "?"
        self.status_label.configure(
            text=f"{info.percent:.1f}%  •  {speed_mb:.1f} MB/s  •  {eta_str} kaldı",
            text_color=theme.COLOR_TEXT_MUTED,
        )

    def update_torrent_progress(self, progress: TorrentProgress) -> None:
        """Torrent ilerleme çubuğunu ve durum metnini günceller."""
        # Pause butonunu ilk torrent güncellemesinde göster
        if not self._pause_btn_visible and (self._on_pause or self._on_resume):
            self._pause_btn.pack(pady=(0, 4))
            self._pause_btn_visible = True

        self.progress.set(progress.progress_percent / 100)

        if progress.status == "paused":
            self.progress.configure(progress_color="#ff9800")
            self._pause_btn.configure(text="▶ Devam")
            status_text = f"⏸ Duraklatıldı — {progress.progress_percent:.1f}%"
        elif progress.status == "downloading":
            self.progress.configure(progress_color=theme.COLOR_ACCENT)
            self._pause_btn.configure(text="⏸ Duraklat")
            status_text = (
                f"{progress.progress_percent:.1f}%  •  "
                f"{progress.speed_formatted()}  •  "
                f"⏱ {progress.eta_formatted()}  •  "
                f"💾 {progress.downloaded_formatted()} / {progress.size_formatted()}  •  "
                f"🌱 {progress.seeds} seed"
            )
        elif progress.status == "seeding":
            self.progress.configure(progress_color=theme.COLOR_SUCCESS)
            status_text = f"✓ Tamamlandı — {progress.size_formatted()}"
        else:
            self.progress.configure(progress_color=theme.COLOR_ACCENT)
            status_text = f"{progress.status} — {progress.progress_percent:.1f}%"

        self.status_label.configure(text=status_text, text_color=theme.COLOR_TEXT_MUTED)

    def set_status_text(self, text: str) -> None:
        """Durum metnini doğrudan günceller."""
        self.status_label.configure(text=text)

    def mark_complete(self, path: Path) -> None:
        """Tamamlandı durumuna geçer; 'Aç' ve 'Klasörde Göster' butonlarını ekler."""
        self._video_path = path
        self.completed_path = path
        self.progress.set(1.0)
        self.progress.configure(progress_color=theme.COLOR_SUCCESS)
        self.status_label.configure(
            text=f"✓  {path.name}",
            text_color=theme.COLOR_SUCCESS,
        )
        self._replace_actions([
            ("Aç", lambda: file_utils.open_file(path)),
            ("Klasör", lambda: file_utils.reveal_in_folder(path)),
        ])
        if self._on_subtitle:
            self._show_subtitle_btn()

    def _show_subtitle_btn(self):
        """Altyazı indirme butonu göster."""
        if hasattr(self, "_subtitle_btn"):
            return
        self._subtitle_btn = ctk.CTkButton(
            self.action_frame,
            text="Altyazi",
            width=80,
            height=32,
            command=self._on_subtitle_click,
            fg_color="#1565c0",
            hover_color="#0d47a1",
            font=theme.FONT_SMALL,
        )
        self._subtitle_btn.pack(pady=2)

    def _on_subtitle_click(self):
        """Altyazı butonuna basıldı."""
        if self._on_subtitle:
            self._subtitle_btn.configure(text="Aranıyor...", state="disabled")
            self._on_subtitle(self._video_path)

    def set_subtitle_result(self, found: bool, count: int = 0):
        """Altyazı sonucunu göster."""
        if not hasattr(self, "_subtitle_btn"):
            return
        if found:
            self._subtitle_btn.configure(
                text=f"✓ {count} altyazi",
                fg_color=theme.COLOR_SUCCESS,
                state="disabled",
            )
        else:
            self._subtitle_btn.configure(
                text="✗ Bulunamadi",
                fg_color=theme.COLOR_ERROR,
                state="normal",
            )

    def mark_error(self, error: Exception) -> None:
        """Hata durumuna geçer."""
        self._error_flag = True
        self.progress.configure(progress_color=theme.COLOR_ERROR)
        self.status_label.configure(
            text=f"✗  {error}",
            text_color=theme.COLOR_ERROR,
        )
        self._replace_actions([])

    def mark_cancelled(self) -> None:
        """İptal durumunu gösterir."""
        self.progress.set(0)
        self.status_label.configure(
            text="✕ İptal edildi",
            text_color=theme.COLOR_WARNING,
        )
        if self._pause_btn_visible:
            self._pause_btn.pack_forget()
            self._pause_btn_visible = False
        self._replace_actions([])

    # ------------------------------------------------------------------
    # Yardımcılar
    # ------------------------------------------------------------------

    def _toggle_pause(self) -> None:
        """Pause/Resume toggle."""
        if self._is_paused:
            self._is_paused = False
            self._pause_btn.configure(text="⏸ Duraklat")
            if self._on_resume:
                self._on_resume()
        else:
            self._is_paused = True
            self._pause_btn.configure(text="▶ Devam")
            if self._on_pause:
                self._on_pause()

    def _handle_cancel(self) -> None:
        self.cancel_btn.configure(state="disabled", text="İptal ediliyor...")
        self.on_cancel()

    def _replace_actions(self, actions: list[tuple[str, Callable[[], None]]]) -> None:
        """Aksiyon frame'ini yeni butonlarla doldurur."""
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        for label, cmd in actions:
            ctk.CTkButton(
                self.action_frame,
                text=label,
                width=80,
                height=32,
                command=cmd,
            ).pack(pady=2)
