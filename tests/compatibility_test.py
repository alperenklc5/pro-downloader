"""Site Compatibility Test Script

Kullanim:
    python -m tests.compatibility_test                    # Tier 1+2 test (default)
    python -m tests.compatibility_test --all              # Tum tier'lar
    python -m tests.compatibility_test --tier nsfw        # Sadece NSFW
    python -m tests.compatibility_test --download         # Test indirme de yap
    python -m tests.compatibility_test --no-cookies       # Cookie kullanma
    python -m tests.compatibility_test --report report.md # Rapor dosyasi
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal


# Windows'ta ANSI desteği
if sys.platform == "win32":
    os.system("")


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


from core.auth import CookieConfig
from core.error_messages import clean_ansi, humanize_error
from core.exceptions import (
    AuthenticationRequiredError,
    DownloaderError,
    InvalidURLError,
    NetworkError,
    VideoUnavailableError,
)
from core.extractor import VideoInfo, extract_info
from desktop.config import AppConfig
from tests.test_urls import (
    TestURL,
    USER_CUSTOM_URLS,
    get_all_urls,
)


@dataclass
class TestResult:
    """Tek bir URL'nin test sonucu."""
    test_url: TestURL
    status: Literal[
        "success", "auth_required", "unavailable",
        "network", "format_err", "unknown_error",
    ] = "unknown_error"
    duration_ms: int = 0
    title: str | None = None
    video_duration: int | None = None
    formats_count: int = 0
    has_audio: bool = False
    has_video: bool = False
    error_message: str = ""
    error_category: str = ""
    download_tested: bool = False
    download_success: bool = False
    download_filesize: int = 0


STATUS_ICONS = {
    "success": f"{Colors.GREEN}+{Colors.RESET}",
    "auth_required": f"{Colors.YELLOW}L{Colors.RESET}",
    "unavailable": f"{Colors.RED}x{Colors.RESET}",
    "network": f"{Colors.RED}N{Colors.RESET}",
    "format_err": f"{Colors.YELLOW}!{Colors.RESET}",
    "unknown_error": f"{Colors.RED}?{Colors.RESET}",
}

STATUS_LABELS = {
    "success": "OK",
    "auth_required": "AUTH",
    "unavailable": "FAIL",
    "network": "NET",
    "format_err": "FORMAT",
    "unknown_error": "ERR",
}


def format_duration(seconds: int | None) -> str:
    if not seconds:
        return "-"
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def check_yt_dlp_version() -> None:
    try:
        import yt_dlp
        version = yt_dlp.version.__version__
        print(f"{Colors.CYAN}yt-dlp version:{Colors.RESET} {version}")

        if "stable@" in version:
            date_str = version.split("@")[1]
            try:
                v_date = datetime.strptime(date_str, "%Y.%m.%d")
                days_old = (datetime.now() - v_date).days
                if days_old > 30:
                    print(
                        f"{Colors.YELLOW}  yt-dlp {days_old} gun eski. "
                        f"Guncellemek icin: pip install -U yt-dlp{Colors.RESET}"
                    )
            except ValueError:
                pass
    except ImportError:
        print(f"{Colors.RED}yt-dlp bulunamadi!{Colors.RESET}")
        sys.exit(1)


