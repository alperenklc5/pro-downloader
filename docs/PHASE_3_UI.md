# Faz 3: Profesyonel UI Yenileme (Desktop)

## Hedef
Pro Downloader'ın arayüzünü profesyonel indirme programları (IDM, JDownloader, qBittorrent, Stremio) kalitesinde yenilemek. Sekme bazlı yapı, modern tasarım, insan elinden çıkmış hissi.

## Mevcut Durum vs Hedef

### Mevcut
- Tek ekran, her şey üst üste
- URL input + indirme listesi aynı yerde
- Torrent sonuçları ayrı popup
- Basit CustomTkinter default görünümü
- Profesyonel değil, prototip hissi

### Hedef
- Sekmeli yapı (Tab bar)
- Modern, koyu tema (JDownloader/qBittorrent benzeri)
- Sol sidebar + ana içerik alanı
- Profesyonel ikonlar ve tipografi
- Smooth geçişler ve hover efektleri
- İnsan elinden çıkmış, AI slop olmayan tasarım

## Tasarım Kararları

### Renk Paleti — "Midnight Ocean" Teması
```python
# Ana renkler
BG_PRIMARY = "#0f1923"        # Koyu lacivert - ana arka plan
BG_SECONDARY = "#1a2736"      # Biraz açık - kartlar, sidebar
BG_TERTIARY = "#243447"       # Hover, aktif sekme
BG_ELEVATED = "#2d3e50"       # Popup, dialog arka planı

# Accent renkler
ACCENT_BLUE = "#3b82f6"       # Ana aksiyon rengi
ACCENT_GREEN = "#10b981"      # Başarı, tamamlandı
ACCENT_ORANGE = "#f59e0b"     # Uyarı, duraklatıldı
ACCENT_RED = "#ef4444"        # Hata, iptal
ACCENT_PURPLE = "#8b5cf6"     # Torrent/özel

# Text renkler
TEXT_PRIMARY = "#e2e8f0"      # Ana metin
TEXT_SECONDARY = "#94a3b8"    # İkincil metin
TEXT_MUTED = "#64748b"        # Soluk metin
TEXT_ACCENT = "#60a5fa"       # Link, vurgulu metin

# Border
BORDER_DEFAULT = "#1e3a5f"    # Varsayılan kenarlık
BORDER_HOVER = "#3b82f6"      # Hover kenarlık
```

### Tipografi
```python
# Font ailesi
FONT_FAMILY = "Segoe UI"       # Windows native, temiz
FONT_FAMILY_MONO = "Cascadia Code"  # Log penceresi, teknik

# Boyutlar
FONT_TITLE = (FONT_FAMILY, 20, "bold")     # Sayfa başlıkları
FONT_SUBTITLE = (FONT_FAMILY, 14, "bold")  # Alt başlıklar
FONT_BODY = (FONT_FAMILY, 12)              # Normal metin
FONT_SMALL = (FONT_FAMILY, 10)             # Küçük metin
FONT_TINY = (FONT_FAMILY, 9)               # Çok küçük (status bar)
FONT_MONO = (FONT_FAMILY_MONO, 11)         # Log penceresi
```

### İkonlar (Unicode)
```python
ICONS = {
    "download": "⬇",
    "torrent": "🧲",
    "game": "🎮",
    "settings": "⚙",
    "log": "📋",
    "search": "🔍",
    "pause": "⏸",
    "resume": "▶",
    "cancel": "✕",
    "complete": "✓",
    "error": "✗",
    "folder": "📁",
    "subtitle": "🔤",
    "video": "🎬",
    "music": "🎵",
    "link": "🔗",
    "magnet": "🧲",
    "seed": "🌱",
    "speed": "⚡",
    "time": "⏱",
    "size": "💾",
    "info": "ℹ",
    "warning": "⚠",
    "star": "⭐",
}
```

