"""Kredi kartı ve ekstre dialogları."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QDateEdit, QDialog, QFormLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    ComboBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SpinBox,
    SubtitleLabel,
    SwitchButton,
    TextEdit,
)

from app.core.money import format_amount


class _BaseFormDialog(QDialog):
    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(480)

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


class CreditCardDialog(_BaseFormDialog):
    def __init__(
        self,
        banks: List[Dict[str, Any]],
        currencies: List[Dict[str, Any]],
        parent: Optional[QWidget] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__("Kredi Kartı" if data is None else "Kredi Kartını Düzenle", parent)
        self._data = data
        self._is_edit = data is not None

        self.bank_combo = ComboBox(self)
        for bank in banks:
            self.bank_combo.addItem(bank["name"], userData=bank["id"])

        self.name_edit = LineEdit(self)
        self.currency_combo = ComboBox(self)
        for currency in currencies:
            label = f"{currency['code']} ({currency.get('symbol') or ''})"
            self.currency_combo.addItem(label, userData=currency)

        self.limit_edit = LineEdit(self)
        self.cash_advance_edit = LineEdit(self)
        self.cash_advance_edit.setPlaceholderText("0")
        self.statement_day_spin = SpinBox(self)
        self.statement_day_spin.setRange(0, 31)
        self.statement_day_spin.setSpecialValueText("—")
        self.due_day_spin = SpinBox(self)
        self.due_day_spin.setRange(0, 31)
        self.due_day_spin.setSpecialValueText("—")
        self.liquidity_switch = SwitchButton(self)
        self.liquidity_switch.setChecked(False)
        self.active_switch = SwitchButton(self)
        self.active_switch.setChecked(True)
        self.note_edit = TextEdit(self)
        self.note_edit.setFixedHeight(70)

        self._form.addRow("Banka", self.bank_combo)
        self._form.addRow("Kart Adı", self.name_edit)
        self._form.addRow("Para Birimi", self.currency_combo)
        self._form.addRow("Kart Limiti", self.limit_edit)
        self._form.addRow("Nakit Avans Limiti", self.cash_advance_edit)
        self._form.addRow("Ekstre Kesim Günü", self.statement_day_spin)
        self._form.addRow("Son Ödeme Günü", self.due_day_spin)
        self._form.addRow("Likidite Sayılır", self.liquidity_switch)
        if self._is_edit:
            self._form.addRow("Aktif", self.active_switch)
        self._form.addRow("Not", self.note_edit)

        if data:
            self._load_data(data)

        try_index = self.currency_combo.findData(
            next(c for c in currencies if c["code"] == "TRY")
        ) if any(c["code"] == "TRY" for c in currencies) else -1
        if try_index >= 0 and data is None:
            self.currency_combo.setCurrentIndex(try_index)

    def _load_data(self, data: Dict[str, Any]) -> None:
        for index in range(self.bank_combo.count()):
            if self.bank_combo.itemData(index) == data["bank_id"]:
                self.bank_combo.setCurrentIndex(index)
                break
        self.name_edit.setText(str(data["name"]))
        for index in range(self.currency_combo.count()):
            currency = self.currency_combo.itemData(index)
            if currency and currency["id"] == data["currency_id"]:
                self.currency_combo.setCurrentIndex(index)
                break
        scale = int(data["scale"])
        self.limit_edit.setText(format_amount(int(data["card_limit"]), scale))
        self.cash_advance_edit.setText(
            format_amount(int(data.get("cash_advance_limit") or 0), scale)
        )
        if data.get("statement_day"):
            self.statement_day_spin.setValue(int(data["statement_day"]))
        if data.get("due_day"):
            self.due_day_spin.setValue(int(data["due_day"]))
        self.liquidity_switch.setChecked(bool(data.get("counts_as_liquidity")))
        self.active_switch.setChecked(bool(data.get("is_active", True)))
        self.note_edit.setPlainText(str(data.get("note") or ""))

    def get_values(self) -> Dict[str, Any]:
        statement_day = self.statement_day_spin.value()
        due_day = self.due_day_spin.value()
        return {
            "bank_id": self.bank_combo.currentData(),
            "name": self.name_edit.text(),
            "currency_id": self.currency_combo.currentData()["id"],
            "card_limit_text": self.limit_edit.text(),
            "cash_advance_limit_text": self.cash_advance_edit.text(),
            "statement_day": statement_day if statement_day > 0 else None,
            "due_day": due_day if due_day > 0 else None,
            "counts_as_liquidity": self.liquidity_switch.isChecked(),
            "is_active": self.active_switch.isChecked(),
            "note": self.note_edit.toPlainText(),
        }


class CardStatementDialog(_BaseFormDialog):
    def __init__(
        self,
        card: Dict[str, Any],
        parent: Optional[QWidget] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        card_label = f"{card['bank_name']} - {card['name']} ({card['currency_code']})"
        super().__init__(
            "Ekstre Ekle" if data is None else "Ekstre Düzenle",
            parent,
        )
        self._card = card
        self._scale = int(card["scale"])

        self._form.addRow("Kart", SubtitleLabel(card_label, self))

        self.statement_date_edit = QDateEdit(self)
        self.statement_date_edit.setCalendarPopup(True)
        self.statement_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.statement_date_edit.setDate(QDate.currentDate())
        self.debt_edit = LineEdit(self)
        self.min_payment_edit = LineEdit(self)
        self.due_date_edit = QDateEdit(self)
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.due_date_edit.setDate(QDate.currentDate())
        self.available_limit_edit = LineEdit(self)
        self.available_limit_edit.setPlaceholderText("Opsiyonel")
        self.note_edit = TextEdit(self)
        self.note_edit.setFixedHeight(60)

        self._form.addRow("Ekstre Tarihi", self.statement_date_edit)
        self._form.addRow("Ekstre Borcu", self.debt_edit)
        self._form.addRow("Asgari Ödeme", self.min_payment_edit)
        self._form.addRow("Son Ödeme Tarihi", self.due_date_edit)
        self._form.addRow("Kullanılabilir Limit", self.available_limit_edit)
        self._form.addRow("Not", self.note_edit)

        if data:
            parts = str(data["statement_date"]).split("-")
            if len(parts) == 3:
                self.statement_date_edit.setDate(
                    QDate(int(parts[0]), int(parts[1]), int(parts[2]))
                )
            self.debt_edit.setText(
                format_amount(int(data["statement_debt"]), self._scale)
            )
            self.min_payment_edit.setText(
                format_amount(int(data["min_payment"]), self._scale)
            )
            if data.get("due_date"):
                due_parts = str(data["due_date"]).split("-")
                if len(due_parts) == 3:
                    self.due_date_edit.setDate(
                        QDate(int(due_parts[0]), int(due_parts[1]), int(due_parts[2]))
                    )
            if data.get("available_limit") is not None:
                self.available_limit_edit.setText(
                    format_amount(int(data["available_limit"]), self._scale)
                )
            self.note_edit.setPlainText(str(data.get("note") or ""))

    def get_values(self) -> Dict[str, Any]:
        return {
            "credit_card_id": self._card["id"],
            "statement_date": self.statement_date_edit.date().toString("yyyy-MM-dd"),
            "statement_debt_text": self.debt_edit.text(),
            "min_payment_text": self.min_payment_edit.text(),
            "due_date": self.due_date_edit.date().toString("yyyy-MM-dd"),
            "available_limit_text": self.available_limit_edit.text(),
            "note": self.note_edit.toPlainText(),
        }
