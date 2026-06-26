"""Banka yönetimi bölümü — tablo ve CRUD."""

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
from qfluentwidgets import MessageBox, PrimaryPushButton, PushButton, SubtitleLabel

from app.core.exceptions import AppError, ValidationError
from app.modules.banks.dialogs.bank_account_dialogs import BankDialog
from app.modules.banks.pages._ui_helpers import active_label, show_error, show_success
from app.ui.table_utils import autosize_columns
from app.services.bank_service import BankService


class BankManagementSection(QWidget):
    """Banka listesi ve CRUD işlemleri."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._bank_service = BankService()
        self._bank_rows: List[Dict[str, Any]] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(SubtitleLabel("Bankalar", self))

        button_row = QHBoxLayout()
        self.add_bank_button = PrimaryPushButton("Ekle", self)
        self.edit_bank_button = PushButton("Düzenle", self)
        self.delete_bank_button = PushButton("Sil", self)
        self.refresh_bank_button = PushButton("Yenile", self)
        button_row.addWidget(self.add_bank_button)
        button_row.addWidget(self.edit_bank_button)
        button_row.addWidget(self.delete_bank_button)
        button_row.addWidget(self.refresh_bank_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.bank_table = QTableWidget(self)
        self.bank_table.setColumnCount(5)
        self.bank_table.setHorizontalHeaderLabels(
            ["#", "Banka Adı", "Kısa Ad", "Aktif", "Not"]
        )
        self.bank_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.bank_table.setSelectionMode(QTableWidget.SingleSelection)
        self.bank_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.bank_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.bank_table.verticalHeader().setVisible(False)
        layout.addWidget(self.bank_table)

        self.add_bank_button.clicked.connect(self._open_add_bank_dialog)
        self.edit_bank_button.clicked.connect(self._on_edit_bank)
        self.delete_bank_button.clicked.connect(self._on_delete_bank)
        self.refresh_bank_button.clicked.connect(self.refresh)

    def refresh(self) -> None:
        self._bank_rows = self._bank_service.list_banks(include_inactive=True)
        self.bank_table.setRowCount(len(self._bank_rows))
        for row_index, row in enumerate(self._bank_rows):
            values = [
                row_index + 1,
                row["name"],
                row.get("short_name") or "",
                active_label(row["is_active"]),
                row.get("note") or "",
            ]
            for col_index, value in enumerate(values):
                self.bank_table.setItem(
                    row_index,
                    col_index,
                    QTableWidgetItem(str(value)),
                )
        autosize_columns(self.bank_table)

    def _selected_bank(self) -> Optional[Dict[str, Any]]:
        selected = self.bank_table.selectionModel().selectedRows()
        if not selected:
            return None
        row_index = selected[0].row()
        if 0 <= row_index < len(self._bank_rows):
            return self._bank_rows[row_index]
        return None

    def _handle_bank_action(self, action: Callable[[], None], success_message: str) -> None:
        try:
            action()
            show_success(self, "Başarılı", success_message)
            self.refresh()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))
        except AppError as exc:
            show_error(self, "Hata", str(exc))

    def _open_add_bank_dialog(self) -> None:
        dialog = BankDialog(self.window())
        if not dialog.exec_():
            return
        values = dialog.get_values()

        def action() -> None:
            self._bank_service.create_bank(
                values["name"],
                values["short_name"],
                values["note"],
            )

        self._handle_bank_action(action, "Banka eklendi.")

    def _on_edit_bank(self) -> None:
        row = self._selected_bank()
        if row is None:
            show_error(self, "Seçim Gerekli", "Düzenlemek için bir banka seçin.")
            return
        dialog = BankDialog(self.window(), data=row)
        if not dialog.exec_():
            return
        values = dialog.get_values()

        def action() -> None:
            self._bank_service.update_bank(
                int(row["id"]),
                values["name"],
                values["short_name"],
                values["is_active"],
                values["note"],
            )

        self._handle_bank_action(action, "Banka güncellendi.")

    def _on_delete_bank(self) -> None:
        row = self._selected_bank()
        if row is None:
            show_error(self, "Seçim Gerekli", "Silmek için bir banka seçin.")
            return
        dialog = MessageBox(
            "Silme Onayı",
            f"'{row['name']}' bankasını silmek istediğinize emin misiniz?",
            self.window(),
        )
        dialog.yesButton.setText("Sil")
        dialog.cancelButton.setText("İptal")
        if not dialog.exec_():
            return

        def action() -> None:
            self._bank_service.delete_bank(int(row["id"]))

        self._handle_bank_action(action, "Banka silindi.")