def test_single_url(
    test_url: TestURL,
    cookies: CookieConfig | None = None,
    do_download: bool = False,
    output_dir: Path | None = None,
) -> TestResult:
    """Tek bir URL'yi test et."""
    print(f"  {Colors.GRAY}Testing:{Colors.RESET} {test_url.site:<20} ", end="", flush=True)

    start = time.time()
    result = TestResult(test_url=test_url)

    try:
        info = extract_info(test_url.url, timeout=30, cookies=cookies)
        result.title = info.title
        result.video_duration = info.duration
        result.formats_count = len(info.video_formats) + len(info.audio_formats)
        result.has_video = len(info.video_formats) > 0
        result.has_audio = len(info.audio_formats) > 0 or any(
            f.has_audio for f in info.video_formats
        )
        result.status = "success"

        if do_download and output_dir:
            result = _try_test_download(result, test_url, cookies, output_dir)

    except AuthenticationRequiredError as e:
        result.status = "auth_required"
        friendly = humanize_error(str(e))
        result.error_message = friendly.title
        result.error_category = "auth"

    except VideoUnavailableError as e:
        result.status = "unavailable"
        friendly = humanize_error(str(e))
        result.error_message = friendly.title
        result.error_category = "unavailable"

    except NetworkError as e:
        result.status = "network"
        friendly = humanize_error(str(e))
        result.error_message = friendly.title
        result.error_category = "network"

    except InvalidURLError as e:
        result.status = "format_err"
        friendly = humanize_error(str(e))
        result.error_message = friendly.title
        result.error_category = "format"

    except DownloaderError as e:
        friendly = humanize_error(str(e))
        if friendly.category == "auth":
            result.status = "auth_required"
        elif friendly.category == "network":
            result.status = "network"
        elif friendly.category == "format":
            result.status = "format_err"
        else:
            result.status = "unknown_error"
        result.error_message = friendly.title
        result.error_category = friendly.category

    except Exception as e:
        result.status = "unknown_error"
        result.error_message = clean_ansi(str(e))[:80]
        result.error_category = "unknown"

    result.duration_ms = int((time.time() - start) * 1000)

    # Console ciktisi
    icon = STATUS_ICONS.get(result.status, "?")
    label = STATUS_LABELS.get(result.status, "?")
    if result.status == "success":
        info_str = f"{result.formats_count} fmt, {format_duration(result.video_duration)}"
        dl_str = ""
        if result.download_tested:
            dl_str = (
                f", DL:{'OK' if result.download_success else 'FAIL'}"
            )
        print(f"{icon} {Colors.GREEN}{label}{Colors.RESET} ({info_str}, {result.duration_ms}ms{dl_str})")
    else:
        print(f"{icon} {Colors.RED}{label}{Colors.RESET} - {result.error_message[:60]}")

    return result


def _try_test_download(
    result: TestResult,
    test_url: TestURL,
    cookies: CookieConfig | None,
    output_dir: Path,
) -> TestResult:
    """Kucuk bir test indirmesi yap."""
    from core.downloader import DownloadOptions, Downloader

    try:
        opts = DownloadOptions(
            output_dir=output_dir,
            quality="360p",
            cookies=cookies or CookieConfig(),
        )
        downloader = Downloader(opts)
        downloaded_path = downloader.download(test_url.url)
        if downloaded_path.exists():
            result.download_tested = True
            result.download_success = True
            result.download_filesize = downloaded_path.stat().st_size
            try:
                downloaded_path.unlink()
            except OSError:
                pass
    except Exception:
        result.download_tested = True
        result.download_success = False
    return result


