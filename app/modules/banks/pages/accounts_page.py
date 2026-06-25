"""Hesaplar sayfası."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, ComboBox, MessageBox, PrimaryPushButton, PushButton, TitleLabel

from app.core.event_bus import event_bus
from app.core.exceptions import AppError, ValidationError
from app.core.money import format_amount
from app.modules.banks.dialogs.bank_account_dialogs import AccountDialog
from app.modules.banks.pages._ui_helpers import active_label, show_error, show_success
from app.services.account_service import AccountService
from app.services.bank_service import BankService
from app.services.reference_service import ReferenceService


class AccountsPage(QWidget):
    """Banka hesapları yönetim sayfası."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._account_service = AccountService()
        self._bank_service = BankService()
        self._reference_service = ReferenceService()
        self._rows: List[Dict[str, Any]] = []
        self._build_ui()
        self._load_bank_filter()
        self.refresh()
        event_bus.subscribe("account_balance_changed", self._on_balance_changed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.setSpacing(16)

        layout.addWidget(TitleLabel("Hesaplar", self))

        filter_row = QHBoxLayout()
        filter_row.addWidget(BodyLabel("Banka Filtresi:", self))
        self.bank_filter = ComboBox(self)
        self.bank_filter.setMinimumWidth(240)
        self.bank_filter.currentIndexChanged.connect(self.refresh)
        filter_row.addWidget(self.bank_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        button_row = QHBoxLayout()
        self.add_button = PrimaryPushButton("Ekle", self)
        self.edit_button = PushButton("Düzenle", self)
        self.delete_button = PushButton("Sil", self)
        self.refresh_button = PushButton("Yenile", self)
        button_row.addWidget(self.add_button)
        button_row.addWidget(self.edit_button)
        button_row.addWidget(self.delete_button)
        button_row.addWidget(self.refresh_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.table = QTableWidget(self)
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Banka",
                "Hesap Adı",
                "Para Birimi",
                "Açılış Bakiyesi",
                "Güncel Bakiye",
                "Takip Modu",
                "Aktif",
                "Not",
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        self.add_button.clicked.connect(self._on_add)
        self.edit_button.clicked.connect(self._on_edit)
        self.delete_button.clicked.connect(self._on_delete)
        self.refresh_button.clicked.connect(self.refresh)

    def _load_bank_filter(self) -> None:
        self.bank_filter.blockSignals(True)
        self.bank_filter.clear()
        self.bank_filter.addItem("Tümü", userData=None)
        for bank in self._bank_service.list_banks(include_inactive=True):
            self.bank_filter.addItem(bank["name"], userData=bank["id"])
        self.bank_filter.blockSignals(False)

    def refresh(self) -> None:
        bank_id = self.bank_filter.currentData()
        if bank_id is None:
            self._rows = self._account_service.list_accounts(include_inactive=True)
        else:
            self._rows = self._account_service.list_accounts_by_bank(
                bank_id,
                include_inactive=True,
            )

        self.table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            scale = int(row["currency_scale"])
            values = [
                row["id"],
                row["bank_name"],
                row["name"],
                row["currency_code"],
                format_amount(int(row["opening_balance"]), scale),
                format_amount(int(row["current_balance"]), scale),
                row["tracking_mode"],
                active_label(row["is_active"]),
                row.get("note") or "",
            ]
            for col_index, value in enumerate(values):
                self.table.setItem(row_index, col_index, QTableWidgetItem(str(value)))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._load_bank_filter()
        self.refresh()

    def _on_balance_changed(self, _data=None) -> None:
        self.refresh()

    def _selected_row(self) -> Optional[Dict[str, Any]]:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row_index = selected[0].row()
        if 0 <= row_index < len(self._rows):
            return self._rows[row_index]
        return None

    def _handle_action(self, action: Callable[[], None], success_message: str) -> None:
        try:
            action()
            show_success(self, "Başarılı", success_message)
            self._load_bank_filter()
            self.refresh()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))
        except AppError as exc:
            show_error(self, "Hata", str(exc))

    def _on_add(self) -> None:
        banks = self._bank_service.list_banks()
        if not banks:
            show_error(self, "Banka Gerekli", "Önce en az bir banka eklemelisiniz.")
            return
        currencies = self._reference_service.list_currencies()
        if not currencies:
            show_error(self, "Para Birimi Gerekli", "Önce en az bir para birimi tanımlayın.")
            return

        dialog = AccountDialog(banks, currencies, self.window())
        if not dialog.exec_():
            return
        values = dialog.get_values()

        def action() -> None:
            self._account_service.create_account(
                values["bank_id"],
                values["name"],
                values["currency_id"],
                values["opening_balance_text"],
                values["note"],
                values["tracking_mode"],
            )

        self._handle_action(action, "Hesap eklendi.")

    def _on_edit(self) -> None:
        row = self._selected_row()
        if row is None:
            show_error(self, "Seçim Gerekli", "Düzenlemek için bir hesap seçin.")
            return

        banks = self._bank_service.list_banks(include_inactive=True)
        currencies = self._reference_service.list_currencies()
        dialog = AccountDialog(banks, currencies, self.window(), data=row)
        if not dialog.exec_():
            return
        values = dialog.get_values()

        def action() -> None:
            self._account_service.update_account(
                int(row["id"]),
                values["bank_id"],
                values["name"],
                values["currency_id"],
                values["opening_balance_text"],
                values["current_balance_text"],
                values["tracking_mode"],
                values["is_active"],
                values["note"],
            )

        self._handle_action(action, "Hesap güncellendi.")

    def _on_delete(self) -> None:
        row = self._selected_row()
        if row is None:
            show_error(self, "Seçim Gerekli", "Silmek için bir hesap seçin.")
            return

        dialog = MessageBox(
            "Silme Onayı",
            f"'{row['name']}' hesabını silmek istediğinize emin misiniz?",
            self.window(),
        )
        dialog.yesButton.setText("Sil")
        dialog.cancelButton.setText("İptal")
        if not dialog.exec_():
            return

        def action() -> None:
            self._account_service.delete_account(int(row["id"]))

        self._handle_action(action, "Hesap silindi.")
