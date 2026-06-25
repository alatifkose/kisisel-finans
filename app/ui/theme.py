"""Uygulama teması ve merkezi stylesheet."""

from PyQt5.QtWidgets import QApplication, QWidget
from qfluentwidgets import Theme, setTheme, setThemeColor

from app.ui.table_utils import configure_tables_in

BANK_PAGE_OBJECT_NAMES = (
    "bank_summary",
    "accounts",
    "credit_cards",
    "kmh",
    "loans",
    "installment_advances",
    "transactions",
    "transfers",
    "definitions",
    "reports",
)

_PAGE_ROOT_SELECTORS = ", ".join(f"#{name}" for name in ("home", *BANK_PAGE_OBJECT_NAMES))

DARK_STYLESHEET = f"""
QWidget {{
    background-color: #242424;
    color: #f0f0f0;
}}

QLabel {{
    color: #f0f0f0;
    background: transparent;
}}

QFrame {{
    background-color: #2b2b2b;
    color: #f0f0f0;
    border: none;
}}

QPushButton {{
    background-color: #333333;
    color: #f0f0f0;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 5px 10px;
}}

QPushButton:hover {{
    background-color: #3f3f3f;
}}

QLineEdit,
QTextEdit,
QPlainTextEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox,
QDateEdit {{
    background-color: #2f2f2f;
    color: #f0f0f0;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 4px;
}}

QTableWidget,
QTableView {{
    background-color: #252525;
    alternate-background-color: #2d2d2d;
    color: #f0f0f0;
    gridline-color: #444444;
    selection-background-color: #3a6ea5;
    selection-color: #ffffff;
}}

QHeaderView::section {{
    background-color: #303030;
    color: #f0f0f0;
    border: 1px solid #444444;
    padding: 4px;
}}

QTableCornerButton::section {{
    background-color: #303030;
    border: 1px solid #444444;
}}

QMenu {{
    background-color: #2b2b2b;
    color: #f0f0f0;
    border: 1px solid #555555;
}}

QMenu::item:selected {{
    background-color: #3a6ea5;
}}

QScrollArea,
QScrollArea > QWidget,
QScrollArea > QWidget > QWidget {{
    background-color: #242424;
    color: #f0f0f0;
}}

QStackedWidget {{
    background-color: #242424;
    color: #f0f0f0;
}}

QTabWidget::pane {{
    border: 1px solid #444444;
    background-color: #242424;
}}

QTabBar::tab {{
    background-color: #333333;
    color: #f0f0f0;
    padding: 6px 12px;
    border: 1px solid #444444;
}}

QTabBar::tab:selected {{
    background-color: #3a6ea5;
    color: #ffffff;
}}

QCheckBox,
QRadioButton {{
    color: #f0f0f0;
    background: transparent;
}}

QGroupBox {{
    color: #f0f0f0;
    border: 1px solid #444444;
    margin-top: 8px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}}

QDialog {{
    background-color: #242424;
    color: #f0f0f0;
}}

QMessageBox {{
    background-color: #242424;
    color: #f0f0f0;
}}

{_PAGE_ROOT_SELECTORS} {{
    background-color: #242424;
    color: #f0f0f0;
}}
"""


def apply_app_theme(app: QApplication) -> None:
    """qfluentwidgets dark tema + Qt native widget merkezi stylesheet."""
    setTheme(Theme.DARK)
    setThemeColor("#0078D4")
    app.setStyleSheet(DARK_STYLESHEET)


def apply_page_basics(widget: QWidget) -> None:
    """Sayfa kök widget için arka plan ve tablo okunabilirlik ayarları."""
    widget.setAutoFillBackground(True)
    configure_tables_in(widget)
