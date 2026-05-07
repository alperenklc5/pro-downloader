"""
Cookie ve kimlik doğrulama yönetimi.

Tarayıcıdan otomatik okuma ve manuel cookies.txt desteği.
"""

from __future__ import annotations

import configparser
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from core.exceptions import AuthenticationRequiredError

BrowserName = Literal[
    "chrome", "chromium", "edge", "firefox",
    "brave", "opera", "vivaldi", "safari", "whale",
]

SUPPORTED_BROWSERS: list[str] = [
    "chrome", "edge", "firefox", "brave", "opera", "vivaldi", "chromium",
]


@dataclass
class CookieConfig:
    """
    Cookie yapılandırması.

    Üç mod:
    - "none":    Cookie kullanılmaz.
    - "browser": Tarayıcıdan otomatik okunur (yt-dlp yapıyor).
    - "file":    Manuel Netscape format cookies.txt dosyası.
    """

    mode: Literal["browser", "file", "none"] = "none"
    browser: BrowserName | None = None
    browser_profile: str | None = None  # "Default", "Profile 1", vb.
    file_path: Path | None = None
    use_cache: bool = True  # Browser modunda cache varsa onu kullan

    def to_ydl_opts(self) -> dict:
        """yt-dlp options dict'ine dönüştürür."""
        if self.mode == "browser" and self.browser:
            # Cache varsa onu kullan (tarayıcı açıkken de çalışır)
            if self.use_cache:
                from core.cookie_cache import get_cached_cookies_path, is_cache_valid
                if is_cache_valid(self.browser, self.browser_profile):
                    cached = get_cached_cookies_path()
                    if cached:
                        return {"cookiefile": str(cached)}

            # Cache yok/geçersiz → direkt tarayıcıdan (lock olabilir)
            # Firefox: "Default" profil ismi yanlış (rastgele hash'li isim kullanır)
            # None/""/Default → profil belirtme, yt-dlp kendi bulsun
            profile = self.browser_profile
            if profile in (None, "", "Default"):
                return {"cookiesfrombrowser": (self.browser,)}
            return {"cookiesfrombrowser": (self.browser, profile, None, None)}
        if self.mode == "file" and self.file_path:
            return {"cookiefile": str(self.file_path)}
        return {}


def _windows_browser_paths() -> dict[str, list[Path]]:
    """Windows'ta her tarayıcının olabileceği executable + profil yolları."""
    home = Path.home()
    program_files = Path("C:/Program Files")
    program_files_x86 = Path("C:/Program Files (x86)")
    local_appdata = home / "AppData" / "Local"
    roaming = home / "AppData" / "Roaming"

    return {
        "chrome": [
            program_files / "Google" / "Chrome" / "Application" / "chrome.exe",
            program_files_x86 / "Google" / "Chrome" / "Application" / "chrome.exe",
            local_appdata / "Google" / "Chrome" / "Application" / "chrome.exe",
            local_appdata / "Google" / "Chrome" / "User Data",
        ],
        "edge": [
            program_files / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            program_files_x86 / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            local_appdata / "Microsoft" / "Edge" / "User Data",
        ],
        "firefox": [
            program_files / "Mozilla Firefox" / "firefox.exe",
            program_files_x86 / "Mozilla Firefox" / "firefox.exe",
            local_appdata / "Mozilla Firefox" / "firefox.exe",
            roaming / "Mozilla" / "Firefox" / "Profiles",
            roaming / "Mozilla" / "Firefox",
        ],
        "brave": [
            program_files / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
            program_files_x86 / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
            local_appdata / "BraveSoftware" / "Brave-Browser" / "User Data",
        ],
        "opera": [
            program_files / "Opera" / "launcher.exe",
            local_appdata / "Programs" / "Opera" / "launcher.exe",
            roaming / "Opera Software" / "Opera Stable",
        ],
        "vivaldi": [
            local_appdata / "Vivaldi" / "Application" / "vivaldi.exe",
            program_files / "Vivaldi" / "Application" / "vivaldi.exe",
            local_appdata / "Vivaldi" / "User Data",
        ],
        "chromium": [
            program_files / "Chromium" / "Application" / "chrome.exe",
            local_appdata / "Chromium" / "Application" / "chrome.exe",
            local_appdata / "Chromium" / "User Data",
        ],
    }


