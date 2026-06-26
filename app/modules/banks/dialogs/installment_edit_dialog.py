"""Taksit düzenleme dialogu."""

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
from qfluentwidgets import ComboBox, LineEdit, PrimaryPushButton, PushButton, SpinBox, SubtitleLabel, TextEdit

from app.core.money import format_amount


class InstallmentEditDialog(QDialog):
    """Tek taksit ve bileşenlerini düzenler."""

    def __init__(
        self,
        component_types: List[Dict[str, Any]],
        scale: int,
        parent: Optional[QWidget] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(parent)
        self._component_types = component_types
        self._scale = scale
        self._components: List[Dict[str, Any]] = []
        self.setWindowTitle("Taksit" if data is None else "Taksiti Düzenle")
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(SubtitleLabel(self.windowTitle(), self))

        form = QFormLayout()
        self.seq_spin = SpinBox(self)
        self.seq_spin.setRange(1, 9999)
        self.due_date_edit = QDateEdit(self)
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.due_date_edit.setDate(QDate.currentDate())
        self.total_amount_edit = LineEdit(self)
        self.remaining_edit = LineEdit(self)
        self.note_edit = TextEdit(self)
        self.note_edit.setFixedHeight(50)

        form.addRow("Sıra No", self.seq_spin)
        form.addRow("Vade Tarihi", self.due_date_edit)
        form.addRow("Taksit Toplamı", self.total_amount_edit)
        form.addRow("Kalan Anapara", self.remaining_edit)
        form.addRow("Not", self.note_edit)
        layout.addLayout(form)

        layout.addWidget(SubtitleLabel("Bileşenler", self))
        comp_buttons = QHBoxLayout()
        self.add_comp_button = PushButton("Bileşen Ekle", self)
        self.remove_comp_button = PushButton("Bileşen Sil", self)
        comp_buttons.addWidget(self.add_comp_button)
        comp_buttons.addWidget(self.remove_comp_button)
        comp_buttons.addStretch()
        layout.addLayout(comp_buttons)

        self.comp_table = QTableWidget(self)
        self.comp_table.setColumnCount(2)
        self.comp_table.setHorizontalHeaderLabels(["Bileşen Tipi", "Tutar"])
        self.comp_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.comp_table.verticalHeader().setVisible(False)
        layout.addWidget(self.comp_table)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_button = PushButton("İptal", self)
        save_button = PrimaryPushButton("Kaydet", self)
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.accept)
        self.add_comp_button.clicked.connect(self._add_component_row)
        self.remove_comp_button.clicked.connect(self._remove_component_row)

        if data:
            self._load_data(data)

    def _add_component_row(
        self,
        component_type_id: Optional[int] = None,
        amount_text: str = "",
    ) -> None:
        row = self.comp_table.rowCount()
        self.comp_table.insertRow(row)
        combo = ComboBox(self.comp_table)
        for comp in self._component_types:
            combo.addItem(comp["name"], userData=comp["id"])
        if component_type_id is not None:
            index = combo.findData(component_type_id)
            if index >= 0:
                combo.setCurrentIndex(index)
        amount_edit = LineEdit(self.comp_table)
        amount_edit.setText(amount_text)
        self.comp_table.setCellWidget(row, 0, combo)
        self.comp_table.setCellWidget(row, 1, amount_edit)

    def _remove_component_row(self) -> None:
        selected = self.comp_table.selectionModel().selectedRows()
        if selected:
            self.comp_table.removeRow(selected[0].row())
            return
        # Hücrelerde widget (ComboBox/LineEdit) olduğu için satır seçimi her
        # zaman gerçekleşmeyebilir; seçim yoksa son satırı kaldır.
        row_count = self.comp_table.rowCount()
        if row_count > 0:
            self.comp_table.removeRow(row_count - 1)

    def _load_data(self, data: Dict[str, Any]) -> None:
        self.seq_spin.setValue(int(data["seq"]))
        parts = str(data["due_date"]).split("-")
        if len(parts) == 3:
            self.due_date_edit.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))
        self.total_amount_edit.setText(
            format_amount(int(data["total_amount"]), self._scale)
        )
        if data.get("remaining_principal_after") is not None:
            self.remaining_edit.setText(
                format_amount(int(data["remaining_principal_after"]), self._scale)
            )
        self.note_edit.setPlainText(str(data.get("note") or ""))
        for comp in data.get("components", []):
            amount = comp.get("amount")
            amount_text = (
                format_amount(int(amount), self._scale)
                if isinstance(amount, int)
                else str(comp.get("amount_text") or "")
            )
            self._add_component_row(comp.get("component_type_id"), amount_text)

    def get_installment_data(self) -> Dict[str, Any]:
        components: List[Dict[str, Any]] = []
        for row in range(self.comp_table.rowCount()):
            combo = self.comp_table.cellWidget(row, 0)
            amount_edit = self.comp_table.cellWidget(row, 1)
            if combo is None or amount_edit is None:
                continue
            components.append(
                {
                    "component_type_id": combo.currentData(),
                    "amount_text": amount_edit.text(),
                }
            )
        return {
            "seq": self.seq_spin.value(),
            "due_date": self.due_date_edit.date().toString("yyyy-MM-dd"),
            "total_amount_text": self.total_amount_edit.text(),
            "remaining_principal_after_text": self.remaining_edit.text(),
            "note": self.note_edit.toPlainText(),
            "components": components,
        }