## Ana Yapı — Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  🔻 Pro Downloader                              ─ □ ✕             │
├────────┬────────────────────────────────────────────────────────────┤
│        │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                     │
│  SIDE  │  │ Video│ │Torrent│ │ Oyun │ │Aktif │           ⚙  📋    │
│  BAR   │  └──────┘ └──────┘ └──────┘ └──────┘                     │
│        ├────────────────────────────────────────────────────────────┤
│ ⬇ Video│                                                           │
│ 🧲 Torr│  [Ana İçerik Alanı — seçili sekmeye göre değişir]        │
│ 🎮 Oyun│                                                           │
│ 📋 Log │                                                           │
│ ⚙ Ayar │                                                           │
│        │                                                           │
│        │                                                           │
│        │                                                           │
│────────│                                                           │
│ v1.0   │                                                           │
│ 3 aktif│                                                           │
├────────┴────────────────────────────────────────────────────────────┤
│ Status Bar: 2 indirme aktif | ⬇ 4.2 MB/s | 💾 124 GB boş alan    │
└─────────────────────────────────────────────────────────────────────┘
```

## Görev 1: `desktop/ui/theme.py` — Tema Sistemi (Tam Yenile)

```python
"""Pro Downloader UI teması — Midnight Ocean."""

# ─── Renkler ───────────────────────────────────────────
BG_PRIMARY = "#0f1923"
BG_SECONDARY = "#1a2736"
BG_TERTIARY = "#243447"
BG_ELEVATED = "#2d3e50"
BG_INPUT = "#162232"

ACCENT_BLUE = "#3b82f6"
ACCENT_BLUE_HOVER = "#2563eb"
ACCENT_GREEN = "#10b981"
ACCENT_GREEN_HOVER = "#059669"
ACCENT_ORANGE = "#f59e0b"
ACCENT_ORANGE_HOVER = "#d97706"
ACCENT_RED = "#ef4444"
ACCENT_RED_HOVER = "#dc2626"
ACCENT_PURPLE = "#8b5cf6"

TEXT_PRIMARY = "#e2e8f0"
TEXT_SECONDARY = "#94a3b8"
TEXT_MUTED = "#64748b"
TEXT_ACCENT = "#60a5fa"

BORDER_DEFAULT = "#1e3a5f"
BORDER_HOVER = "#3b82f6"
BORDER_SUBTLE = "#1a2f45"

# ─── Eski Değişken İsimleri (Geriye Uyum) ──────────────
COLOR_BG_PRIMARY = BG_PRIMARY
COLOR_BG_SECONDARY = BG_SECONDARY
COLOR_BG_TERTIARY = BG_TERTIARY
COLOR_TEXT_PRIMARY = TEXT_PRIMARY
COLOR_TEXT_MUTED = TEXT_SECONDARY
COLOR_ACCENT = ACCENT_BLUE
COLOR_ACCENT_HOVER = ACCENT_BLUE_HOVER
COLOR_SUCCESS = ACCENT_GREEN
COLOR_WARNING = ACCENT_ORANGE
COLOR_ERROR = ACCENT_RED

# ─── Font ──────────────────────────────────────────────
FONT_FAMILY = "Segoe UI"
FONT_FAMILY_MONO = "Cascadia Code"

FONT_TITLE = (FONT_FAMILY, 20, "bold")
FONT_SUBTITLE = (FONT_FAMILY, 14, "bold")
FONT_BODY = (FONT_FAMILY, 12)
FONT_BODY_BOLD = (FONT_FAMILY, 12, "bold")
FONT_SMALL = (FONT_FAMILY, 10)
FONT_TINY = (FONT_FAMILY, 9)
FONT_MONO = (FONT_FAMILY_MONO, 11)

# ─── Boyutlar ──────────────────────────────────────────
CORNER_RADIUS = 8
CORNER_RADIUS_SMALL = 4
CORNER_RADIUS_LARGE = 12

SIDEBAR_WIDTH = 200
SIDEBAR_WIDTH_COLLAPSED = 56  # Sadece ikon
STATUS_BAR_HEIGHT = 32
TAB_HEIGHT = 40