def _macos_browser_paths() -> dict[str, list[Path]]:
    """macOS'ta her tarayıcının olabileceği executable + profil yolları."""
    home = Path.home()
    apps = Path("/Applications")
    app_support = home / "Library" / "Application Support"

    return {
        "chrome": [
            apps / "Google Chrome.app",
            app_support / "Google" / "Chrome",
        ],
        "edge": [
            apps / "Microsoft Edge.app",
            app_support / "Microsoft Edge",
        ],
        "firefox": [
            apps / "Firefox.app",
            app_support / "Firefox" / "Profiles",
            app_support / "Firefox",
        ],
        "brave": [
            apps / "Brave Browser.app",
            app_support / "BraveSoftware" / "Brave-Browser",
        ],
        "opera": [
            apps / "Opera.app",
            app_support / "com.operasoftware.Opera",
        ],
        "vivaldi": [
            apps / "Vivaldi.app",
            app_support / "Vivaldi",
        ],
        "safari": [
            apps / "Safari.app",
        ],
    }


def _linux_browser_paths() -> dict[str, list[Path]]:
    """Linux'ta her tarayıcının olabileceği executable + profil yolları."""
    home = Path.home()
    config = home / ".config"

    return {
        "chrome": [
            Path("/usr/bin/google-chrome"),
            Path("/usr/bin/google-chrome-stable"),
            Path("/snap/bin/google-chrome"),
            config / "google-chrome",
        ],
        "chromium": [
            Path("/usr/bin/chromium"),
            Path("/usr/bin/chromium-browser"),
            Path("/snap/bin/chromium"),
            config / "chromium",
        ],
        "edge": [
            Path("/usr/bin/microsoft-edge"),
            Path("/usr/bin/microsoft-edge-stable"),
            config / "microsoft-edge",
        ],
        "firefox": [
            Path("/usr/bin/firefox"),
            Path("/snap/bin/firefox"),
            home / ".mozilla" / "firefox",
        ],
        "brave": [
            Path("/usr/bin/brave-browser"),
            Path("/snap/bin/brave"),
            config / "BraveSoftware" / "Brave-Browser",
        ],
        "opera": [
            Path("/usr/bin/opera"),
            config / "opera",
        ],
        "vivaldi": [
            Path("/usr/bin/vivaldi"),
            Path("/usr/bin/vivaldi-stable"),
            config / "vivaldi",
        ],
    }


def detect_installed_browsers() -> list[str]:
    """
    Sistemde kurulu olan desteklenen tarayıcıları tespit eder.

    Strateji:
    1. Platforma özgü executable + profil yollarından herhangi birini bulursa kurulu say
    2. Fallback olarak PATH üzerinden de kontrol (winget/scoop kurulumları için)

    Returns:
        Kurulu tarayıcıların isim listesi.
    """
    if sys.platform == "win32":
        paths_map = _windows_browser_paths()
    elif sys.platform == "darwin":
        paths_map = _macos_browser_paths()
    else:
        paths_map = _linux_browser_paths()

    # PATH fallback için executable isimleri
    exe_names: dict[str, list[str]] = {
        "chrome": ["chrome", "google-chrome"],
        "chromium": ["chromium", "chromium-browser"],
        "edge": ["msedge", "microsoft-edge"],
        "firefox": ["firefox"],
        "brave": ["brave", "brave-browser"],
        "opera": ["opera"],
        "vivaldi": ["vivaldi"],
        "safari": ["safari"],
    }

    detected: list[str] = []
    for browser, paths in paths_map.items():
        if any(p.exists() for p in paths):
            detected.append(browser)
            continue

        # Fallback: PATH'te executable var mı?
        if browser in exe_names:
            for exe in exe_names[browser]:
                if shutil.which(exe):
                    detected.append(browser)
                    break

    return detected