def print_summary_table(results: list[TestResult]) -> None:
    """Renkli ozet tablosu."""
    print(f"\n{Colors.BOLD}=== OZET ==={Colors.RESET}\n")

    by_tier: dict[str, list[TestResult]] = {}
    for r in results:
        by_tier.setdefault(r.test_url.tier, []).append(r)

    tier_labels = {
        "tier1": "Tier 1 (Mainstream)",
        "tier2": "Tier 2 (Bazen Cookie)",
        "tier3": "Tier 3 (Cookie Gerekli)",
        "nsfw": "NSFW",
    }

    for tier in ["tier1", "tier2", "tier3", "nsfw"]:
        if tier not in by_tier:
            continue

        tier_results = by_tier[tier]
        success_count = sum(1 for r in tier_results if r.status == "success")
        total = len(tier_results)

        color = (
            Colors.GREEN if success_count == total
            else (Colors.YELLOW if success_count > 0 else Colors.RED)
        )

        print(
            f"{Colors.BOLD}{tier_labels[tier]}:{Colors.RESET} "
            f"{color}{success_count}/{total}{Colors.RESET}"
        )

        print(f"  {'Site':<20} {'Durum':<10} {'Fmt':<6} {'Sure':<10} {'Detay'}")
        print(f"  {'-'*20} {'-'*10} {'-'*6} {'-'*10} {'-'*40}")

        for r in tier_results:
            site = r.test_url.site[:20]
            icon = STATUS_ICONS.get(r.status, "?")
            label = STATUS_LABELS.get(r.status, "?")
            formats = str(r.formats_count) if r.formats_count else "-"
            duration = format_duration(r.video_duration)
            detail = (r.title or r.error_message or "")[:40]
            print(f"  {site:<20} {icon} {label:<8} {formats:<6} {duration:<10} {detail}")

        print()

    # Genel istatistik
    total = len(results)
    success = sum(1 for r in results if r.status == "success")
    auth = sum(1 for r in results if r.status == "auth_required")
    failed = total - success - auth

    pct = success * 100 // total if total else 0
    print(f"{Colors.BOLD}=================================={Colors.RESET}")
    print(f"  Toplam:        {total}")
    print(f"  {Colors.GREEN}Basarili:      {success} ({pct}%){Colors.RESET}")
    print(f"  {Colors.YELLOW}Auth Gerekli:  {auth}{Colors.RESET}")
    print(f"  {Colors.RED}Basarisiz:     {failed}{Colors.RESET}")
    print()