PADDING_SMALL = 4
PADDING_MEDIUM = 8
PADDING_LARGE = 16
PADDING_XL = 24

# ─── Animasyon ─────────────────────────────────────────
ANIMATION_DURATION_MS = 200
HOVER_TRANSITION_MS = 150
```

## Görev 2: `desktop/ui/sidebar.py` — Sol Sidebar (Yeni Dosya)

```python
"""Sol sidebar navigasyon."""
import customtkinter as ctk
from desktop.ui import theme


class SidebarItem:
    """Tek bir sidebar menü öğesi."""
    def __init__(self, parent, icon: str, label: str, command=None, is_active=False):
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

        ctk.CTkLabel(
            inner,
            text=label,
            font=theme.FONT_BODY,
            text_color=theme.TEXT_PRIMARY if is_active else theme.TEXT_SECONDARY,
        ).pack(side="left", padx=(12, 0))

        # Hover efekti
        self.frame.bind("<Enter>", lambda e: self.frame.configure(
            fg_color=theme.BG_TERTIARY
        ))
        self.frame.bind("<Leave>", lambda e: self.frame.configure(
            fg_color=theme.BG_TERTIARY if is_active else "transparent"
        ))
        
        if command:
            self.frame.bind("<Button-1>", lambda e: command())
            inner.bind("<Button-1>", lambda e: command())
            for child in inner.winfo_children():
                child.bind("<Button-1>", lambda e: command())

    def set_active(self, active: bool):
        self.frame.configure(
            fg_color=theme.BG_TERTIARY if active else "transparent"
        )


