"""Kredi Kartları sayfası: kart tanımı, tekil hareketler ve türetilen ekstre."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    MessageBox,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
    TitleLabel,
)

from app.core.constants import Nature
from app.core.exceptions import AppError, ValidationError
from app.modules.banks.dialogs.credit_card_dialogs import CardEntryDialog, CreditCardDialog
from app.modules.banks.pages._ui_helpers import active_label, show_error, show_success
from app.ui.table_utils import autosize_columns
from app.services.bank_service import BankService
from app.services.card_entry_service import CardEntryService
from app.services.card_statement_service import CardStatementService
from app.services.credit_card_service import CreditCardService
from app.services.reference_service import ReferenceService


class CreditCardsPage(QWidget):
    """Kart tanımı + tekil hareketler + türetilen ekstre."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service = CreditCardService()
        self._bank_service = BankService()
        self._reference_service = ReferenceService()
        self._entry_service = CardEntryService()
        self._statement_service = CardStatementService()
        self._cards: List[Dict[str, Any]] = []
        self._entries: List[Dict[str, Any]] = []
        self._periods: List[Dict[str, Any]] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.setSpacing(16)
        layout.addWidget(TitleLabel("Kredi Kartları", self))

        splitter = QSplitter(self)
        layout.addWidget(splitter, 1)

        splitter.addWidget(self._build_cards_panel())
        splitter.addWidget(self._build_detail_panel())
        splitter.setSizes([560, 520])

    def _build_cards_panel(self) -> QWidget:
        cards_widget = QWidget(self)
        cards_layout = QVBoxLayout(cards_widget)
        cards_layout.setContentsMargins(0, 0, 8, 0)
        cards_layout.addWidget(SubtitleLabel("Kartlar", self))

        card_buttons = QHBoxLayout()
        self.add_card_button = PrimaryPushButton("Kart Ekle", self)
        self.edit_card_button = PushButton("Kart Düzenle", self)
        self.delete_card_button = PushButton("Kart Sil", self)
        self.refresh_cards_button = PushButton("Yenile", self)
        for button in (
            self.add_card_button,
            self.edit_card_button,
            self.delete_card_button,
            self.refresh_cards_button,
        ):
            card_buttons.addWidget(button)
        card_buttons.addStretch()
        cards_layout.addLayout(card_buttons)

        self.cards_table = QTableWidget(self)
        self.cards_table.setColumnCount(12)
        self.cards_table.setHorizontalHeaderLabels(
            [
                "#", "Banka", "Kart Adı", "Para Birimi", "Kart Limiti",
                "Nakit Avans Limiti", "Ekstre Günü", "Son Ödeme Günü",
                "Likidite Sayılır", "Aktif", "Not", "Güncel Borç",
            ]
        )
        self.cards_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cards_table.setSelectionMode(QTableWidget.SingleSelection)
        self.cards_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cards_table.verticalHeader().setVisible(False)
        cards_layout.addWidget(self.cards_table)

        self.add_card_button.clicked.connect(self._on_add_card)
        self.edit_card_button.clicked.connect(self._on_edit_card)
        self.delete_card_button.clicked.connect(self._on_delete_card)
        self.refresh_cards_button.clicked.connect(self.refresh)
        self.cards_table.itemSelectionChanged.connect(self._load_card_detail)
        return cards_widget

    def _build_detail_panel(self) -> QWidget:
        detail = QWidget(self)
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(8, 0, 0, 0)
        inner = QSplitter(self)
        inner.setOrientation(Qt.Vertical)
        detail_layout.addWidget(inner, 1)

        # --- Kart Hareketleri ---
        entries_widget = QWidget(self)
        entries_layout = QVBoxLayout(entries_widget)
        entries_layout.setContentsMargins(0, 0, 0, 0)
        entries_layout.addWidget(SubtitleLabel("Kart Hareketleri", self))
        entry_buttons = QHBoxLayout()
        self.add_entry_button = PrimaryPushButton("Hareket Ekle", self)
        self.edit_entry_button = PushButton("Düzenle", self)
        self.delete_entry_button = PushButton("Sil", self)
        for button in (self.add_entry_button, self.edit_entry_button, self.delete_entry_button):
            entry_buttons.addWidget(button)
        entry_buttons.addStretch()
        entries_layout.addLayout(entry_buttons)

        self.entries_table = QTableWidget(self)
        self.entries_table.setColumnCount(6)
        self.entries_table.setHorizontalHeaderLabels(
            ["#", "Tarih", "Tür", "Açıklama", "Kategori", "Tutar"]
        )
        self.entries_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.entries_table.setSelectionMode(QTableWidget.SingleSelection)
        self.entries_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.entries_table.verticalHeader().setVisible(False)
        entries_layout.addWidget(self.entries_table)
        inner.addWidget(entries_widget)

        # --- Türetilen Ekstre ---
        stmt_widget = QWidget(self)
        stmt_layout = QVBoxLayout(stmt_widget)
        stmt_layout.setContentsMargins(0, 0, 0, 0)
        stmt_layout.addWidget(SubtitleLabel("Türetilen Ekstre", self))
        period_row = QHBoxLayout()
        period_row.addWidget(BodyLabel("Dönem:", self))
        self.period_combo = ComboBox(self)
        self.period_combo.setMinimumWidth(260)
        period_row.addWidget(self.period_combo)
        period_row.addStretch()
        stmt_layout.addLayout(period_row)

        self.period_summary = BodyLabel("—", self)
        self.period_summary.setWordWrap(True)
        stmt_layout.addWidget(self.period_summary)

        self.lines_table = QTableWidget(self)
        self.lines_table.setColumnCount(4)
        self.lines_table.setHorizontalHeaderLabels(["Tarih", "Tür", "Açıklama", "Tutar"])
        self.lines_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.lines_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.lines_table.verticalHeader().setVisible(False)
        stmt_layout.addWidget(self.lines_table)
        inner.addWidget(stmt_widget)
        inner.setSizes([300, 320])

        self.add_entry_button.clicked.connect(self._on_add_entry)
        self.edit_entry_button.clicked.connect(self._on_edit_entry)
        self.delete_entry_button.clicked.connect(self._on_delete_entry)
        self.period_combo.currentIndexChanged.connect(self._fill_period_lines)
        return detail

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()

    def refresh(self) -> None:
        self._cards = self._service.list_credit_cards(include_inactive=True)
        self.cards_table.setRowCount(len(self._cards))
        for row_index, card in enumerate(self._cards):
            debt = self._statement_service.get_current_statement_debt(int(card["id"]))
            debt_display = self._service.format_card_for_ui(
                {**card, "card_limit": debt}
            )["card_limit_display"]["display"]
            values = [
                row_index + 1,
                card["bank_name"],
                card["name"],
                card["currency_code"],
                card["card_limit_display"]["display"],
                card["cash_advance_limit_display"]["display"],
                card.get("statement_day") or "—",
                card.get("due_day") or "—",
                active_label(card["counts_as_liquidity"]),
                active_label(card["is_active"]),
                card.get("note") or "",
                debt_display,
            ]
            for col_index, value in enumerate(values):
                self.cards_table.setItem(row_index, col_index, QTableWidgetItem(str(value)))
        autosize_columns(self.cards_table)
        self._load_card_detail()

    def _selected_card(self) -> Optional[Dict[str, Any]]:
        selected = self.cards_table.selectionModel().selectedRows()
        if not selected:
            return None
        row_index = selected[0].row()
        if 0 <= row_index < len(self._cards):
            return self._cards[row_index]
        return None

    def _selected_entry(self) -> Optional[Dict[str, Any]]:
        selected = self.entries_table.selectionModel().selectedRows()
        if not selected:
            return None
        row_index = selected[0].row()
        if 0 <= row_index < len(self._entries):
            return self._entries[row_index]
        return None

    def _load_card_detail(self) -> None:
        self._load_entries()
        self._load_derived_statement()

    def _load_entries(self) -> None:
        card = self._selected_card()
        if card is None:
            self._entries = []
            self.entries_table.setRowCount(0)
            return
        self._entries = self._entry_service.list_entries(int(card["id"]))
        self.entries_table.setRowCount(len(self._entries))
        for row_index, entry in enumerate(self._entries):
            values = [
                row_index + 1,
                entry["txn_date"],
                _entry_type_label(entry["entry_type"]),
                entry.get("description") or "",
                entry.get("category_name") or "—",
                entry["amount_display"],
            ]
            for col_index, value in enumerate(values):
                self.entries_table.setItem(row_index, col_index, QTableWidgetItem(str(value)))
        autosize_columns(self.entries_table)

    def _load_derived_statement(self) -> None:
        card = self._selected_card()
        self.period_combo.blockSignals(True)
        self.period_combo.clear()
        self._periods = []
        if card is not None:
            self._periods = self._statement_service.get_statements(int(card["id"]))
            for period in self._periods:
                label = (
                    f"{period['cut_date']}  •  Dönem Borcu: "
                    f"{period['period_debt_display']}"
                )
                self.period_combo.addItem(label)
        self.period_combo.blockSignals(False)
        if self._periods:
            self.period_combo.setCurrentIndex(len(self._periods) - 1)  # en güncel dönem
        self._fill_period_lines()

    def _fill_period_lines(self) -> None:
        index = self.period_combo.currentIndex()
        if not self._periods or index < 0 or index >= len(self._periods):
            self.period_summary.setText("—")
            self.lines_table.setRowCount(0)
            return
        period = self._periods[index]
        self.period_summary.setText(
            f"Devir: {period['opening_balance_display']}   |   "
            f"Harcama: {period['charges_display']}   |   "
            f"Ödeme: {period['payments_display']}   |   "
            f"Dönem Borcu: {period['period_debt_display']}"
            + (f"   |   Son Ödeme: {period['due_date']}" if period.get("due_date") else "")
        )
        lines = period["lines"]
        self.lines_table.setRowCount(len(lines))
        for row_index, line in enumerate(lines):
            values = [
                line["date"],
                line["type_label"],
                line["description"],
                line["signed_display"],
            ]
            for col_index, value in enumerate(values):
                self.lines_table.setItem(row_index, col_index, QTableWidgetItem(str(value)))
        autosize_columns(self.lines_table)

    # --- Kart CRUD ---

    def _on_add_card(self) -> None:
        banks = self._bank_service.list_banks()
        currencies = self._reference_service.list_currencies()
        if not banks or not currencies:
            show_error(self, "Eksik Tanım", "Banka ve para birimi tanımlı olmalıdır.")
            return
        dialog = CreditCardDialog(banks, currencies, self.window())
        if not dialog.exec_():
            return
        try:
            self._service.create_credit_card(dialog.get_values())
            show_success(self, "Başarılı", "Kredi kartı eklendi.")
            self.refresh()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))

    def _on_edit_card(self) -> None:
        card = self._selected_card()
        if card is None:
            show_error(self, "Seçim Gerekli", "Düzenlemek için bir kart seçin.")
            return
        banks = self._bank_service.list_banks(include_inactive=True)
        currencies = self._reference_service.list_currencies()
        dialog = CreditCardDialog(banks, currencies, self.window(), data=card)
        if not dialog.exec_():
            return
        try:
            self._service.update_credit_card(int(card["id"]), dialog.get_values())
            show_success(self, "Başarılı", "Kredi kartı güncellendi.")
            self.refresh()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))

    def _on_delete_card(self) -> None:
        card = self._selected_card()
        if card is None:
            show_error(self, "Seçim Gerekli", "Silmek için bir kart seçin.")
            return
        dialog = MessageBox(
            "Silme Onayı",
            f"'{card['name']}' kartını silmek istediğinize emin misiniz?",
            self.window(),
        )
        dialog.yesButton.setText("Sil")
        dialog.cancelButton.setText("İptal")
        if not dialog.exec_():
            return
        try:
            self._service.delete_credit_card(int(card["id"]))
            show_success(self, "Başarılı", "Kredi kartı silindi.")
            self.refresh()
        except (ValidationError, AppError) as exc:
            show_error(self, "Hata", str(exc))

    # --- Kart hareketi CRUD ---

    def _expense_categories(self) -> List[Dict[str, Any]]:
        return [
            c for c in self._reference_service.list_categories()
            if c["nature"] == Nature.EXPENSE
        ]

    def _on_add_entry(self) -> None:
        card = self._selected_card()
        if card is None:
            show_error(self, "Seçim Gerekli", "Hareket eklemek için bir kart seçin.")
            return
        dialog = CardEntryDialog(card, self._expense_categories(), self.window())
        if not dialog.exec_():
            return
        try:
            self._entry_service.create_entry(dialog.get_values())
            show_success(self, "Başarılı", "Kart hareketi eklendi.")
            self.refresh()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))

    def _on_edit_entry(self) -> None:
        card = self._selected_card()
        entry = self._selected_entry()
        if card is None or entry is None:
            show_error(self, "Seçim Gerekli", "Düzenlemek için bir hareket seçin.")
            return
        dialog = CardEntryDialog(card, self._expense_categories(), self.window(), data=entry)
        if not dialog.exec_():
            return
        try:
            self._entry_service.update_entry(int(entry["id"]), dialog.get_values())
            show_success(self, "Başarılı", "Kart hareketi güncellendi.")
            self.refresh()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))

    def _on_delete_entry(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            show_error(self, "Seçim Gerekli", "Silmek için bir hareket seçin.")
            return
        dialog = MessageBox(
            "Silme Onayı",
            "Seçili kart hareketini silmek istediğinize emin misiniz?",
            self.window(),
        )
        dialog.yesButton.setText("Sil")
        dialog.cancelButton.setText("İptal")
        if not dialog.exec_():
            return
        try:
            self._entry_service.delete_entry(int(entry["id"]))
            show_success(self, "Başarılı", "Kart hareketi silindi.")
            self.refresh()
        except (ValidationError, AppError) as exc:
            show_error(self, "Hata", str(exc))


def _entry_type_label(entry_type: str) -> str:
    from app.core.constants import CARD_ENTRY_TYPE_LABELS
    return CARD_ENTRY_TYPE_LABELS.get(entry_type, entry_type)
