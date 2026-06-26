"""Tablo görünüm yardımcıları — iş mantığı değil, yalnızca okunabilirlik."""

from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableView,
    QWidget,
)


def configure_table(table: QTableWidget | QTableView) -> None:
    """Merkezi dark tema ile uyumlu tablo davranışı.

    Sütunlar kullanıcı tarafından elle daraltılıp genişletilebilir (Interactive);
    son sütun kalan boşluğu doldurur. Sayfalar kendi içinde Stretch ayarlasa bile
    bu fonksiyon onları (apply_page_basics ile) kurulumdan sonra ezer.
    """
    table.setAlternatingRowColors(True)
    header = table.horizontalHeader()
    if header is not None:
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setMinimumSectionSize(24)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)


def configure_tables_in(root: QWidget) -> None:
    """Bir sayfa kökündeki tüm tablolara ortak tablo ayarlarını uygula."""
    for table in root.findChildren(QTableWidget):
        configure_table(table)
    for table in root.findChildren(QTableView):
        configure_table(table)


def autosize_columns(table: QTableWidget | QTableView) -> None:
    """Veri doldurulduktan sonra sütunları içeriğe göre boyutla.

    Interactive mod korunduğu için kullanıcı sonradan yine elle değiştirebilir;
    bu yalnızca makul bir başlangıç genişliği verir (tek haneli sütun dar kalır).
    """
    table.resizeColumnsToContents()