class Sidebar(ctk.CTkFrame):
    """Sol navigasyon sidebar."""
    def __init__(self, master, on_navigate):
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

    def _build(self):
        # Logo/Başlık
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(20, 24))

        ctk.CTkLabel(
            header,
            text="⬇",
            font=("", 28),
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text="Pro Downloader",
            font=(theme.FONT_FAMILY, 15, "bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left", padx=(10, 0))

        # Separator
        ctk.CTkFrame(self, height=1, fg_color=theme.BORDER_SUBTLE).pack(
            fill="x", padx=16, pady=(0, 12)
        )

        # Menü öğeleri
        nav_items = [
            ("video", "🎬", "Video İndirici"),
            ("torrent", "🧲", "Torrent"),
            ("game", "🎮", "Oyun İndirici"),
            ("active", "⬇", "Aktif İndirmeler"),
        ]

        for key, icon, label in nav_items:
            item = SidebarItem(
                self, icon, label,
                command=lambda k=key: self._on_click(k),
                is_active=(key == "video"),
            )
            self.items[key] = item

        # Alt kısım — boşluk doldurucu
        spacer = ctk.CTkFrame(self, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        # Separator
        ctk.CTkFrame(self, height=1, fg_color=theme.BORDER_SUBTLE).pack(
            fill="x", padx=16, pady=(0, 8)
        )

        # Alt menü
        bottom_items = [
            ("log", "📋", "Log"),
            ("settings", "⚙", "Ayarlar"),
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

    def _on_click(self, key: str):
        # Tüm öğeleri deaktif yap
        for k, item in self.items.items():
            item.set_active(k == key)
        self.on_navigate(key)
```

## Görev 3: `desktop/ui/status_bar.py` — Alt Durum Çubuğu (Yeni Dosya)

```python
"""Alt durum çubuğu — aktif indirme sayısı, hız, boş alan."""
import shutil
import customtkinter as ctk
from desktop.ui import theme


class StatusBar(ctk.CTkFrame):
    """Alt durum çubuğu."""
    def __init__(self, master):
        super().__init__(
            master,
            height=theme.STATUS_BAR_HEIGHT,
            fg_color=theme.BG_SECONDARY,
            corner_radius=0,
        )
        self.pack_propagate(False)
        self._build()

    def _build(self):
        # Sol: aktif indirme sayısı
        self.active_label = ctk.CTkLabel(
            self,
            text="0 aktif indirme",
            font=theme.FONT_TINY,
            text_color=theme.TEXT_MUTED,
        )
        self.active_label.pack(side="left", padx=16)

        # Orta: hız
        self.speed_label = ctk.CTkLabel(
            self,
            text="⬇ 0 B/s",
            font=theme.FONT_TINY,
            text_color=theme.TEXT_MUTED,
        )
        self.speed_label.pack(side="left", padx=16)

        # Sağ: disk alanı
        self.disk_label = ctk.CTkLabel(
            self,
            text="",
            font=theme.FONT_TINY,
            text_color=theme.TEXT_MUTED,
        )
        self.disk_label.pack(side="right", padx=16)
        self._update_disk()

    def _update_disk(self):
        try:
            usage = shutil.disk_usage("C:\\")
            free_gb = usage.free / (1024**3)
            self.disk_label.configure(text=f"💾 {free_gb:.0f} GB boş alan")
        except Exception:
            pass

    def update(self, active_count: int = 0, total_speed: float = 0):
        self.active_label.configure(text=f"{active_count} aktif indirme")
        if total_speed > 1_000_000:
            speed_str = f"⬇ {total_speed/1_000_000:.1f} MB/s"
        elif total_speed > 1_000:
            speed_str = f"⬇ {total_speed/1_000:.0f} KB/s"
        else:
            speed_str = f"⬇ {total_speed:.0f} B/s"
        self.speed_label.configure(text=speed_str)
        self._update_disk()
```

## Görev 4: `desktop/ui/pages/video_page.py` — Video Sekmesi (Yeni Dosya)

```python
"""Video indirici sekmesi — URL yapıştır, bilgi al, indir."""
import customtkinter as ctk
from desktop.ui import theme


class VideoPage(ctk.CTkFrame):
    """Video indirme sayfası."""
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self):
        # Sayfa başlığı
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=theme.PADDING_XL, pady=(theme.PADDING_XL, theme.PADDING_LARGE))

        ctk.CTkLabel(
            header,
            text="🎬 Video İndirici",
            font=theme.FONT_TITLE,
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text="URL yapıştır, format seç, indir",
            font=theme.FONT_SMALL,
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=(16, 0))

        # URL Input Card
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

        # URL input
        self.url_entry = ctk.CTkEntry(
            inner,
            placeholder_text="Video URL'si yapıştır veya film/dizi adı yaz...",
            font=theme.FONT_BODY,
            height=44,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER_DEFAULT,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.CORNER_RADIUS,
        )
        self.url_entry.pack(fill="x", pady=(0, theme.PADDING_MEDIUM))

        # Buton satırı
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
            corner_radius=theme.CORNER_RADIUS,
            command=self._paste,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row,
            text="🔍 Bilgi Al",
            font=theme.FONT_BODY_BOLD,
            width=140,
            height=38,
            fg_color=theme.ACCENT_BLUE,
            hover_color=theme.ACCENT_BLUE_HOVER,
            corner_radius=theme.CORNER_RADIUS,
            command=self._fetch,
        ).pack(side="left")

        # Format seçimi (başta gizli, bilgi gelince görünür)
        self.format_frame = ctk.CTkFrame(
            self,
            fg_color=theme.BG_SECONDARY,
            corner_radius=theme.CORNER_RADIUS_LARGE,
            border_width=1,
            border_color=theme.BORDER_DEFAULT,
        )
        # pack() bilgi gelince çağrılacak

        # İndirme listesi başlığı
        ctk.CTkLabel(
            self,
            text="İndirmeler",
            font=theme.FONT_SUBTITLE,
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", padx=theme.PADDING_XL, pady=(theme.PADDING_LARGE, theme.PADDING_SMALL))

        # İndirme listesi
        self.download_list = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
        )
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

    def _fetch(self):
        url = self.url_entry.get().strip()
        if url:
            self.app._on_fetch(url)
```

## Görev 5: `desktop/ui/pages/torrent_page.py` — Torrent Sekmesi (Yeni Dosya)

```python
"""Torrent arama sekmesi — film/dizi adı yaz, torrent bul, indir."""
import customtkinter as ctk
from desktop.ui import theme


