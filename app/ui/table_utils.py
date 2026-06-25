"""Tablo görünüm yardımcıları — iş mantığı değil, yalnızca okunabilirlik."""

from PyQt5.QtWidgets import QAbstractItemView, QTableWidget, QTableView, QWidget


def configure_table(table: QTableWidget | QTableView) -> None:
    """Merkezi dark tema ile uyumlu tablo davranışı."""
    table.setAlternatingRowColors(True)
    header = table.horizontalHeader()
    if header is not None:
        header.setStretchLastSection(True)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)


def configure_tables_in(root: QWidget) -> None:
    """Bir sayfa kökündeki tüm tablolara ortak tablo ayarlarını uygula."""
    for table in root.findChildren(QTableWidget):
        configure_table(table)
    for table in root.findChildren(QTableView):
        configure_table(table)
