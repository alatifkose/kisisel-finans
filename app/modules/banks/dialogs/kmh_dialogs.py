"""KMH dialogları."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt5.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QVBoxLayout, QWidget
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

from app.core.money import format_amount


class _BaseKmhDialog(QDialog):
    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(500)

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


class KmhAccountDialog(_BaseKmhDialog):
    def __init__(
        self,
        banks: List[Dict[str, Any]],
        accounts: List[Dict[str, Any]],
        parent: Optional[QWidget] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            "KMH / Ek Hesap" if data is None else "KMH / Ek Hesabı Düzenle",
            parent,
        )
        self._all_accounts = accounts
        self._data = data
        self._is_edit = data is not None

        self.bank_combo = ComboBox(self)
        for bank in banks:
            self.bank_combo.addItem(bank["name"], userData=bank["id"])

        self.account_combo = ComboBox(self)
        self.currency_label = BodyLabel("—", self)
        self.name_edit = LineEdit(self)
        self.limit_edit = LineEdit(self)
        self.used_edit = LineEdit(self)
        self.used_edit.setPlaceholderText("0")
        self.interest_edit = LineEdit(self)
        self.interest_edit.setPlaceholderText("Opsiyonel")
        self.liquidity_switch = SwitchButton(self)
        self.liquidity_switch.setChecked(True)
        self.active_switch = SwitchButton(self)
        self.active_switch.setChecked(True)
        self.note_edit = TextEdit(self)
        self.note_edit.setFixedHeight(70)

        self._form.addRow("Banka", self.bank_combo)
        self._form.addRow("Bağlı Hesap", self.account_combo)
        self._form.addRow("Para Birimi", self.currency_label)
        self._form.addRow("KMH Adı", self.name_edit)
        self._form.addRow("Limit", self.limit_edit)
        self._form.addRow("Kullanılan Tutar", self.used_edit)
        self._form.addRow("Faiz Oranı", self.interest_edit)
        self._form.addRow("Likidite Sayılır", self.liquidity_switch)
        if self._is_edit:
            self._form.addRow("Aktif", self.active_switch)
        self._form.addRow("Not", self.note_edit)

        self.bank_combo.currentIndexChanged.connect(self._refresh_accounts)
        self.account_combo.currentIndexChanged.connect(self._update_currency_label)

        if data:
            self._load_data(data)
        else:
            self._refresh_accounts()

    def _refresh_accounts(self) -> None:
        bank_id = self.bank_combo.currentData()
        selected_account_id = self.account_combo.currentData()
        self.account_combo.blockSignals(True)
        self.account_combo.clear()
        for account in self._all_accounts:
            if bank_id is not None and int(account["bank_id"]) != int(bank_id):
                continue
            label = account["name"]
            self.account_combo.addItem(label, userData=account["id"])
        if selected_account_id is not None:
            index = self.account_combo.findData(selected_account_id)
            if index >= 0:
                self.account_combo.setCurrentIndex(index)
        self.account_combo.blockSignals(False)
        self._update_currency_label()

    def _update_currency_label(self) -> None:
        account_id = self.account_combo.currentData()
        if account_id is None:
            self.currency_label.setText("—")
            return
        for account in self._all_accounts:
            if account["id"] == account_id:
                self.currency_label.setText(
                    f"{account.get('currency_code', '')} (scale={account.get('currency_scale', 2)})"
                )
                return

    def _account_scale(self) -> int:
        account_id = self.account_combo.currentData()
        if account_id is None:
            return 2
        for account in self._all_accounts:
            if account["id"] == account_id:
                return int(account.get("currency_scale") or 2)
        return 2

    def _load_data(self, data: Dict[str, Any]) -> None:
        for index in range(self.bank_combo.count()):
            if self.bank_combo.itemData(index) == data["bank_id"]:
                self.bank_combo.setCurrentIndex(index)
                break
        self._refresh_accounts()
        for index in range(self.account_combo.count()):
            if self.account_combo.itemData(index) == data["account_id"]:
                self.account_combo.setCurrentIndex(index)
                break
        self.name_edit.setText(str(data["name"]))
        scale = int(data["scale"])
        self.limit_edit.setText(format_amount(int(data["kmh_limit"]), scale))
        self.used_edit.setText(format_amount(int(data["used_amount"]), scale))
        if data.get("interest_rate") is not None:
            self.interest_edit.setText(str(data["interest_rate"]).replace(".", ","))
        self.liquidity_switch.setChecked(bool(data.get("counts_as_liquidity", True)))
        self.active_switch.setChecked(bool(data.get("is_active", True)))
        self.note_edit.setPlainText(str(data.get("note") or ""))

    def get_values(self) -> Dict[str, Any]:
        return {
            "bank_id": self.bank_combo.currentData(),
            "account_id": self.account_combo.currentData(),
            "name": self.name_edit.text(),
            "kmh_limit_text": self.limit_edit.text(),
            "used_amount_text": self.used_edit.text(),
            "interest_rate": self.interest_edit.text(),
            "counts_as_liquidity": self.liquidity_switch.isChecked(),
            "is_active": self.active_switch.isChecked(),
            "note": self.note_edit.toPlainText(),
        }


class KmhUsageDialog(QDialog):
    def __init__(
        self,
        kmh: Dict[str, Any],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._kmh = kmh
        self.setWindowTitle("KMH Kullanım Güncelle")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(SubtitleLabel("Kullanım Güncelle", self))

        info = QFormLayout()
        info.addRow("KMH", BodyLabel(kmh["name"], self))
        info.addRow("Limit", BodyLabel(kmh["kmh_limit_display"]["display"], self))
        info.addRow(
            "Kullanılabilir",
            BodyLabel(kmh["available_amount_display"]["display"], self),
        )
        layout.addLayout(info)

        form = QFormLayout()
        self.used_edit = LineEdit(self)
        self.used_edit.setText(kmh["used_amount_display"]["display"])
        form.addRow("Kullanılan Tutar", self.used_edit)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_button = PushButton("İptal", self)
        save_button = PrimaryPushButton("Kaydet", self)
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.accept)

    def get_used_amount_text(self) -> str:
        return self.used_edit.text()