class TorrentPage(ctk.CTkFrame):
    """Torrent arama sayfası."""
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self):
        # Başlık
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=theme.PADDING_XL, pady=(theme.PADDING_XL, theme.PADDING_LARGE))

        ctk.CTkLabel(
            header,
            text="🧲 Torrent Arama",
            font=theme.FONT_TITLE,
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        # Arama Card
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

        # Arama input
        self.search_entry = ctk.CTkEntry(
            inner,
            placeholder_text="Film veya dizi adı yaz... (ör: Game of Thrones S03E07)",
            font=theme.FONT_BODY,
            height=44,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER_DEFAULT,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.CORNER_RADIUS,
        )
        self.search_entry.pack(fill="x", pady=(0, theme.PADDING_MEDIUM))
        self.search_entry.bind("<Return>", lambda e: self._search())

        # Filtre satırı
        filter_row = ctk.CTkFrame(inner, fg_color="transparent")
        filter_row.pack(fill="x")

        # Kategori filtresi
        self.category_var = ctk.StringVar(value="Tümü")
        ctk.CTkSegmentedButton(
            filter_row,
            values=["Tümü", "Film", "Dizi"],
            variable=self.category_var,
            font=theme.FONT_SMALL,
            fg_color=theme.BG_TERTIARY,
            selected_color=theme.ACCENT_BLUE,
            selected_hover_color=theme.ACCENT_BLUE_HOVER,
        ).pack(side="left")

        ctk.CTkButton(
            filter_row,
            text="🔍 Ara",
            font=theme.FONT_BODY_BOLD,
            width=100,
            height=36,
            fg_color=theme.ACCENT_PURPLE,
            hover_color="#7c3aed",
            corner_radius=theme.CORNER_RADIUS,
            command=self._search,
        ).pack(side="right")

        # Sonuç listesi
        self.results_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            label_text="Sonuçlar",
            label_font=theme.FONT_SUBTITLE,
            label_text_color=theme.TEXT_SECONDARY,
        )
        self.results_frame.pack(
            fill="both", expand=True,
            padx=theme.PADDING_XL, pady=(0, theme.PADDING_MEDIUM)
        )

        # Boş durum
        self.empty_label = ctk.CTkLabel(
            self.results_frame,
            text="🔍 Bir şey arayarak başlayın",
            font=theme.FONT_BODY,
            text_color=theme.TEXT_MUTED,
        )
        self.empty_label.pack(pady=40)

    def _search(self):
        query = self.search_entry.get().strip()
        if not query:
            return
        
        category = self.category_var.get()
        content_type = {"Tümü": "unknown", "Film": "movie", "Dizi": "series"}[category]
        
        # ContentInfo oluştur ve torrent dialog aç
        from core.torrent.detector import ContentInfo
        content_info = ContentInfo(
            name=query,
            content_type=content_type,
            original_url=query,
        )
        self.app._open_torrent_dialog(content_info)
```

## Görev 6: `desktop/ui/pages/game_page.py` — Oyun Sekmesi (Yeni Dosya)

```python
"""Oyun indirici sekmesi."""
import customtkinter as ctk
from desktop.ui import theme