def write_markdown_report(results: list[TestResult], output_path: Path) -> None:
    """Sonuclari markdown rapor olarak yaz."""
    lines: list[str] = []
    total = len(results)
    success = sum(1 for r in results if r.status == "success")
    pct = success * 100 // total if total else 0

    lines.append("# Site Compatibility Test Raporu")
    lines.append("")
    lines.append(f"**Tarih:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Toplam Test:** {total}")
    lines.append(f"**Basari Orani:** {success}/{total} ({pct}%)")
    lines.append("")

    by_tier: dict[str, list[TestResult]] = {}
    for r in results:
        by_tier.setdefault(r.test_url.tier, []).append(r)

    tier_labels = {
        "tier1": "Tier 1 -- Mainstream (Public)",
        "tier2": "Tier 2 -- Bazen Cookie Ister",
        "tier3": "Tier 3 -- Cookie Genellikle Gerekli",
        "nsfw": "Yetiskin Icerik (NSFW)",
    }

    status_emoji = {
        "success": "OK",
        "auth_required": "AUTH",
        "unavailable": "FAIL",
        "network": "NET",
        "format_err": "FORMAT",
        "unknown_error": "ERR",
    }

    for tier in ["tier1", "tier2", "tier3", "nsfw"]:
        if tier not in by_tier:
            continue

        lines.append(f"## {tier_labels[tier]}")
        lines.append("")
        lines.append("| Site | Durum | Format Sayisi | Sure | Detay |")
        lines.append("|------|-------|---------------|------|-------|")

        for r in by_tier[tier]:
            site = r.test_url.site
            s_label = status_emoji.get(r.status, "?")
            formats = str(r.formats_count) if r.formats_count else "-"
            duration = format_duration(r.video_duration)
            detail = (r.title or r.error_message or "-").replace("|", "\\|")[:60]
            lines.append(f"| {site} | {s_label} | {formats} | {duration} | {detail} |")

        lines.append("")

    # Hata detaylari
    errors = [r for r in results if r.status != "success"]
    if errors:
        lines.append("## Hata Detaylari")
        lines.append("")
        for r in errors:
            lines.append(f"### {r.test_url.site}")
            lines.append(f"- **URL:** `{r.test_url.url}`")
            lines.append(f"- **Hata:** {r.error_message}")
            lines.append(f"- **Kategori:** {r.error_category}")
            if r.test_url.notes:
                lines.append(f"- **Not:** {r.test_url.notes}")
            lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"{Colors.CYAN}Rapor yazildi:{Colors.RESET} {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Site compatibility test")
    parser.add_argument(
        "--all", action="store_true",
        help="Tum tier'lari test et (default: tier1+tier2)",
    )
    parser.add_argument(
        "--tier", choices=["tier1", "tier2", "tier3", "nsfw"],
        help="Sadece belirli tier",
    )
    parser.add_argument(
        "--download", action="store_true",
        help="Test indirme de yap (yavas!)",
    )
    parser.add_argument(
        "--no-cookies", action="store_true",
        help="Cookie kullanma",
    )
    parser.add_argument(
        "--report", type=str, default="tests/compatibility_report.md",
        help="Markdown rapor yolu",
    )
    parser.add_argument(
        "--include-custom", action="store_true",
        help="USER_CUSTOM_URLS'i de dahil et",
    )
    args = parser.parse_args()

    check_yt_dlp_version()

    # URL listesi
    if args.tier:
        urls = get_all_urls([args.tier])
    elif args.all:
        urls = get_all_urls()
    else:
        urls = get_all_urls(["tier1", "tier2"])

    if args.include_custom:
        urls = urls + USER_CUSTOM_URLS

    if not urls:
        print(f"{Colors.RED}Test URL'si bulunamadi!{Colors.RESET}")
        sys.exit(1)

    # Cookie config
    cookies: CookieConfig | None = None
    if not args.no_cookies:
        try:
            config = AppConfig.load()
            cookie_cfg = config.get_cookie_config()
            if cookie_cfg.mode != "none":
                cookies = cookie_cfg
                source = cookie_cfg.browser or cookie_cfg.file_path or "?"
                print(f"{Colors.CYAN}Cookie:{Colors.RESET} {cookie_cfg.mode} ({source})")
            else:
                print(f"{Colors.GRAY}Cookie: yapilandirilmamis (none){Colors.RESET}")
        except Exception as e:
            print(f"{Colors.YELLOW}Cookie yapilandirmasi yuklenemedi: {e}{Colors.RESET}")
    else:
        print(f"{Colors.YELLOW}Cookie kullanilmiyor (--no-cookies){Colors.RESET}")

    # Output dizini (download test icin)
    output_dir = Path("tests/_download_test_temp")
    if args.download:
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"{Colors.CYAN}Indirme testi:{Colors.RESET} acik (gecici dosyalar {output_dir})")

    # Test calistir
    print(f"\n{Colors.BOLD}=== TEST BASLIYOR ==={Colors.RESET}")
    print(f"Toplam URL: {len(urls)}\n")

    results: list[TestResult] = []

    by_tier: dict[str, list[TestURL]] = {}
    for u in urls:
        by_tier.setdefault(u.tier, []).append(u)

    tier_headers = {
        "tier1": "TIER 1 -- Mainstream",
        "tier2": "TIER 2 -- Bazen Cookie",
        "tier3": "TIER 3 -- Cookie Gerekli",
        "nsfw": "NSFW",
    }

    for tier in ["tier1", "tier2", "tier3", "nsfw"]:
        if tier not in by_tier:
            continue

        print(f"\n{Colors.BOLD}{Colors.BLUE}--- {tier_headers[tier]} ---{Colors.RESET}")

        for url in by_tier[tier]:
            r = test_single_url(
                url,
                cookies=cookies,
                do_download=args.download,
                output_dir=output_dir if args.download else None,
            )
            results.append(r)
            time.sleep(0.5)  # Rate limit'lerden kacinmak icin

    # Ozet ve rapor
    print_summary_table(results)
    write_markdown_report(results, Path(args.report))

    # Cleanup
    if args.download and output_dir.exists():
        try:
            for f in output_dir.iterdir():
                f.unlink()
            output_dir.rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    main()
