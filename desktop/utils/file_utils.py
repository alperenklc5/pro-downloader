"""OS'a özgü dosya ve klasör açma yardımcıları."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def open_file(path: Path) -> None:
    """Dosyayı varsayılan uygulamayla açar."""
    if sys.platform == "win32":
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def open_folder(path: Path) -> None:
    """Klasörü dosya yöneticisinde açar."""
    if sys.platform == "win32":
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def reveal_in_folder(path: Path) -> None:
    """Dosyayı dosya yöneticisinde seçili olarak gösterir."""
    if sys.platform == "win32":
        subprocess.run(["explorer", "/select,", str(path)], check=False)
    elif sys.platform == "darwin":
        subprocess.run(["open", "-R", str(path)], check=False)
    else:
        open_folder(path.parent)