class GamePage(ctk.CTkFrame):
    """Oyun indirme sayfası."""
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=theme.PADDING_XL, pady=(theme.PADDING_XL, theme.PADDING_LARGE))

        ctk.CTkLabel(
            header,
            text="🎮 Oyun İndirici",
            font=theme.FONT_TITLE,
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        # Arama Card
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

        self.search_entry = ctk.CTkEntry(
            inner,
            placeholder_text="Oyun adı yaz... (ör: Forza Horizon 5, GTA V)",
            font=theme.FONT_BODY,
            height=44,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER_DEFAULT,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.CORNER_RADIUS,
        )
        self.search_entry.pack(fill="x", pady=(0, theme.PADDING_MEDIUM))
        self.search_entry.bind("<Return>", lambda e: self._search())

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x")

        # Platform filtresi
        self.platform_var = ctk.StringVar(value="PC")
        ctk.CTkSegmentedButton(
            btn_row,
            values=["PC"],
            variable=self.platform_var,
            font=theme.FONT_SMALL,
            fg_color=theme.BG_TERTIARY,
            selected_color=theme.ACCENT_BLUE,
        ).pack(side="left")

        ctk.CTkButton(
            btn_row,
            text="🔍 Ara",
            font=theme.FONT_BODY_BOLD,
            width=100,
            height=36,
            fg_color=theme.ACCENT_GREEN,
            hover_color=theme.ACCENT_GREEN_HOVER,
            corner_radius=theme.CORNER_RADIUS,
            command=self._search,
        ).pack(side="right")

        # Sonuç listesi
        self.results_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            label_text="Sonuçlar",
            label_font=theme.FONT_SUBTITLE,
        )
        self.results_frame.pack(
            fill="both", expand=True,
            padx=theme.PADDING_XL, pady=(0, theme.PADDING_MEDIUM)
        )

        self.empty_label = ctk.CTkLabel(
            self.results_frame,
            text="🎮 Oyun arayarak başlayın\n\n💡 FitGirl Repack'ler otomatik önce sıralanır",
            font=theme.FONT_BODY,
            text_color=theme.TEXT_MUTED,
        )
        self.empty_label.pack(pady=40)

    def _search(self):
        query = self.search_entry.get().strip()
        if not query:
            return
        self.app._open_game_search_with_query(query)
```

## Görev 7: `desktop/ui/pages/active_page.py` — Aktif İndirmeler Sekmesi (Yeni Dosya)

```python
"""Aktif indirmeler sayfası — tüm indirmeleri tek yerde göster."""
import customtkinter as ctk
from desktop.ui import theme


class ActiveDownloadsPage(ctk.CTkFrame):
    """Tüm aktif indirmeler — video + torrent + oyun."""
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=theme.PADDING_XL, pady=(theme.PADDING_XL, theme.PADDING_LARGE))

        ctk.CTkLabel(
            header,
            text="⬇ Aktif İndirmeler",
            font=theme.FONT_TITLE,
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        # İstatistik kartları
        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.pack(fill="x", padx=theme.PADDING_XL, pady=(0, theme.PADDING_LARGE))

        for label, icon, color in [
            ("Aktif", "⬇", theme.ACCENT_BLUE),
            ("Duraklatılmış", "⏸", theme.ACCENT_ORANGE),
            ("Tamamlanan", "✓", theme.ACCENT_GREEN),
            ("Hatalı", "✗", theme.ACCENT_RED),
        ]:
            stat_card = ctk.CTkFrame(
                stats,
                fg_color=theme.BG_SECONDARY,
                corner_radius=theme.CORNER_RADIUS,
                border_width=1,
                border_color=theme.BORDER_DEFAULT,
            )
            stat_card.pack(side="left", fill="x", expand=True, padx=4)

            ctk.CTkLabel(
                stat_card,
                text=f"{icon} {label}",
                font=theme.FONT_SMALL,
                text_color=theme.TEXT_SECONDARY,
            ).pack(padx=12, pady=(8, 0))

            ctk.CTkLabel(
                stat_card,
                text="0",
                font=theme.FONT_TITLE,
                text_color=color,
            ).pack(padx=12, pady=(0, 8))

        # İndirme listesi
        self.download_list = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
        )
        self.download_list.pack(
            fill="both", expand=True,
            padx=theme.PADDING_XL, pady=(0, theme.PADDING_MEDIUM)
        )
