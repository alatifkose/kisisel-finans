"""Kredi Kartları sayfası."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt5.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import MessageBox, PrimaryPushButton, PushButton, SubtitleLabel, TitleLabel

from app.core.exceptions import AppError, ValidationError
from app.modules.banks.dialogs.credit_card_dialogs import CardStatementDialog, CreditCardDialog
from app.modules.banks.pages._ui_helpers import active_label, show_error, show_success
from app.services.bank_service import BankService
from app.services.credit_card_service import CreditCardService
from app.services.reference_service import ReferenceService


class CreditCardsPage(QWidget):
    """Kredi kartı tanımı ve ekstre snapshot yönetimi."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service = CreditCardService()
        self._bank_service = BankService()
        self._reference_service = ReferenceService()
        self._cards: List[Dict[str, Any]] = []
        self._statements: List[Dict[str, Any]] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.setSpacing(16)
        layout.addWidget(TitleLabel("Kredi Kartları", self))

        splitter = QSplitter(self)
        layout.addWidget(splitter)

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
        self.cards_table.setColumnCount(11)
        self.cards_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Banka",
                "Kart Adı",
                "Para Birimi",
                "Kart Limiti",
                "Ekstre Günü",
                "Son Ödeme Günü",
                "Likidite Sayılır",
                "Aktif",
                "Not",
                "Son Ekstre Borcu",
            ]
        )
        self.cards_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cards_table.setSelectionMode(QTableWidget.SingleSelection)
        self.cards_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cards_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cards_table.verticalHeader().setVisible(False)
        cards_layout.addWidget(self.cards_table)
        splitter.addWidget(cards_widget)

        statements_widget = QWidget(self)
        statements_layout = QVBoxLayout(statements_widget)
        statements_layout.setContentsMargins(8, 0, 0, 0)
        statements_layout.addWidget(SubtitleLabel("Ekstreler", self))

        stmt_buttons = QHBoxLayout()
        self.add_stmt_button = PrimaryPushButton("Ekstre Ekle", self)
        self.edit_stmt_button = PushButton("Ekstre Düzenle", self)
        self.delete_stmt_button = PushButton("Ekstre Sil", self)
        self.refresh_stmt_button = PushButton("Yenile", self)
        for button in (
            self.add_stmt_button,
            self.edit_stmt_button,
            self.delete_stmt_button,
            self.refresh_stmt_button,
        ):
            stmt_buttons.addWidget(button)
        stmt_buttons.addStretch()
        statements_layout.addLayout(stmt_buttons)

        self.statements_table = QTableWidget(self)
        self.statements_table.setColumnCount(7)
        self.statements_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Ekstre Tarihi",
                "Ekstre Borcu",
                "Asgari Ödeme",
                "Son Ödeme Tarihi",
                "Kullanılabilir Limit",
                "Not",
            ]
        )
        self.statements_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.statements_table.setSelectionMode(QTableWidget.SingleSelection)
        self.statements_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.statements_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.statements_table.verticalHeader().setVisible(False)
        statements_layout.addWidget(self.statements_table)
        splitter.addWidget(statements_widget)
        splitter.setSizes([520, 420])

        self.add_card_button.clicked.connect(self._on_add_card)
        self.edit_card_button.clicked.connect(self._on_edit_card)
        self.delete_card_button.clicked.connect(self._on_delete_card)
        self.refresh_cards_button.clicked.connect(self.refresh)
        self.cards_table.itemSelectionChanged.connect(self._load_statements)

        self.add_stmt_button.clicked.connect(self._on_add_statement)
        self.edit_stmt_button.clicked.connect(self._on_edit_statement)
        self.delete_stmt_button.clicked.connect(self._on_delete_statement)
        self.refresh_stmt_button.clicked.connect(self._load_statements)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()

    def refresh(self) -> None:
        self._cards = self._service.list_credit_cards(include_inactive=True)
        self.cards_table.setRowCount(len(self._cards))
        for row_index, card in enumerate(self._cards):
            latest_debt = "—"
            latest = self._service.get_latest_statement(int(card["id"]))
            if latest:
                latest_debt = latest["statement_debt_display"]["display"]
            values = [
                card["id"],
                card["bank_name"],
                card["name"],
                card["currency_code"],
                card["card_limit_display"]["display"],
                card.get("statement_day") or "—",
                card.get("due_day") or "—",
                active_label(card["counts_as_liquidity"]),
                active_label(card["is_active"]),
                card.get("note") or "",
                latest_debt,
            ]
            for col_index, value in enumerate(values):
                self.cards_table.setItem(row_index, col_index, QTableWidgetItem(str(value)))
        self._load_statements()

    def _selected_card(self) -> Optional[Dict[str, Any]]:
        selected = self.cards_table.selectionModel().selectedRows()
        if not selected:
            return None
        row_index = selected[0].row()
        if 0 <= row_index < len(self._cards):
            return self._cards[row_index]
        return None

    def _selected_statement(self) -> Optional[Dict[str, Any]]:
        selected = self.statements_table.selectionModel().selectedRows()
        if not selected:
            return None
        row_index = selected[0].row()
        if 0 <= row_index < len(self._statements):
            return self._statements[row_index]
        return None

    def _load_statements(self) -> None:
        card = self._selected_card()
        if card is None:
            self._statements = []
            self.statements_table.setRowCount(0)
            return
        self._statements = self._service.list_statements(int(card["id"]))
        self.statements_table.setRowCount(len(self._statements))
        for row_index, stmt in enumerate(self._statements):
            available = stmt.get("available_limit_display", {}).get("display", "—")
            values = [
                stmt["id"],
                stmt["statement_date"],
                stmt["statement_debt_display"]["display"],
                stmt["min_payment_display"]["display"],
                stmt.get("due_date") or "—",
                available,
                stmt.get("note") or "",
            ]
            for col_index, value in enumerate(values):
                self.statements_table.setItem(
                    row_index, col_index, QTableWidgetItem(str(value))
                )

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
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))
        except AppError as exc:
            show_error(self, "Hata", str(exc))

    def _on_add_statement(self) -> None:
        card = self._selected_card()
        if card is None:
            show_error(self, "Seçim Gerekli", "Ekstre eklemek için bir kart seçin.")
            return
        dialog = CardStatementDialog(card, self.window())
        if not dialog.exec_():
            return
        try:
            self._service.add_statement(dialog.get_values())
            show_success(self, "Başarılı", "Ekstre eklendi.")
            self.refresh()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))

    def _on_edit_statement(self) -> None:
        card = self._selected_card()
        stmt = self._selected_statement()
        if card is None or stmt is None:
            show_error(self, "Seçim Gerekli", "Düzenlemek için bir ekstre seçin.")
            return
        dialog = CardStatementDialog(card, self.window(), data=stmt)
        if not dialog.exec_():
            return
        try:
            self._service.update_statement(int(stmt["id"]), dialog.get_values())
            show_success(self, "Başarılı", "Ekstre güncellendi.")
            self.refresh()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))

    def _on_delete_statement(self) -> None:
        stmt = self._selected_statement()
        if stmt is None:
            show_error(self, "Seçim Gerekli", "Silmek için bir ekstre seçin.")
            return
        dialog = MessageBox(
            "Silme Onayı",
            "Seçili ekstreyi silmek istediğinize emin misiniz?",
            self.window(),
        )
        dialog.yesButton.setText("Sil")
        dialog.cancelButton.setText("İptal")
        if not dialog.exec_():
            return
        try:
            self._service.delete_statement(int(stmt["id"]))
            show_success(self, "Başarılı", "Ekstre silindi.")
            self.refresh()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))
        except AppError as exc:
            show_error(self, "Hata", str(exc))
