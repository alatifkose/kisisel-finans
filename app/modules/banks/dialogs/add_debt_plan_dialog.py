"""Borç planı ekleme/düzenleme dialogu."""

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
from qfluentwidgets import (
    ComboBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
    SwitchButton,
    TextEdit,
)

from app.core.constants import PLAN_KIND_LABELS, PlanKind, VALID_PLAN_KINDS
from app.core.money import format_amount
from app.modules.banks.dialogs.installment_edit_dialog import InstallmentEditDialog
from app.services.credit_card_service import CreditCardService
from app.services.kmh_service import KmhService


class AddDebtPlanDialog(QDialog):
    """Manuel borç/ödeme planı giriş dialogu."""

    def __init__(
        self,
        banks: List[Dict[str, Any]],
        currencies: List[Dict[str, Any]],
        component_types: List[Dict[str, Any]],
        parent: Optional[QWidget] = None,
        data: Optional[Dict[str, Any]] = None,
        default_plan_kind: str = PlanKind.LOAN,
        lock_plan_kind: bool = False,
    ) -> None:
        super().__init__(parent)
        self._banks = banks
        self._currencies = currencies
        self._component_types = component_types
        self._installments: List[Dict[str, Any]] = []
        self._data = data
        self._is_edit = data is not None
        self._lock_plan_kind = lock_plan_kind
        self._credit_card_service = CreditCardService()
        self._kmh_service = KmhService()

        title = "Borç Planı" if data is None else "Borç Planını Düzenle"
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(760, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(SubtitleLabel(title, self))

        form = QFormLayout()
        self.bank_combo = ComboBox(self)
        for bank in banks:
            self.bank_combo.addItem(bank["name"], userData=bank["id"])

        self.kind_combo = ComboBox(self)
        for kind in VALID_PLAN_KINDS:
            self.kind_combo.addItem(PLAN_KIND_LABELS[kind], userData=kind)
        if lock_plan_kind:
            self.kind_combo.setEnabled(False)

        self.name_edit = LineEdit(self)
        self.currency_combo = ComboBox(self)
        for currency in currencies:
            label = f"{currency['code']} ({currency.get('symbol') or ''})"
            self.currency_combo.addItem(label, userData=currency)

        self.principal_edit = LineEdit(self)
        self.interest_edit = LineEdit(self)
        self.interest_edit.setPlaceholderText("Opsiyonel")
        self.start_date_edit = QDateEdit(self)
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.start_date_edit.setDate(QDate.currentDate())
        self.note_edit = TextEdit(self)
        self.note_edit.setFixedHeight(60)
        self.active_switch = SwitchButton(self)
        self.active_switch.setChecked(True)
        self.source_card_combo = ComboBox(self)
        self.source_card_combo.addItem("— Seçilmedi —", userData=None)
        self.source_kmh_combo = ComboBox(self)
        self.source_kmh_combo.addItem("— Seçilmedi —", userData=None)

        form.addRow("Banka", self.bank_combo)
        form.addRow("Plan Türü", self.kind_combo)
        form.addRow("Plan Adı", self.name_edit)
        form.addRow("Para Birimi", self.currency_combo)
        form.addRow("Kaynak Kredi Kartı", self.source_card_combo)
        form.addRow("Kaynak KMH / Ek Hesap", self.source_kmh_combo)
        form.addRow("Ana Para", self.principal_edit)
        form.addRow("Faiz Oranı", self.interest_edit)
        form.addRow("Başlangıç Tarihi", self.start_date_edit)
        form.addRow("Not", self.note_edit)
        if self._is_edit:
            form.addRow("Aktif", self.active_switch)
        layout.addLayout(form)

        layout.addWidget(SubtitleLabel("Taksitler", self))
        inst_buttons = QHBoxLayout()
        self.add_inst_button = PrimaryPushButton("Taksit Ekle", self)
        self.edit_inst_button = PushButton("Taksit Düzenle", self)
        self.remove_inst_button = PushButton("Taksit Sil", self)
        inst_buttons.addWidget(self.add_inst_button)
        inst_buttons.addWidget(self.edit_inst_button)
        inst_buttons.addWidget(self.remove_inst_button)
        inst_buttons.addStretch()
        layout.addLayout(inst_buttons)

        self.inst_table = QTableWidget(self)
        self.inst_table.setColumnCount(5)
        self.inst_table.setHorizontalHeaderLabels(
            ["Sıra", "Vade", "Toplam", "Kalan Anapara", "Not"]
        )
        self.inst_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.inst_table.setSelectionMode(QTableWidget.SingleSelection)
        self.inst_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.inst_table.verticalHeader().setVisible(False)
        layout.addWidget(self.inst_table)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_button = PushButton("İptal", self)
        save_button = PrimaryPushButton("Kaydet", self)
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.accept)
        self.add_inst_button.clicked.connect(self._add_installment)
        self.edit_inst_button.clicked.connect(self._edit_installment)
        self.remove_inst_button.clicked.connect(self._remove_installment)
        self.currency_combo.currentIndexChanged.connect(self._refresh_installment_table)
        self.bank_combo.currentIndexChanged.connect(self._refresh_source_options)
        self.currency_combo.currentIndexChanged.connect(self._refresh_source_options)
        self.kind_combo.currentIndexChanged.connect(self._on_kind_changed)

        default_index = self.kind_combo.findData(default_plan_kind)
        if default_index >= 0:
            self.kind_combo.setCurrentIndex(default_index)

        self._sync_source_visibility()
        self._refresh_source_options()

        if data:
            self._load_data(data)

    def _on_kind_changed(self) -> None:
        self._sync_source_visibility()
        self._refresh_source_options()

    def _sync_source_visibility(self) -> None:
        is_ca = self.kind_combo.currentData() == PlanKind.CASH_ADVANCE_INSTALLMENT
        is_kmh = self.kind_combo.currentData() == PlanKind.KMH_INSTALLMENT
        self.source_card_combo.setVisible(is_ca)
        self.source_card_combo.setEnabled(is_ca)
        self.source_kmh_combo.setVisible(is_kmh)
        self.source_kmh_combo.setEnabled(is_kmh)
        if not is_ca:
            self.source_card_combo.setCurrentIndex(0)
        if not is_kmh:
            self.source_kmh_combo.setCurrentIndex(0)

    def _refresh_source_options(self) -> None:
        bank_id = self.bank_combo.currentData()
        currency = self.currency_combo.currentData()
        plan_kind = self.kind_combo.currentData()

        if plan_kind == PlanKind.CASH_ADVANCE_INSTALLMENT:
            selected_card = self.source_card_combo.currentData()
            self.source_card_combo.blockSignals(True)
            self.source_card_combo.clear()
            self.source_card_combo.addItem("— Seçilmedi —", userData=None)
            if bank_id is not None and currency is not None:
                for card in self._credit_card_service.list_credit_cards_for_plan(
                    int(bank_id),
                    int(currency["id"]),
                ):
                    self.source_card_combo.addItem(card["name"], userData=card["id"])
            if selected_card is not None:
                index = self.source_card_combo.findData(selected_card)
                if index >= 0:
                    self.source_card_combo.setCurrentIndex(index)
            self.source_card_combo.blockSignals(False)

        if plan_kind == PlanKind.KMH_INSTALLMENT:
            selected_kmh = self.source_kmh_combo.currentData()
            self.source_kmh_combo.blockSignals(True)
            self.source_kmh_combo.clear()
            self.source_kmh_combo.addItem("— Seçilmedi —", userData=None)
            if bank_id is not None and currency is not None:
                for kmh in self._kmh_service.list_kmh_for_plan(
                    int(bank_id),
                    int(currency["id"]),
                ):
                    self.source_kmh_combo.addItem(kmh["name"], userData=kmh["id"])
            if selected_kmh is not None:
                index = self.source_kmh_combo.findData(selected_kmh)
                if index >= 0:
                    self.source_kmh_combo.setCurrentIndex(index)
            self.source_kmh_combo.blockSignals(False)

    def _current_scale(self) -> int:
        currency = self.currency_combo.currentData()
        return int(currency["scale"]) if currency else 2

    def _refresh_installment_table(self) -> None:
        scale = self._current_scale()
        self.inst_table.setRowCount(len(self._installments))
        for row_index, inst in enumerate(sorted(self._installments, key=lambda x: x["seq"])):
            remaining = inst.get("remaining_principal_after")
            remaining_text = ""
            if remaining is not None:
                remaining_text = format_amount(int(remaining), scale)
            elif inst.get("remaining_principal_after_text"):
                remaining_text = str(inst["remaining_principal_after_text"])
            total_text = inst.get("total_amount_text")
            if not total_text and inst.get("total_amount") is not None:
                total_text = format_amount(int(inst["total_amount"]), scale)
            values = [
                inst["seq"],
                inst["due_date"],
                total_text or "",
                remaining_text,
                inst.get("note") or "",
            ]
            for col_index, value in enumerate(values):
                self.inst_table.setItem(row_index, col_index, QTableWidgetItem(str(value)))

    def _add_installment(self) -> None:
        dialog = InstallmentEditDialog(
            self._component_types,
            self._current_scale(),
            self.window(),
        )
        if not dialog.exec_():
            return
        self._installments.append(dialog.get_installment_data())
        self._refresh_installment_table()

    def _edit_installment(self) -> None:
        selected = self.inst_table.selectionModel().selectedRows()
        if not selected:
            return
        row_index = selected[0].row()
        sorted_installments = sorted(self._installments, key=lambda x: x["seq"])
        if row_index >= len(sorted_installments):
            return
        current = sorted_installments[row_index]
        dialog = InstallmentEditDialog(
            self._component_types,
            self._current_scale(),
            self.window(),
            data=current,
        )
        if not dialog.exec_():
            return
        updated = dialog.get_installment_data()
        for index, inst in enumerate(self._installments):
            if inst["seq"] == current["seq"]:
                self._installments[index] = updated
                break
        self._refresh_installment_table()

    def _remove_installment(self) -> None:
        selected = self.inst_table.selectionModel().selectedRows()
        if not selected:
            return
        row_index = selected[0].row()
        sorted_installments = sorted(self._installments, key=lambda x: x["seq"])
        if row_index >= len(sorted_installments):
            return
        target_seq = sorted_installments[row_index]["seq"]
        self._installments = [i for i in self._installments if i["seq"] != target_seq]
        self._refresh_installment_table()

    def _load_data(self, data: Dict[str, Any]) -> None:
        for index in range(self.bank_combo.count()):
            if self.bank_combo.itemData(index) == data["bank_id"]:
                self.bank_combo.setCurrentIndex(index)
                break
        kind_index = self.kind_combo.findData(data["plan_kind"])
        if kind_index >= 0:
            self.kind_combo.setCurrentIndex(kind_index)
        self.name_edit.setText(str(data["name"]))
        for index in range(self.currency_combo.count()):
            currency = self.currency_combo.itemData(index)
            if currency and currency["id"] == data["currency_id"]:
                self.currency_combo.setCurrentIndex(index)
                break
        scale = int(data["scale"])
        self.principal_edit.setText(format_amount(int(data["principal_amount"]), scale))
        if data.get("interest_rate") is not None:
            self.interest_edit.setText(str(data["interest_rate"]).replace(".", ","))
        if data.get("start_date"):
            parts = str(data["start_date"]).split("-")
            if len(parts) == 3:
                self.start_date_edit.setDate(
                    QDate(int(parts[0]), int(parts[1]), int(parts[2]))
                )
        self.note_edit.setPlainText(str(data.get("note") or ""))
        self.active_switch.setChecked(bool(data.get("is_active", True)))
        self._sync_source_visibility()
        self._refresh_source_options()
        source_card_id = data.get("source_card_id")
        if source_card_id is not None:
            index = self.source_card_combo.findData(source_card_id)
            if index >= 0:
                self.source_card_combo.setCurrentIndex(index)
        source_kmh_id = data.get("source_kmh_id")
        if source_kmh_id is not None:
            index = self.source_kmh_combo.findData(source_kmh_id)
            if index >= 0:
                self.source_kmh_combo.setCurrentIndex(index)
        self._installments = []
        for inst in data.get("installments", []):
            inst_data = {
                "seq": inst["seq"],
                "due_date": inst["due_date"],
                "total_amount": inst["total_amount"],
                "total_amount_text": format_amount(int(inst["total_amount"]), scale),
                "remaining_principal_after": inst.get("remaining_principal_after"),
                "remaining_principal_after_text": (
                    format_amount(int(inst["remaining_principal_after"]), scale)
                    if inst.get("remaining_principal_after") is not None
                    else ""
                ),
                "note": inst.get("note") or "",
                "components": [
                    {
                        "component_type_id": comp["component_type_id"],
                        "amount": comp["amount"],
                        "amount_text": format_amount(int(comp["amount"]), scale),
                    }
                    for comp in inst.get("components", [])
                ],
            }
            self._installments.append(inst_data)
        self._refresh_installment_table()

    def get_plan_data(self) -> Dict[str, Any]:
        plan_kind = self.kind_combo.currentData()
        source_card_id = None
        source_kmh_id = None
        if plan_kind == PlanKind.CASH_ADVANCE_INSTALLMENT:
            source_card_id = self.source_card_combo.currentData()
        if plan_kind == PlanKind.KMH_INSTALLMENT:
            source_kmh_id = self.source_kmh_combo.currentData()
        return {
            "bank_id": self.bank_combo.currentData(),
            "plan_kind": plan_kind,
            "name": self.name_edit.text(),
            "currency_id": self.currency_combo.currentData()["id"],
            "source_card_id": source_card_id,
            "source_kmh_id": source_kmh_id,
            "principal_amount_text": self.principal_edit.text(),
            "interest_rate": self.interest_edit.text(),
            "start_date": self.start_date_edit.date().toString("yyyy-MM-dd"),
            "note": self.note_edit.toPlainText(),
            "installment_count": len(self._installments),
            "installments": self._installments,
            "is_active": self.active_switch.isChecked(),
        }
