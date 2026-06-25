"""Uygulama ana giriş sayfası."""

from PyQt5.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, TitleLabel

from app.core.constants import APP_NAME
from app.ui.theme import apply_page_basics


class HomePage(QWidget):
    """Açılışta gösterilen sade giriş ekranı."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("home")
        apply_page_basics(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(16)

        layout.addWidget(TitleLabel(APP_NAME, self))
        subtitle = BodyLabel(
            "Finans, muhasebe, trade ve diğer modüller buradan yönetilecek.",
            self,
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        layout.addStretch()
