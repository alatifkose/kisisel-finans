"""Banka ve hesap ekleme/düzenleme dialogları."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt5.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    ComboBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
    SwitchButton,
    TextEdit,
)

from app.core.constants import TrackingMode


class _BaseFormDialog(QDialog):
    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(SubtitleLabel(title, self))

        self._form = QFormLayout()
        self._form.setSpacing(12)
        layout.addLayout(self._form)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_button = PushButton("İptal", self)
        save_button = PrimaryPushButton("Kaydet", self)
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.accept)


class BankDialog(_BaseFormDialog):
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__("Banka" if data is None else "Bankayı Düzenle", parent)

        self.name_edit = LineEdit(self)
        self.short_name_edit = LineEdit(self)
        self.active_switch = SwitchButton(self)
        self.active_switch.setChecked(True)
        self.note_edit = TextEdit(self)
        self.note_edit.setFixedHeight(80)

        self._form.addRow("Banka Adı", self.name_edit)
        self._form.addRow("Kısa Ad", self.short_name_edit)
        self._form.addRow("Aktif", self.active_switch)
        self._form.addRow("Not", self.note_edit)

        if data:
            self.name_edit.setText(str(data["name"]))
            self.short_name_edit.setText(str(data.get("short_name") or ""))
            self.active_switch.setChecked(bool(data["is_active"]))
            self.note_edit.setPlainText(str(data.get("note") or ""))

    def get_values(self) -> Dict[str, Any]:
        return {
            "name": self.name_edit.text(),
            "short_name": self.short_name_edit.text(),
            "is_active": self.active_switch.isChecked(),
            "note": self.note_edit.toPlainText(),
        }


class AccountDialog(_BaseFormDialog):
    def __init__(
        self,
        banks: List[Dict[str, Any]],
        currencies: List[Dict[str, Any]],
        parent: Optional[QWidget] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__("Hesap" if data is None else "Hesabı Düzenle", parent)
        self._data = data
        self._is_edit = data is not None

        self.bank_combo = ComboBox(self)
        for bank in banks:
            self.bank_combo.addItem(bank["name"], userData=bank["id"])

        self.name_edit = LineEdit(self)
        self.currency_combo = ComboBox(self)
        for currency in currencies:
            label = f"{currency['code']} ({currency.get('symbol') or ''})"
            self.currency_combo.addItem(label, userData=currency["id"])

        self.opening_balance_edit = LineEdit(self)
        self.opening_balance_edit.setPlaceholderText("0,00")

        self.current_balance_edit = LineEdit(self)
        self.current_balance_edit.setPlaceholderText("0,00")

        self.tracking_combo = ComboBox(self)
        self.tracking_combo.addItem("Defter (ledger)", userData=TrackingMode.LEDGER)
        self.tracking_combo.addItem("Anlık (snapshot)", userData=TrackingMode.SNAPSHOT)

        self.active_switch = SwitchButton(self)
        self.active_switch.setChecked(True)
        self.note_edit = TextEdit(self)
        self.note_edit.setFixedHeight(80)

        self._form.addRow("Banka", self.bank_combo)
        self._form.addRow("Hesap Adı", self.name_edit)
        self._form.addRow("Para Birimi", self.currency_combo)
        self._form.addRow("Açılış Bakiyesi", self.opening_balance_edit)

        if self._is_edit:
            self._form.addRow("Güncel Bakiye", self.current_balance_edit)
        else:
            self.current_balance_edit.hide()

        self._form.addRow("Takip Modu", self.tracking_combo)
        self._form.addRow("Aktif", self.active_switch)
        self._form.addRow("Not", self.note_edit)

        if data:
            bank_index = self.bank_combo.findData(data["bank_id"])
            if bank_index >= 0:
                self.bank_combo.setCurrentIndex(bank_index)
            self.name_edit.setText(str(data["name"]))
            currency_index = self.currency_combo.findData(data["currency_id"])
            if currency_index >= 0:
                self.currency_combo.setCurrentIndex(currency_index)
            self.opening_balance_edit.setText(
                self._format_balance(data["opening_balance"], data["currency_scale"])
            )
            if self._is_edit:
                self.current_balance_edit.setText(
                    self._format_balance(data["current_balance"], data["currency_scale"])
                )
            tracking_index = self.tracking_combo.findData(data["tracking_mode"])
            if tracking_index >= 0:
                self.tracking_combo.setCurrentIndex(tracking_index)
            self.active_switch.setChecked(bool(data["is_active"]))
            self.note_edit.setPlainText(str(data.get("note") or ""))

    @staticmethod
    def _format_balance(value: int, scale: int) -> str:
        from app.core.money import format_amount

        return format_amount(int(value), int(scale))

    def get_values(self) -> Dict[str, Any]:
        values = {
            "bank_id": self.bank_combo.currentData(),
            "name": self.name_edit.text(),
            "currency_id": self.currency_combo.currentData(),
            "opening_balance_text": self.opening_balance_edit.text(),
            "tracking_mode": self.tracking_combo.currentData(),
            "is_active": self.active_switch.isChecked(),
            "note": self.note_edit.toPlainText(),
        }
        if self._is_edit:
            values["current_balance_text"] = self.current_balance_edit.text()
        return values

    def is_edit_mode(self) -> bool:
        return self._is_edit
