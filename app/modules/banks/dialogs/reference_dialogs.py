"""Referans verisi ekleme/düzenleme dialogları."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    ComboBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SpinBox,
    SubtitleLabel,
    SwitchButton,
)

from app.core.constants import NATURE_LABELS, VALID_CATEGORY_NATURES, VALID_COMPONENT_NATURES


class _BaseReferenceDialog(QDialog):
    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(16)
        self._layout.addWidget(SubtitleLabel(title, self))

        self._form = QFormLayout()
        self._form.setSpacing(12)
        self._layout.addLayout(self._form)

        button_row = QHBoxLayout()
        button_row.addStretch()
        self._cancel_button = PushButton("İptal", self)
        self._save_button = PrimaryPushButton("Kaydet", self)
        button_row.addWidget(self._cancel_button)
        button_row.addWidget(self._save_button)
        self._layout.addLayout(button_row)

        self._cancel_button.clicked.connect(self.reject)
        self._save_button.clicked.connect(self.accept)


class CurrencyDialog(_BaseReferenceDialog):
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__("Para Birimi" if data is None else "Para Birimini Düzenle", parent)
        self._data = data

        self.code_edit = LineEdit(self)
        self.symbol_edit = LineEdit(self)
        self.scale_spin = SpinBox(self)
        self.scale_spin.setRange(0, 6)
        self.active_switch = SwitchButton(self)
        self.active_switch.setChecked(True)

        self._form.addRow("Kod", self.code_edit)
        self._form.addRow("Sembol", self.symbol_edit)
        self._form.addRow("Scale", self.scale_spin)
        self._form.addRow("Aktif", self.active_switch)

        if data:
            self.code_edit.setText(str(data["code"]))
            self.symbol_edit.setText(str(data.get("symbol") or ""))
            self.scale_spin.setValue(int(data["scale"]))
            self.active_switch.setChecked(bool(data["is_active"]))

    def get_values(self) -> Dict[str, Any]:
        return {
            "code": self.code_edit.text(),
            "symbol": self.symbol_edit.text(),
            "scale": self.scale_spin.value(),
            "is_active": self.active_switch.isChecked(),
        }


class CategoryDialog(_BaseReferenceDialog):
    def __init__(
        self,
        categories: List[Dict[str, Any]],
        parent: Optional[QWidget] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__("Kategori" if data is None else "Kategoriyi Düzenle", parent)
        self._data = data

        self.name_edit = LineEdit(self)
        self.nature_combo = ComboBox(self)
        for nature in VALID_CATEGORY_NATURES:
            self.nature_combo.addItem(NATURE_LABELS[nature], userData=nature)

        self.parent_combo = ComboBox(self)
        self.parent_combo.addItem("—", userData=None)
        current_id = data["id"] if data else None
        for category in categories:
            if current_id is not None and category["id"] == current_id:
                continue
            self.parent_combo.addItem(category["name"], userData=category["id"])

        self.active_switch = SwitchButton(self)
        self.active_switch.setChecked(True)

        self._form.addRow("Ad", self.name_edit)
        self._form.addRow("Nitelik", self.nature_combo)
        self._form.addRow("Üst Kategori", self.parent_combo)
        self._form.addRow("Aktif", self.active_switch)

        if data:
            self.name_edit.setText(str(data["name"]))
            index = self.nature_combo.findData(data["nature"])
            if index >= 0:
                self.nature_combo.setCurrentIndex(index)
            parent_index = self.parent_combo.findData(data.get("parent_id"))
            if parent_index >= 0:
                self.parent_combo.setCurrentIndex(parent_index)
            self.active_switch.setChecked(bool(data["is_active"]))

    def get_values(self) -> Dict[str, Any]:
        return {
            "name": self.name_edit.text(),
            "nature": self.nature_combo.currentData(),
            "parent_id": self.parent_combo.currentData(),
            "is_active": self.active_switch.isChecked(),
        }


class AssetDialog(_BaseReferenceDialog):
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__("Varlık" if data is None else "Varlığı Düzenle", parent)
        self._data = data

        self.name_edit = LineEdit(self)
        self.type_edit = LineEdit(self)
        self.type_edit.setPlaceholderText("other")
        self.active_switch = SwitchButton(self)
        self.active_switch.setChecked(True)

        self._form.addRow("Ad", self.name_edit)
        self._form.addRow("Tip", self.type_edit)
        self._form.addRow("Aktif", self.active_switch)

        if data:
            self.name_edit.setText(str(data["name"]))
            self.type_edit.setText(str(data.get("type") or ""))
            self.active_switch.setChecked(bool(data["is_active"]))

    def get_values(self) -> Dict[str, Any]:
        return {
            "name": self.name_edit.text(),
            "type": self.type_edit.text(),
            "is_active": self.active_switch.isChecked(),
        }


class ComponentTypeDialog(_BaseReferenceDialog):
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        data: Optional[Dict[str, Any]] = None,
        expense_categories: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(
            "Bileşen Tipi" if data is None else "Bileşen Tipini Düzenle",
            parent,
        )
        self._data = data
        self._expense_categories = expense_categories or []

        self.code_edit = LineEdit(self)
        self.name_edit = LineEdit(self)
        self.nature_combo = ComboBox(self)
        for nature in VALID_COMPONENT_NATURES:
            self.nature_combo.addItem(NATURE_LABELS[nature], userData=nature)
        self.category_combo = ComboBox(self)
        self.category_combo.addItem("— Seçilmedi —", userData=None)
        for category in self._expense_categories:
            self.category_combo.addItem(category["name"], userData=category["id"])
        self.active_switch = SwitchButton(self)
        self.active_switch.setChecked(True)

        self._form.addRow("Kod", self.code_edit)
        self._form.addRow("Ad", self.name_edit)
        self._form.addRow("Nitelik", self.nature_combo)
        self._form.addRow("Varsayılan Gider Kategorisi", self.category_combo)
        self._form.addRow("Aktif", self.active_switch)

        self.nature_combo.currentIndexChanged.connect(self._sync_category_enabled)

        if data:
            self.code_edit.setText(str(data["code"]))
            self.name_edit.setText(str(data["name"]))
            index = self.nature_combo.findData(data["nature"])
            if index >= 0:
                self.nature_combo.setCurrentIndex(index)
            default_category_id = data.get("default_category_id")
            if default_category_id is not None:
                cat_index = self.category_combo.findData(default_category_id)
                if cat_index >= 0:
                    self.category_combo.setCurrentIndex(cat_index)
            self.active_switch.setChecked(bool(data["is_active"]))

        self._sync_category_enabled()

    def _sync_category_enabled(self) -> None:
        is_expense = self.nature_combo.currentData() == "expense"
        self.category_combo.setEnabled(is_expense)
        if not is_expense:
            self.category_combo.setCurrentIndex(0)

    def get_values(self) -> Dict[str, Any]:
        nature = self.nature_combo.currentData()
        default_category_id = self.category_combo.currentData() if nature == "expense" else None
        return {
            "code": self.code_edit.text(),
            "name": self.name_edit.text(),
            "nature": nature,
            "default_category_id": default_category_id,
            "is_active": self.active_switch.isChecked(),
        }
