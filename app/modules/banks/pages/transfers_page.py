"""Transferler sayfası."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

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
from app.modules.banks.dialogs.add_transfer_dialog import AddTransferDialog
from app.modules.banks.pages._ui_helpers import show_error, show_success
from app.services.account_service import AccountService
from app.services.transfer_service import TransferService


class TransfersPage(QWidget):
    """Hesaplar arası transfer yönetim sayfası."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service = TransferService()
        self._account_service = AccountService()
        self._rows: List[Dict[str, Any]] = []
        self._build_ui()
        self.refresh()
        event_bus.subscribe("account_balance_changed", self._on_data_changed)
        event_bus.subscribe("transfer_created", self._on_data_changed)
        event_bus.subscribe("transfer_deleted", self._on_data_changed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.setSpacing(16)
        layout.addWidget(TitleLabel("Transferler", self))

        filter_row = QHBoxLayout()
        filter_row.addWidget(BodyLabel("Hesap Filtresi:", self))
        self.account_filter = ComboBox(self)
        self.account_filter.setMinimumWidth(280)
        self.account_filter.currentIndexChanged.connect(self.refresh)
        filter_row.addWidget(self.account_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        button_row = QHBoxLayout()
        self.add_button = PrimaryPushButton("Ekle", self)
        self.delete_button = PushButton("Sil / Geri Al", self)
        self.refresh_button = PushButton("Yenile", self)
        for button in (self.add_button, self.delete_button, self.refresh_button):
            button_row.addWidget(button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.table = QTableWidget(self)
        self.table.setColumnCount(13)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Tarih",
                "Kaynak Banka",
                "Kaynak Hesap",
                "Kaynak Tutar",
                "Kaynak PB",
                "Hedef Banka",
                "Hedef Hesap",
                "Hedef Tutar",
                "Hedef PB",
                "Kur",
                "Açıklama",
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        self.add_button.clicked.connect(self._on_add)
        self.delete_button.clicked.connect(self._on_delete)
        self.refresh_button.clicked.connect(self.refresh)

    def _on_data_changed(self, _data=None) -> None:
        self.refresh()

    def _load_account_filter(self) -> None:
        self.account_filter.blockSignals(True)
        self.account_filter.clear()
        self.account_filter.addItem("Tümü", userData=None)
        for account in self._account_service.list_accounts(include_inactive=True):
            label = f"{account['bank_name']} — {account['name']}"
            self.account_filter.addItem(label, userData=account["id"])
        self.account_filter.blockSignals(False)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._load_account_filter()
        self.refresh()

    def refresh(self) -> None:
        account_id = self.account_filter.currentData()
        if account_id is None:
            self._rows = self._service.list_transfers()
        else:
            self._rows = self._service.list_transfers_by_account(int(account_id))

        self.table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            values = [
                row["id"],
                row["transfer_date"],
                row["from_bank_name"],
                row["from_account_name"],
                row["from_amount_display"]["display"],
                row["from_currency_code"],
                row["to_bank_name"],
                row["to_account_name"],
                row["to_amount_display"]["display"],
                row["to_currency_code"],
                row.get("exchange_rate") or "—",
                row.get("description") or "",
            ]
            for col_index, value in enumerate(values):
                self.table.setItem(row_index, col_index, QTableWidgetItem(str(value)))

    def _selected_row(self) -> Optional[Dict[str, Any]]:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row_index = selected[0].row()
        if 0 <= row_index < len(self._rows):
            return self._rows[row_index]
        return None

    def _on_add(self) -> None:
        accounts = self._account_service.list_accounts()
        if len(accounts) < 2:
            show_error(
                self,
                "Hesap Gerekli",
                "Transfer için en az iki aktif hesap tanımlı olmalıdır.",
            )
            return
        dialog = AddTransferDialog(accounts, self.window())
        if not dialog.exec_():
            return
        try:
            self._service.create_transfer(dialog.get_values())
            show_success(self, "Başarılı", "Transfer kaydedildi.")
            self.refresh()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))

    def _on_delete(self) -> None:
        row = self._selected_row()
        if row is None:
            show_error(self, "Seçim Gerekli", "Geri almak için bir transfer seçin.")
            return
        dialog = MessageBox(
            "Transfer Geri Al",
            "Bu transfer geri alınacak. Kaynak ve hedef hesap bakiyeleri eski haline "
            "döndürülecek. Devam edilsin mi?",
            self.window(),
        )
        dialog.yesButton.setText("Geri Al")
        dialog.cancelButton.setText("İptal")
        if not dialog.exec_():
            return
        try:
            self._service.delete_transfer(int(row["id"]))
            show_success(self, "Başarılı", "Transfer geri alındı.")
            self.refresh()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))
        except AppError as exc:
            show_error(self, "Hata", str(exc))
