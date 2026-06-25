"""Para Hareketleri sayfası."""

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

from app.core.constants import (
    DIRECTION_LABELS,
    SOURCE_INSTALLMENT,
    SOURCE_LABELS,
    SOURCE_MANUAL,
    SOURCE_TRANSFER,
)
from app.core.exceptions import AppError, ValidationError
from app.core.money import format_amount
from app.modules.banks.dialogs.add_transaction_dialog import AddTransactionDialog
from app.modules.banks.pages._ui_helpers import active_label, show_error, show_success
from app.services.account_service import AccountService
from app.services.reference_service import ReferenceService
from app.services.transaction_service import TransactionService


class TransactionsPage(QWidget):
    """Para hareketleri yönetim sayfası."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._transaction_service = TransactionService()
        self._account_service = AccountService()
        self._reference_service = ReferenceService()
        self._rows: List[Dict[str, Any]] = []
        self._build_ui()
        self._load_account_filter()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.setSpacing(16)

        layout.addWidget(TitleLabel("Para Hareketleri", self))

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
                "Tarih",
                "Banka",
                "Hesap",
                "Yön",
                "Toplam Tutar",
                "Açıklama",
                "Bakiye Etkiler",
                "Kaynak",
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

    def _load_account_filter(self) -> None:
        self.account_filter.blockSignals(True)
        self.account_filter.clear()
        self.account_filter.addItem("Tümü", userData=None)
        for account in self._account_service.list_accounts(include_inactive=True):
            label = f"{account['bank_name']} - {account['name']}"
            self.account_filter.addItem(label, userData=account["id"])
        self.account_filter.blockSignals(False)

    def refresh(self) -> None:
        account_id = self.account_filter.currentData()
        if account_id is None:
            self._rows = self._transaction_service.list_transactions()
        else:
            self._rows = self._transaction_service.list_transactions_by_account(account_id)

        self.table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            scale = int(row["currency_scale"])
            values = [
                row["id"],
                row["txn_date"],
                row["bank_name"],
                row["account_name"],
                DIRECTION_LABELS.get(row["direction"], row["direction"]),
                format_amount(int(row["total_amount"]), scale),
                row.get("description") or "",
                active_label(row["affects_balance"]),
                SOURCE_LABELS.get(row.get("source_type") or SOURCE_MANUAL, row.get("source_type") or SOURCE_MANUAL),
            ]
            for col_index, value in enumerate(values):
                self.table.setItem(row_index, col_index, QTableWidgetItem(str(value)))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._load_account_filter()
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
            self.refresh()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))
        except AppError as exc:
            show_error(self, "Hata", str(exc))

    def _on_add(self) -> None:
        accounts = self._account_service.list_accounts()
        if not accounts:
            show_error(self, "Hesap Gerekli", "Önce en az bir hesap tanımlayın.")
            return

        categories = self._reference_service.list_categories()
        assets = self._reference_service.list_assets()
        dialog = AddTransactionDialog(accounts, categories, assets, self.window())
        if not dialog.exec_():
            return
        values = dialog.get_values()

        def action() -> None:
            self._transaction_service.create_transaction(
                values["account_id"],
                values["txn_date"],
                values["direction"],
                values["total_amount_text"],
                values["description"],
                values["affects_balance"],
                values["lines"],
            )

        self._handle_action(action, "Para hareketi eklendi.")

    def _on_edit(self) -> None:
        row = self._selected_row()
        if row is None:
            show_error(self, "Seçim Gerekli", "Düzenlemek için bir işlem seçin.")
            return

        if (row.get("source_type") or SOURCE_MANUAL) != SOURCE_MANUAL:
            self._show_non_manual_edit_error(row)
            return

        txn = self._transaction_service.get_transaction(int(row["id"]))
        if txn is None:
            show_error(self, "Hata", "İşlem bulunamadı.")
            return

        accounts = self._account_service.list_accounts(include_inactive=True)
        categories = self._reference_service.list_categories()
        assets = self._reference_service.list_assets()
        dialog = AddTransactionDialog(
            accounts,
            categories,
            assets,
            self.window(),
            data=txn,
        )
        if not dialog.exec_():
            return
        values = dialog.get_values()

        def action() -> None:
            self._transaction_service.update_transaction(
                int(row["id"]),
                values["account_id"],
                values["txn_date"],
                values["direction"],
                values["total_amount_text"],
                values["description"],
                values["affects_balance"],
                values["lines"],
            )

        self._handle_action(action, "Para hareketi güncellendi.")

    def _on_delete(self) -> None:
        row = self._selected_row()
        if row is None:
            show_error(self, "Seçim Gerekli", "Silmek için bir işlem seçin.")
            return

        if (row.get("source_type") or SOURCE_MANUAL) != SOURCE_MANUAL:
            self._show_non_manual_delete_error(row)
            return

        dialog = MessageBox(
            "Silme Onayı",
            f"Seçili para hareketini silmek istediğinize emin misiniz?",
            self.window(),
        )
        dialog.yesButton.setText("Sil")
        dialog.cancelButton.setText("İptal")
        if not dialog.exec_():
            return

        def action() -> None:
            self._transaction_service.delete_transaction(int(row["id"]))

        self._handle_action(action, "Para hareketi silindi.")

    def _show_non_manual_edit_error(self, row: Dict[str, Any]) -> None:
        source = row.get("source_type") or SOURCE_MANUAL
        if source == SOURCE_TRANSFER:
            message = (
                "Transferden oluşan işlem buradan düzenlenemez veya silinemez. "
                "Transferler sayfasından transferi geri alın."
            )
        elif source == SOURCE_INSTALLMENT:
            message = (
                "Taksit ödemesinden oluşan işlem buradan düzenlenemez. "
                "İlgili taksitten ödemeyi geri alın."
            )
        else:
            message = "Bu işlem buradan düzenlenemez."
        show_error(self, "Düzenleme Engellendi", message)

    def _show_non_manual_delete_error(self, row: Dict[str, Any]) -> None:
        source = row.get("source_type") or SOURCE_MANUAL
        if source == SOURCE_TRANSFER:
            message = (
                "Transferden oluşan işlem buradan düzenlenemez veya silinemez. "
                "Transferler sayfasından transferi geri alın."
            )
        elif source == SOURCE_INSTALLMENT:
            message = (
                "Bu işlem taksit ödemesine bağlı. "
                "Silmek için ilgili taksitte Ödemeyi Geri Al kullanın."
            )
        else:
            message = "Bu işlem buradan silinemez."
        show_error(self, "Silme Engellendi", message)
