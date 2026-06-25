"""Ana pencere navigasyon kurulumu."""

from typing import Callable, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout, QMenu, QWidget
from qfluentwidgets import InfoBar, InfoBarPosition, PushButton

from app.core.constants import (
    INACTIVE_MODULE_MESSAGE,
    MODULE_BILIM,
    MODULE_FINANS,
    MODULE_LABELS,
    MODULE_MUHASEBE,
    MODULE_TRADE,
)


INACTIVE_MODULE_KEYS: List[str] = [
    MODULE_MUHASEBE,
    MODULE_TRADE,
    MODULE_BILIM,
]


class FinansMenuButton(PushButton):
    """Finans üst menüsü — hover ile BANKALAR alt menüsünü açar."""

    def __init__(self, on_banks_open=None, parent=None) -> None:
        super().__init__(parent=parent)
        self.setText("Finans")
        self._on_banks_open = on_banks_open
        self._menu = QMenu(self)
        self._banks_action = self._menu.addAction("BANKALAR")
        self._banks_action.triggered.connect(self._handle_banks_clicked)

    def _handle_banks_clicked(self) -> None:
        if callable(self._on_banks_open):
            self._on_banks_open()

    def _show_menu(self) -> None:
        if self._menu.isVisible():
            return
        self._menu.popup(self.mapToGlobal(self.rect().bottomLeft()))

    def enterEvent(self, event) -> None:
        self._show_menu()
        super().enterEvent(event)

    def mousePressEvent(self, event) -> None:
        self._show_menu()
        super().mousePressEvent(event)


class TopModuleBar(QWidget):
    """Üst seviye modül seçici."""

    def __init__(
        self,
        on_banks_open: Callable[[], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._on_banks_open = on_banks_open
        self._current_module: Optional[str] = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(4)

        self._finans_button = FinansMenuButton(on_banks_open, self)
        layout.addWidget(self._finans_button)

        for key in INACTIVE_MODULE_KEYS:
            button = PushButton(parent=self)
            button.setText(MODULE_LABELS[key])
            button.clicked.connect(lambda _checked=False, module_key=key: self._show_inactive(module_key))
            layout.addWidget(button)

    @property
    def current_module(self) -> Optional[str]:
        return self._current_module

    def select_module(self, module_key: str) -> None:
        """Programatik olarak aktif modülü işaretle."""
        self._current_module = module_key

    def clear_module_selection(self) -> None:
        """Ana giriş ekranında üst modül seçimini sıfırla."""
        self._current_module = None

    def _show_inactive(self, module_key: str) -> None:
        InfoBar.warning(
            title=MODULE_LABELS[module_key],
            content=INACTIVE_MODULE_MESSAGE,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self.window(),
        )
