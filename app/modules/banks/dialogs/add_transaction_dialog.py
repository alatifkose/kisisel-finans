"""Para hareketi ekleme/düzenleme dialogu."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QDateEdit, QDialog, QFormLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
    SwitchButton,
    TextEdit,
)

from app.core.constants import (
    DIRECTION_LABELS,
    Direction,
    NATURE_LABELS,
    Nature,
)
from app.core.money import format_amount


class AddTransactionDialog(QDialog):
    """Tek satırlı gelir/gider/masraf işlemi dialogu."""

    def __init__(
        self,
        accounts: List[Dict[str, Any]],
        categories: List[Dict[str, Any]],
        assets: List[Dict[str, Any]],
        parent: Optional[QWidget] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(parent)
        self._categories = categories
        self._assets = assets
        self._data = data
        self._is_edit = data is not None

        title = "Para Hareketi" if data is None else "Para Hareketini Düzenle"
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(SubtitleLabel(title, self))

        self._form = QFormLayout()
        self._form.setSpacing(12)
        layout.addLayout(self._form)

        self.account_combo = ComboBox(self)
        for account in accounts:
            label = (
                f"{account['bank_name']} - {account['name']} "
                f"({account['currency_code']})"
            )
            self.account_combo.addItem(label, userData=account)

        self.date_edit = QDateEdit(self)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setDate(QDate.currentDate())

        self.direction_combo = ComboBox(self)
        self.direction_combo.addItem(DIRECTION_LABELS[Direction.IN], userData=Direction.IN)
        self.direction_combo.addItem(DIRECTION_LABELS[Direction.OUT], userData=Direction.OUT)

        self.total_amount_edit = LineEdit(self)
        self.total_amount_edit.setPlaceholderText("0,00")

        self.description_edit = LineEdit(self)

        self.affects_balance_switch = SwitchButton(self)
        self.affects_balance_switch.setChecked(True)

        layout.addWidget(BodyLabel("İşlem Satırı", self))

        self.nature_combo = ComboBox(self)
        self.category_combo = ComboBox(self)
        self.asset_combo = ComboBox(self)
        self.asset_combo.addItem("—", userData=None)
        for asset in assets:
            self.asset_combo.addItem(asset["name"], userData=asset["id"])

        self.line_note_edit = TextEdit(self)
        self.line_note_edit.setFixedHeight(60)

        self._form.addRow("Hesap", self.account_combo)
        self._form.addRow("Tarih", self.date_edit)
        self._form.addRow("Yön", self.direction_combo)
        self._form.addRow("Toplam Tutar", self.total_amount_edit)
        self._form.addRow("Açıklama", self.description_edit)
        self._form.addRow("Bakiyeyi Etkiler", self.affects_balance_switch)
        self._form.addRow("Nitelik", self.nature_combo)
        self._form.addRow("Kategori", self.category_combo)
        self._form.addRow("Varlık", self.asset_combo)
        self._form.addRow("Satır Notu", self.line_note_edit)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_button = PushButton("İptal", self)
        save_button = PrimaryPushButton("Kaydet", self)
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.accept)

        self.direction_combo.currentIndexChanged.connect(self._on_direction_changed)
        self.nature_combo.currentIndexChanged.connect(self._reload_categories)
        self._on_direction_changed()

        if data:
            self._load_data(data)

    def _on_direction_changed(self) -> None:
        current_direction = self.direction_combo.currentData()
        self.nature_combo.blockSignals(True)
        self.nature_combo.clear()

        if current_direction == Direction.IN:
            self.nature_combo.addItem(
                NATURE_LABELS[Nature.INCOME],
                userData=Nature.INCOME,
            )
            self.nature_combo.setCurrentIndex(0)
        else:
            self.nature_combo.addItem(
                NATURE_LABELS[Nature.EXPENSE],
                userData=Nature.EXPENSE,
            )
            self.nature_combo.addItem(
                NATURE_LABELS[Nature.COST],
                userData=Nature.COST,
            )
            self.nature_combo.setCurrentIndex(0)

        self.nature_combo.blockSignals(False)
        self._reload_categories()

    def _reload_categories(self) -> None:
        selected_nature = self.nature_combo.currentData()
        previous_category = self.category_combo.currentData()
        self.category_combo.clear()
        for category in self._categories:
            if category["nature"] != selected_nature:
                continue
            self.category_combo.addItem(category["name"], userData=category["id"])
        if previous_category is not None:
            index = self.category_combo.findData(previous_category)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)

    def _load_data(self, data: Dict[str, Any]) -> None:
        for index in range(self.account_combo.count()):
            account = self.account_combo.itemData(index)
            if account and account["id"] == data["account_id"]:
                self.account_combo.setCurrentIndex(index)
                break

        date_parts = str(data["txn_date"]).split("-")
        if len(date_parts) == 3:
            self.date_edit.setDate(
                QDate(int(date_parts[0]), int(date_parts[1]), int(date_parts[2]))
            )

        direction_index = self.direction_combo.findData(data["direction"])
        if direction_index >= 0:
            self.direction_combo.setCurrentIndex(direction_index)

        scale = int(data["currency_scale"])
        self.total_amount_edit.setText(
            format_amount(int(data["total_amount"]), scale)
        )
        self.description_edit.setText(str(data.get("description") or ""))
        self.affects_balance_switch.setChecked(bool(data["affects_balance"]))

        lines = data.get("lines") or []
        if lines:
            line = lines[0]
            nature_index = self.nature_combo.findData(line["nature"])
            if nature_index >= 0:
                self.nature_combo.setCurrentIndex(nature_index)
            self._reload_categories()
            category_index = self.category_combo.findData(line.get("category_id"))
            if category_index >= 0:
                self.category_combo.setCurrentIndex(category_index)
            asset_index = self.asset_combo.findData(line.get("asset_id"))
            if asset_index >= 0:
                self.asset_combo.setCurrentIndex(asset_index)
            self.line_note_edit.setPlainText(str(line.get("note") or ""))

    def _selected_account(self) -> Dict[str, Any]:
        return self.account_combo.currentData()

    def get_values(self) -> Dict[str, Any]:
        account = self._selected_account()
        txn_date = self.date_edit.date().toString("yyyy-MM-dd")
        total_amount_text = self.total_amount_edit.text()
        line = {
            "nature": self.nature_combo.currentData(),
            "category_id": self.category_combo.currentData(),
            "asset_id": self.asset_combo.currentData(),
            "amount_text": total_amount_text,
            "note": self.line_note_edit.toPlainText(),
        }
        return {
            "account_id": account["id"],
            "txn_date": txn_date,
            "direction": self.direction_combo.currentData(),
            "total_amount_text": total_amount_text,
            "description": self.description_edit.text(),
            "affects_balance": self.affects_balance_switch.isChecked(),
            "lines": [line],
        }
