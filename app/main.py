"""Uygulama giriş noktası."""

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt5.QtWidgets import QApplication, QMessageBox

from app.core.database import init_database
from app.core.exceptions import AppError
from app.core.seed import seed_database
from app.ui.main_window import MainWindow
from app.ui.theme import apply_app_theme


def _startup_database() -> None:
    init_database()
    seed_database()


def main() -> None:
    try:
        _startup_database()
    except AppError as exc:
        print(f"Veritabanı başlatma hatası: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Veritabanı başlatma hatası: {exc}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    app = QApplication(sys.argv)

    try:
        apply_app_theme(app)
        window = MainWindow()
        window.show()
    except Exception as exc:
        QMessageBox.critical(
            None,
            "Başlatma Hatası",
            f"Uygulama başlatılamadı:\n{exc}",
        )
        print(f"Uygulama başlatma hatası: {exc}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
