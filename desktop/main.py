"""
Video Downloader — Desktop Uygulaması

Çalıştırma:
    python -m desktop.main
"""

import logging

from desktop.app import App


def main() -> None:
    """Uygulamayı başlatır."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
