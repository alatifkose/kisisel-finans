"""KMH / Ek Hesap sayfası."""

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

from app.core.exceptions import AppError, ValidationError
from app.modules.banks.dialogs.kmh_dialogs import KmhAccountDialog, KmhUsageDialog
from app.modules.banks.pages._ui_helpers import active_label, show_error, show_info, show_success
from app.ui.table_utils import autosize_columns
from app.services.account_service import AccountService
from app.services.bank_service import BankService
from app.services.kmh_service import KmhService


class KmhPage(QWidget):
    """KMH / Ek Hesap yönetim sayfası."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service = KmhService()
        self._bank_service = BankService()
        self._account_service = AccountService()
        self._rows: List[Dict[str, Any]] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.setSpacing(16)
        layout.addWidget(TitleLabel("KMH / Ek Hesap", self))

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
        self.usage_button = PushButton("Kullanım Güncelle", self)
        self.delete_button = PushButton("Sil", self)
        self.refresh_button = PushButton("Yenile", self)
        for button in (
            self.add_button,
            self.edit_button,
            self.usage_button,
            self.delete_button,
            self.refresh_button,
        ):
            button_row.addWidget(button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.table = QTableWidget(self)
        self.table.setColumnCount(12)
        self.table.setHorizontalHeaderLabels(
            [
                "#",
                "Banka",
                "Bağlı Hesap",
                "Para Birimi",
                "KMH Adı",
                "Limit",
                "Kullanılan",
                "Kullanılabilir",
                "Faiz Oranı",
                "Likidite Sayılır",
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
        self.usage_button.clicked.connect(self._on_update_usage)
        self.delete_button.clicked.connect(self._on_delete)
        self.refresh_button.clicked.connect(self.refresh)

    def _load_bank_filter(self) -> None:
        self.bank_filter.blockSignals(True)
        self.bank_filter.clear()
        self.bank_filter.addItem("Tümü", userData=None)
        for bank in self._bank_service.list_banks(include_inactive=True):
            self.bank_filter.addItem(bank["name"], userData=bank["id"])
        self.bank_filter.blockSignals(False)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._load_bank_filter()
        self.refresh()

    def refresh(self) -> None:
        bank_id = self.bank_filter.currentData()
        if bank_id is None:
            self._rows = self._service.list_kmh_accounts(include_inactive=True)
        else:
            self._rows = self._service.list_kmh_accounts_by_bank(
                int(bank_id),
                include_inactive=True,
            )

        self.table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            values = [
                row_index + 1,
                row["bank_name"],
                row["account_name"],
                row["currency_code"],
                row["name"],
                row["kmh_limit_display"]["display"],
                row["used_amount_display"]["display"],
                row["available_amount_display"]["display"],
                row.get("interest_rate") or "—",
                active_label(row["counts_as_liquidity"]),
                active_label(row["is_active"]),
                row.get("note") or "",
            ]
            for col_index, value in enumerate(values):
                self.table.setItem(row_index, col_index, QTableWidgetItem(str(value)))
        autosize_columns(self.table)

    def _selected_row(self) -> Optional[Dict[str, Any]]:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row_index = selected[0].row()
        if 0 <= row_index < len(self._rows):
            return self._rows[row_index]
        return None

    def _show_warnings(self, warnings: List[str]) -> None:
        for message in warnings:
            show_info(self, "Uyarı", message)

    def _on_add(self) -> None:
        banks = self._bank_service.list_banks()
        accounts = self._account_service.list_accounts()
        if not banks or not accounts:
            show_error(self, "Eksik Tanım", "Banka ve hesap tanımlı olmalıdır.")
            return
        dialog = KmhAccountDialog(banks, accounts, self.window())
        if not dialog.exec_():
            return
        try:
            _, warnings = self._service.create_kmh_account(dialog.get_values())
            show_success(self, "Başarılı", "KMH hesabı eklendi.")
            self._show_warnings(warnings)
            self.refresh()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))

    def _on_edit(self) -> None:
        row = self._selected_row()
        if row is None:
            show_error(self, "Seçim Gerekli", "Düzenlemek için bir KMH seçin.")
            return
        banks = self._bank_service.list_banks(include_inactive=True)
        accounts = self._account_service.list_accounts(include_inactive=True)
        dialog = KmhAccountDialog(banks, accounts, self.window(), data=row)
        if not dialog.exec_():
            return
        try:
            warnings = self._service.update_kmh_account(int(row["id"]), dialog.get_values())
            show_success(self, "Başarılı", "KMH hesabı güncellendi.")
            self._show_warnings(warnings)
            self.refresh()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))

    def _on_update_usage(self) -> None:
        row = self._selected_row()
        if row is None:
            show_error(self, "Seçim Gerekli", "Güncellemek için bir KMH seçin.")
            return
        dialog = KmhUsageDialog(row, self.window())
        if not dialog.exec_():
            return
        try:
            warnings = self._service.update_kmh_usage(
                int(row["id"]),
                dialog.get_used_amount_text(),
            )
            show_success(self, "Başarılı", "KMH kullanım tutarı güncellendi.")
            self._show_warnings(warnings)
            self.refresh()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))

    def _on_delete(self) -> None:
        row = self._selected_row()
        if row is None:
            show_error(self, "Seçim Gerekli", "Silmek için bir KMH seçin.")
            return
        dialog = MessageBox(
            "Silme Onayı",
            f"'{row['name']}' KMH hesabını silmek istediğinize emin misiniz?",
            self.window(),
        )
        dialog.yesButton.setText("Sil")
        dialog.cancelButton.setText("İptal")
        if not dialog.exec_():
            return
        try:
            self._service.delete_kmh_account(int(row["id"]))
            show_success(self, "Başarılı", "KMH hesabı silindi.")
            self.refresh()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))
        except AppError as exc:
            show_error(self, "Hata", str(exc))