```

## Görev 8: `desktop/app.py` — Ana Uygulama Yenile

```python
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Pro Downloader")
        self.geometry("1100x700")
        self.minsize(900, 600)

        # Tema ayarla
        ctk.set_appearance_mode("dark")

        # Config yükle
        self.config_obj = AppConfig.load()
        # ... environment set etme kodu ...

        self._build_ui()
        self.log_window = LogWindow(self)

    def _build_ui(self):
        # Ana container
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sol Sidebar
        self.sidebar = Sidebar(self, on_navigate=self._navigate)
        self.sidebar.grid(row=0, column=0, sticky="ns")

        # Sağ İçerik Alanı
        content = ctk.CTkFrame(self, fg_color=theme.BG_PRIMARY, corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        # Sayfalar
        self.pages = {}
        self.pages["video"] = VideoPage(content, self)
        self.pages["torrent"] = TorrentPage(content, self)
        self.pages["game"] = GamePage(content, self)
        self.pages["active"] = ActiveDownloadsPage(content, self)

        # Varsayılan sayfa
        self.current_page = "video"
        self.pages["video"].grid(row=0, column=0, sticky="nsew")

        # Status Bar
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")

    def _navigate(self, page_key: str):
        """Sayfa değiştir."""
        if page_key == "log":
            self.log_window.toggle()
            return
        if page_key == "settings":
            self._open_settings()
            return

        # Mevcut sayfayı gizle
        if self.current_page in self.pages:
            self.pages[self.current_page].grid_forget()

        # Yeni sayfayı göster
        if page_key in self.pages:
            self.pages[page_key].grid(row=0, column=0, sticky="nsew")
            self.current_page = page_key
```

## Görev 9: `desktop/ui/pages/__init__.py`

```python
from desktop.ui.pages.video_page import VideoPage
from desktop.ui.pages.torrent_page import TorrentPage
from desktop.ui.pages.game_page import GamePage
from desktop.ui.pages.active_page import ActiveDownloadsPage
```

## Görev 10: Mevcut Fonksiyonları Koruma (Önemli!)

**DİKKAT:** Mevcut çalışan fonksiyonları bozmayın!

Korunması gereken fonksiyonlar:
- `_on_fetch()` — URL'den bilgi alma
- `_on_extract_error()` — Torrent fallback
- `_start_torrent_download()` — Torrent indirme
- `_open_torrent_dialog()` — Torrent dialog
- `_open_game_search()` — Oyun arama
- `on_subtitle_request()` — Altyazı indirme
- `_on_closing()` — Uygulama kapanma

Bu fonksiyonlar olduğu gibi kalmalı, sadece UI bağlantıları yeni sayfalara yönlendirilmeli.

## Kabul Kriterleri

1. ✅ Sol sidebar'da navigasyon çalışıyor (Video, Torrent, Oyun, Aktif İndirmeler, Log, Ayarlar)
2. ✅ Her sekmenin kendi sayfası var, bağımsız çalışıyor
3. ✅ Video sekmesi: URL yapıştır → bilgi al → indir (eski gibi çalışıyor)
4. ✅ Torrent sekmesi: Film/dizi adı yaz → ara → sonuçlar gelir → indir
5. ✅ Oyun sekmesi: Oyun adı yaz → ara → sonuçlar → indir
6. ✅ Aktif İndirmeler: Tüm indirmeler tek yerde (video + torrent + oyun)
7. ✅ Alt durum çubuğu: Aktif indirme sayısı, toplam hız, boş disk alanı
8. ✅ Midnight Ocean koyu tema tutarlı
9. ✅ Mevcut fonksiyonlar (indirme, altyazı, torrent, oyun) hâlâ çalışıyor
10. ✅ Hover efektleri ve geçişler smooth

## Humanizer Kontrol Listesi (AI Slop Kaçınma)

❌ Inter, Roboto, Arial font KULLANMA
❌ Mor gradient beyaz üstüne KULLANMA
❌ Generic rounded card + shadow combo KULLANMA
❌ Cookie-cutter dashboard layout KULLANMA

✅ Segoe UI (Windows native, temiz)
✅ Midnight Ocean koyu tema (lacivert tonları)
✅ Keskin accent renkleri (mavi, yeşil, turuncu)
✅ Sidebar + content split (JDownloader/qBittorrent benzeri)
✅ Subtle border + hover efektleri
✅ Tutarlı spacing (8px grid)
✅ Mono font sadece log'da
