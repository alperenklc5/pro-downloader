"""Windows güç yönetimi - indirme sırasında uyku modunu engelle."""
import ctypes
import sys

# Windows API sabitleri
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001      # Sistem uykuya geçmesin
ES_DISPLAY_REQUIRED = 0x00000002     # Ekran kapanmasın (isteğe bağlı)


def prevent_sleep() -> bool:
    """İndirme başlarken uyku modunu engelle."""
    if sys.platform != 'win32':
        return False
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        )
        return True
    except Exception:
        return False


def allow_sleep() -> bool:
    """İndirme bitince uyku moduna izin ver."""
    if sys.platform != 'win32':
        return False
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        return True
    except Exception:
        return False
