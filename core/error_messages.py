"""Hata mesajlarını kullanıcıya gösterilebilir hale getirir.

yt-dlp ham hata mesajları ANSI renk kodları içeriyor ve teknik detaylarla dolu.
Bu modül onları temizler ve bilinen hatalar için Türkçe açıklama ekler.
"""
import re
from dataclasses import dataclass


# ANSI escape sekansları için regex
ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


@dataclass
class FriendlyError:
    """Kullanıcıya gösterilecek hata bilgisi."""
    title: str
    message: str
    suggestion: str | None = None
    category: str = "generic"  # "auth", "cookie", "network", "format", "generic"
    raw_error: str = ""


def clean_ansi(text: str) -> str:
    """ANSI renk kodlarını ve escape karakterlerini temizler."""
    text = ANSI_ESCAPE.sub("", text)
    text = re.sub(r"\[\d+(;\d+)*m", "", text)
    text = re.sub(r"^(ERROR:\s*){2,}", "ERROR: ", text)
    return text.strip()


def humanize_error(raw_error: str) -> FriendlyError:
    """Ham hata mesajını kullanıcı dostu FriendlyError'a çevir."""
    cleaned = clean_ansi(raw_error)
    lower = cleaned.lower()

    # === Cookie / Tarayıcı Hataları ===
    if "failed to decrypt with dpapi" in lower or "could not decrypt" in lower:
        return FriendlyError(
            title="Chrome Cookie'leri Okunamadı",
            message=(
                "Chrome'un yeni sürümleri (v127+) cookie'leri ek bir şifreleme "
                "katmanıyla koruyor. Bu yüzden okuyamadık."
            ),
            suggestion=(
                "Çözüm seçenekleri:\n"
                "1. Edge veya Firefox kullan (bu sorun onlarda yok)\n"
                "2. Manuel cookies.txt dosyası seç (Ayarlar → Cookies)\n"
                "3. Chrome'u tamamen kapatıp tekrar dene"
            ),
            category="cookie",
            raw_error=cleaned,
        )

    if "could not find" in lower and "cookie" in lower:
        return FriendlyError(
            title="Tarayıcı Cookie'leri Bulunamadı",
            message=(
                "Seçili tarayıcının cookie dosyası bulunamadı. "
                "Tarayıcıyı en az bir kez açıp kullanmış olman gerekiyor."
            ),
            suggestion=(
                "1. Seçtiğin tarayıcıyı bir kez aç ve siteye giriş yap\n"
                "2. Tarayıcıyı kapat\n"
                "3. Tekrar dene"
            ),
            category="cookie",
            raw_error=cleaned,
        )

    if "database is locked" in lower or "database locked" in lower:
        return FriendlyError(
            title="Tarayıcı Açık Görünüyor",
            message="Tarayıcı çalışırken cookie dosyası kilitli olur, okuyamayız.",
            suggestion=(
                "1. Tarayıcıyı tamamen kapat (system tray'i de kontrol et)\n"
                "2. Görev Yöneticisi'nden tarayıcı süreçlerinin bittiğinden emin ol\n"
                "3. Tekrar dene"
            ),
            category="cookie",
            raw_error=cleaned,
        )

    # === Login / Auth Hataları ===
    auth_patterns = [
        "login required", "sign in", "authentication required",
        "private video", "members-only", "members only",
        "this video is unavailable", "use --cookies",
        "requires you to be logged in", "nsfw tweet requires authentication",
        "premium", "subscriber",
    ]
    if any(p in lower for p in auth_patterns):
        return FriendlyError(
            title="Login Gerekli",
            message=(
                "Bu video özel, üye-only veya yaş kısıtlı içerik. "
                "İndirebilmek için ilgili sitede login olmalısın."
            ),
            suggestion=(
                "1. Tarayıcında siteye giriş yap\n"
                "2. Tarayıcıyı kapat\n"
                "3. Ayarlar → Cookies → 'Tarayıcıdan oku' seçeneğini aktifleştir\n"
                "4. Tekrar dene"
            ),
            category="auth",
            raw_error=cleaned,
        )

    if "age" in lower and ("restricted" in lower or "confirm" in lower):
        return FriendlyError(
            title="Yaş Kısıtlı İçerik",
            message="Bu video yaş doğrulaması gerektiriyor.",
            suggestion=(
                "Tarayıcında siteye giriş yap (yaş doğrulaması yapılmış hesapla), "
                "sonra Ayarlar → Cookies → 'Tarayıcıdan oku' seç ve tekrar dene."
            ),
            category="auth",
            raw_error=cleaned,
        )

    # === Bölgesel Kısıtlama ===
    if "not available in your country" in lower or ("geo" in lower and "block" in lower):
        return FriendlyError(
            title="Bölgesel Kısıtlama",
            message="Bu video senin ülkende erişilemiyor.",
            suggestion="VPN kullanarak farklı bir ülkeden bağlan ve tekrar dene.",
            category="geo",
            raw_error=cleaned,
        )

    # === URL / Site Hataları ===
    if "unsupported url" in lower or "no extractor" in lower:
        return FriendlyError(
            title="Desteklenmeyen Site",
            message="Bu site veya URL formatı desteklenmiyor.",
            suggestion=(
                "yt-dlp 1800+ site destekliyor ama hepsini değil. "
                "URL'nin doğru olduğundan emin ol veya alternatif bir kaynak dene."
            ),
            category="format",
            raw_error=cleaned,
        )

    if "unable to download webpage" in lower or "404" in cleaned or "not found" in lower:
        return FriendlyError(
            title="Video Bulunamadı",
            message="Bu video silinmiş, kaldırılmış veya URL hatalı.",
            suggestion="URL'yi kontrol et. Video hâlâ tarayıcıda açılıyor mu?",
            category="format",
            raw_error=cleaned,
        )

    # === Network Hataları ===
    network_patterns = [
        "unable to connect", "connection refused", "timed out",
        "network is unreachable", "no route to host",
        "name or service not known", "dns",
    ]
    if any(p in lower for p in network_patterns):
        return FriendlyError(
            title="Bağlantı Hatası",
            message="Sunucuya bağlanılamadı.",
            suggestion=(
                "1. İnternet bağlantını kontrol et\n"
                "2. VPN/proxy kullanıyorsan kapatıp dene\n"
                "3. Birkaç dakika sonra tekrar dene"
            ),
            category="network",
            raw_error=cleaned,
        )

    # === Format Hataları ===
    if "requested format" in lower and ("not available" in lower or "is not available" in lower):
        return FriendlyError(
            title="İstenen Kalite Mevcut Değil",
            message="Seçtiğin kalite bu video için mevcut değil.",
            suggestion="Daha düşük bir kalite seç veya 'Best' kullan.",
            category="format",
            raw_error=cleaned,
        )

    # === Generic Fallback ===
    display_msg = re.sub(r"^ERROR:\s*", "", cleaned).strip()
    if len(display_msg) > 200:
        display_msg = display_msg[:200] + "..."

    return FriendlyError(
        title="İndirme Hatası",
        message=display_msg or "Bilinmeyen bir hata oluştu.",
        suggestion="Hata devam ederse URL'yi ve cookie ayarlarını kontrol et.",
        category="generic",
        raw_error=cleaned,
    )