def list_browser_profiles(browser: str) -> list[str]:
    """
    Bir tarayıcının mevcut profillerini listeler.

    Firefox: profiles.ini dosyasını parse eder (standart + Microsoft Store).
    Chromium-based: Local State JSON'dan profil isimlerini okur.

    Args:
        browser: Tarayıcı adı (örn. "chrome", "edge", "firefox").

    Returns:
        Profil adlarının listesi, en az ["Default"] içerir.
    """
    home = Path.home()

    # === Firefox: profiles.ini parse et ===
    if browser == "firefox":
        possible_paths: list[Path] = []

        if sys.platform == "win32":
            # Standart Firefox
            possible_paths.append(
                home / "AppData" / "Roaming" / "Mozilla" / "Firefox" / "profiles.ini"
            )
            # Microsoft Store Firefox
            packages = home / "AppData" / "Local" / "Packages"
            if packages.exists():
                try:
                    for pkg in packages.iterdir():
                        if pkg.name.startswith("Mozilla.Firefox"):
                            candidate = (
                                pkg / "LocalCache" / "Roaming"
                                / "Mozilla" / "Firefox" / "profiles.ini"
                            )
                            if candidate.exists():
                                possible_paths.append(candidate)
                except OSError:
                    pass
        elif sys.platform == "darwin":
            possible_paths.append(
                home / "Library" / "Application Support" / "Firefox" / "profiles.ini"
            )
        else:
            possible_paths.append(home / ".mozilla" / "firefox" / "profiles.ini")

        profiles: list[str] = []
        for ini_path in possible_paths:
            if not ini_path.exists():
                continue
            try:
                config = configparser.ConfigParser()
                config.read(str(ini_path), encoding="utf-8")

                for section in config.sections():
                    if not section.startswith("Profile"):
                        continue
                    path = config.get(section, "Path", fallback=None)
                    if path:
                        # "xxxxxxxx.default-release" gibi dizin adı
                        display = path.replace("\\", "/").rsplit("/", 1)[-1]
                        if display not in profiles:
                            profiles.append(display)
            except Exception:
                continue

        return profiles if profiles else ["Default"]

    # === Chromium-based: Local State JSON parse et ===
    if sys.platform == "win32":
        base_map: dict[str, Path] = {
            "chrome":   home / "AppData" / "Local" / "Google" / "Chrome" / "User Data",
            "edge":     home / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data",
            "brave":    home / "AppData" / "Local" / "BraveSoftware" / "Brave-Browser" / "User Data",
            "opera":    home / "AppData" / "Roaming" / "Opera Software" / "Opera Stable",
            "vivaldi":  home / "AppData" / "Local" / "Vivaldi" / "User Data",
            "chromium": home / "AppData" / "Local" / "Chromium" / "User Data",
        }
    elif sys.platform == "darwin":
        app = home / "Library" / "Application Support"
        base_map = {
            "chrome":   app / "Google" / "Chrome",
            "edge":     app / "Microsoft Edge",
            "brave":    app / "BraveSoftware" / "Brave-Browser",
            "opera":    app / "com.operasoftware.Opera",
            "vivaldi":  app / "Vivaldi",
            "chromium": app / "Chromium",
        }
    else:
        cfg = home / ".config"
        base_map = {
            "chrome":   cfg / "google-chrome",
            "edge":     cfg / "microsoft-edge",
            "brave":    cfg / "BraveSoftware" / "Brave-Browser",
            "opera":    cfg / "opera",
            "vivaldi":  cfg / "vivaldi",
            "chromium": cfg / "chromium",
        }

    base = base_map.get(browser)
    if not base or not base.exists():
        return ["Default"]

    local_state = base / "Local State"
    if local_state.exists():
        try:
            with open(local_state, "r", encoding="utf-8") as f:
                data = json.load(f)
            profiles = list(data.get("profile", {}).get("info_cache", {}).keys())
            if profiles:
                return profiles
        except (json.JSONDecodeError, OSError):
            pass

    return ["Default"]


def parse_yt_dlp_error(error_message: str) -> type[Exception] | None:
    """
    yt-dlp hata mesajından uygun exception sınıfını tespit eder.

    Args:
        error_message: yt-dlp DownloadError mesajı.

    Returns:
        Uygun exception sınıfı veya None (eşleşme yoksa).
    """
    msg_lower = error_message.lower()

    auth_keywords = (
        "login required",
        "sign in",
        "authentication",
        "members-only",
        "members only",
        "subscriber",
        "premium required",
        "nsfw tweet requires authentication",
        "use --cookies",
        "requires you to be logged in",
        "private video",
        "age-restricted",
        "age restricted",
    )

    if any(kw in msg_lower for kw in auth_keywords):
        return AuthenticationRequiredError

    return None
