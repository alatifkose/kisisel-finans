"""Taksit ödeme dialogu."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, ComboBox, PrimaryPushButton, PushButton, SubtitleLabel

from app.core.constants import NATURE_LABELS, Nature


class PayInstallmentDialog(QDialog):
    """Planlanmış taksit için ödeme girişi."""

    def __init__(
        self,
        installment: Dict[str, Any],
        accounts: List[Dict[str, Any]],
        expense_categories: List[Dict[str, Any]],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._installment = installment
        self._accounts = accounts
        self._expense_categories = expense_categories
        self._category_combos: Dict[int, ComboBox] = {}

        self.setWindowTitle("Taksit Öde")
        self.setModal(True)
        self.setMinimumSize(640, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(SubtitleLabel("Taksit Ödeme", self))

        info = QFormLayout()
        info.addRow("Plan", BodyLabel(str(installment["plan_name"]), self))
        info.addRow("Taksit No", BodyLabel(str(installment["seq"]), self))
        info.addRow("Vade Tarihi", BodyLabel(str(installment["due_date"]), self))
        info.addRow(
            "Taksit Toplamı",
            BodyLabel(installment["total_amount_display"]["display"], self),
        )
        info.addRow("Para Birimi", BodyLabel(str(installment["currency_code"]), self))
        layout.addLayout(info)

        layout.addWidget(SubtitleLabel("Bileşenler", self))
        self.component_table = QTableWidget(self)
        self.component_table.setColumnCount(3)
        self.component_table.setHorizontalHeaderLabels(["Bileşen", "Nitelik", "Tutar"])
        self.component_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.component_table.verticalHeader().setVisible(False)
        self.component_table.setEditTriggers(QTableWidget.NoEditTriggers)
        components = installment.get("components") or []
        self.component_table.setRowCount(len(components))
        for row_index, comp in enumerate(components):
            values = [
                comp.get("component_name") or comp.get("component_code") or "",
                NATURE_LABELS.get(comp.get("component_nature"), comp.get("component_nature", "")),
                comp["amount_display"]["display"],
            ]
            for col_index, value in enumerate(values):
                self.component_table.setItem(row_index, col_index, QTableWidgetItem(str(value)))
        layout.addWidget(self.component_table)

        form = QFormLayout()
        self.account_combo = ComboBox(self)
        for account in accounts:
            mode_label = "Defter" if account.get("tracking_mode") == "ledger" else "Snapshot"
            label = f"{account['bank_name']} - {account['name']} ({mode_label})"
            self.account_combo.addItem(label, userData=account["id"])

        self.paid_date_edit = QDateEdit(self)
        self.paid_date_edit.setCalendarPopup(True)
        self.paid_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.paid_date_edit.setDate(QDate.currentDate())

        form.addRow("Ödeme Hesabı", self.account_combo)
        form.addRow("Ödeme Tarihi", self.paid_date_edit)
        layout.addLayout(form)

        expense_components = [
            comp for comp in components if comp.get("component_nature") == Nature.EXPENSE
        ]
        if expense_components:
            layout.addWidget(SubtitleLabel("Gider Kategorileri", self))
            category_form = QFormLayout()
            for comp in expense_components:
                combo = ComboBox(self)
                combo.addItem("— Seçin —", userData=None)
                default_category_id = comp.get("default_category_id")
                for category in expense_categories:
                    combo.addItem(category["name"], userData=category["id"])
                if default_category_id is not None:
                    index = combo.findData(default_category_id)
                    if index >= 0:
                        combo.setCurrentIndex(index)
                category_form.addRow(
                    comp.get("component_name") or comp.get("component_code") or "Bileşen",
                    combo,
                )
                self._category_combos[int(comp["component_type_id"])] = combo
            layout.addLayout(category_form)

        amount_display = installment["total_amount_display"]["display"]
        symbol = installment["total_amount_display"].get("currency_symbol") or ""
        suffix = f" {symbol}".rstrip()
        self.summary_label = BodyLabel(
            f"Bu işlem seçilen hesaptan {amount_display}{suffix} tutarında çıkış "
            "oluşturacak ve taksiti ödendi işaretleyecek.",
            self,
        )
        layout.addWidget(self.summary_label)

        button_row = QHBoxLayout()
        button_row.addStretch()
        self.confirm_button = PrimaryPushButton("Ödemeyi Onayla", self)
        self.cancel_button = PushButton("İptal", self)
        button_row.addWidget(self.confirm_button)
        button_row.addWidget(self.cancel_button)
        layout.addLayout(button_row)

        self.confirm_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def get_payment_data(self) -> Dict[str, Any]:
        category_overrides: Dict[int, int] = {}
        for component_type_id, combo in self._category_combos.items():
            category_id = combo.currentData()
            if category_id is not None:
                category_overrides[component_type_id] = int(category_id)
        return {
            "installment_id": int(self._installment["id"]),
            "account_id": int(self.account_combo.currentData()),
            "paid_date": self.paid_date_edit.date().toString("yyyy-MM-dd"),
            "category_overrides": category_overrides,
        }
