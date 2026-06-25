"""Placeholder sayfa tabanı."""

from PyQt5.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, TitleLabel


class PlaceholderPage(QWidget):
    """Başlık ve kısa açıklama içeren boş bir sayfa."""

    def __init__(self, title: str, description: str, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.setSpacing(12)

        title_label = TitleLabel(title, self)
        desc_label = BodyLabel(description, self)
        desc_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        layout.addStretch()
