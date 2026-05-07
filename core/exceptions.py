"""
Özel exception sınıfları.

Tüm downloader hataları bu modüldeki sınıflardan türer;
UI ve API katmanları bunları yakalayıp anlamlı mesajlar gösterebilir.
"""


class DownloaderError(Exception):
    """Tüm downloader hatalarının base sınıfı."""
    pass


class InvalidURLError(DownloaderError):
    """URL formatı geçersiz veya desteklenmiyor."""
    pass


class VideoUnavailableError(DownloaderError):
    """Video private, silinmiş veya bölgesel kısıtlamalı."""
    pass


class NetworkError(DownloaderError):
    """Ağ bağlantısı hatası."""
    pass


class FormatNotAvailableError(DownloaderError):
    """İstenen format/kalite bu video için mevcut değil."""
    pass


class DownloadCancelledError(DownloaderError):
    """Kullanıcı indirmeyi iptal etti."""
    pass


class AuthenticationRequiredError(DownloaderError):
    """Video login/cookie gerektiriyor."""
    pass


class CookieError(DownloaderError):
    """Cookie dosyası okunamadı veya geçersiz."""
    pass
