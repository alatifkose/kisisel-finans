"""Transfer ekleme dialogu."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QDateEdit, QDialog, QFormLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, ComboBox, LineEdit, PrimaryPushButton, PushButton, SubtitleLabel, TextEdit

from app.core.money import format_amount, parse_amount


class AddTransferDialog(QDialog):
    """Hesaplar arası transfer oluşturma dialogu."""

    def __init__(
        self,
        accounts: List[Dict[str, Any]],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._accounts = accounts
        self._syncing_amounts = False

        self.setWindowTitle("Transfer Ekle")
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(SubtitleLabel("Transfer Ekle", self))

        form = QFormLayout()
        form.setSpacing(12)

        self.from_account_combo = ComboBox(self)
        self.to_account_combo = ComboBox(self)
        for account in accounts:
            label = f"{account['bank_name']} — {account['name']}"
            self.from_account_combo.addItem(label, userData=account["id"])
            self.to_account_combo.addItem(label, userData=account["id"])

        self.from_currency_label = BodyLabel("—", self)
        self.to_currency_label = BodyLabel("—", self)
        self.from_amount_edit = LineEdit(self)
        self.to_amount_edit = LineEdit(self)
        self.exchange_rate_edit = LineEdit(self)
        self.exchange_rate_edit.setPlaceholderText("Opsiyonel")
        self.transfer_date_edit = QDateEdit(self)
        self.transfer_date_edit.setCalendarPopup(True)
        self.transfer_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.transfer_date_edit.setDate(QDate.currentDate())
        self.description_edit = TextEdit(self)
        self.description_edit.setFixedHeight(70)

        form.addRow("Kaynak Hesap", self.from_account_combo)
        form.addRow("Kaynak Para Birimi", self.from_currency_label)
        form.addRow("Hedef Hesap", self.to_account_combo)
        form.addRow("Hedef Para Birimi", self.to_currency_label)
        form.addRow("Kaynak Tutar", self.from_amount_edit)
        form.addRow("Hedef Tutar", self.to_amount_edit)
        form.addRow("Kur / Oran", self.exchange_rate_edit)
        form.addRow("Transfer Tarihi", self.transfer_date_edit)
        form.addRow("Açıklama", self.description_edit)
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

        self.from_account_combo.currentIndexChanged.connect(self._on_from_account_changed)
        self.to_account_combo.currentIndexChanged.connect(self._on_to_account_changed)
        self.from_amount_edit.textChanged.connect(self._sync_same_currency_to_amount)

        self._on_from_account_changed()
        self._on_to_account_changed()

    def _account_by_id(self, account_id: Optional[int]) -> Optional[Dict[str, Any]]:
        if account_id is None:
            return None
        for account in self._accounts:
            if account["id"] == account_id:
                return account
        return None

    def _on_from_account_changed(self) -> None:
        account = self._account_by_id(self.from_account_combo.currentData())
        if account is None:
            self.from_currency_label.setText("—")
        else:
            self.from_currency_label.setText(
                f"{account.get('currency_code', '')} {account.get('currency_symbol') or ''}".strip()
            )
        self._sync_same_currency_to_amount()

    def _on_to_account_changed(self) -> None:
        account = self._account_by_id(self.to_account_combo.currentData())
        if account is None:
            self.to_currency_label.setText("—")
        else:
            self.to_currency_label.setText(
                f"{account.get('currency_code', '')} {account.get('currency_symbol') or ''}".strip()
            )
        self._sync_same_currency_to_amount()

    def _same_currency(self) -> bool:
        from_account = self._account_by_id(self.from_account_combo.currentData())
        to_account = self._account_by_id(self.to_account_combo.currentData())
        if from_account is None or to_account is None:
            return False
        return int(from_account["currency_id"]) == int(to_account["currency_id"])

    def _sync_same_currency_to_amount(self) -> None:
        if not self._same_currency():
            return
        from_account = self._account_by_id(self.from_account_combo.currentData())
        if from_account is None:
            return
        from_text = self.from_amount_edit.text().strip()
        if not from_text:
            return
        scale = int(from_account["currency_scale"])
        try:
            raw = parse_amount(from_text, scale)
        except ValueError:
            return
        self._syncing_amounts = True
        self.to_amount_edit.setText(format_amount(raw, scale))
        self._syncing_amounts = False

    def get_values(self) -> Dict[str, Any]:
        return {
            "from_account_id": self.from_account_combo.currentData(),
            "to_account_id": self.to_account_combo.currentData(),
            "from_amount_text": self.from_amount_edit.text(),
            "to_amount_text": self.to_amount_edit.text(),
            "exchange_rate": self.exchange_rate_edit.text(),
            "transfer_date": self.transfer_date_edit.date().toString("yyyy-MM-dd"),
            "description": self.description_edit.toPlainText(),
        }
