"""Tanımlar sayfası — referans verisi yönetimi."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import InfoBar, InfoBarPosition, MessageBox, PrimaryPushButton, PushButton, TitleLabel

from app.core.constants import NATURE_LABELS
from app.core.exceptions import AppError, ValidationError
from app.modules.banks.dialogs.reference_dialogs import (
    AssetDialog,
    CategoryDialog,
    ComponentTypeDialog,
    CurrencyDialog,
)
from app.services.reference_service import ReferenceService
from app.ui.table_utils import autosize_columns


def _active_label(value: Any) -> str:
    return "Evet" if bool(value) else "Hayır"


def _show_error(parent: QWidget, title: str, message: str) -> None:
    InfoBar.error(
        title=title,
        content=message,
        orient=Qt.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP,
        duration=4000,
        parent=parent.window(),
    )


def _show_success(parent: QWidget, title: str, message: str) -> None:
    InfoBar.success(
        title=title,
        content=message,
        orient=Qt.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP,
        duration=2500,
        parent=parent.window(),
    )


class ReferenceTabBase(QWidget):
    """Referans verisi sekmesi tabanı."""

    def __init__(
        self,
        service: ReferenceService,
        columns: List[str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        # İlk sütun veritabanı ID'si yerine sıra numarası gösterir.
        if columns and columns[0] == "ID":
            columns = ["#"] + columns[1:]
        self._service = service
        self._columns = columns
        self._rows: List[Dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)

        button_row = QHBoxLayout()
        self.add_button = PrimaryPushButton("Ekle", self)
        self.edit_button = PushButton("Düzenle", self)
        self.delete_button = PushButton("Sil", self)
        self.refresh_button = PushButton("Yenile", self)
        button_row.addWidget(self.add_button)
        button_row.addWidget(self.edit_button)
        button_row.addWidget(self.delete_button)
        button_row.addWidget(self.refresh_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.table = QTableWidget(self)
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        self.add_button.clicked.connect(self._on_add)
        self.edit_button.clicked.connect(self._on_edit)
        self.delete_button.clicked.connect(self._on_delete)
        self.refresh_button.clicked.connect(self.refresh)

    def refresh(self) -> None:
        raise NotImplementedError

    def _populate_table(self, rows: List[List[str]]) -> None:
        self.table.setRowCount(len(rows))
        for row_index, row_values in enumerate(rows):
            # İlk sütun sıra numarası; alt sekmeler ID geçse de gösterimde değiştirilir.
            display_values = [row_index + 1] + list(row_values[1:])
            for col_index, value in enumerate(display_values):
                self.table.setItem(row_index, col_index, QTableWidgetItem(str(value)))
        autosize_columns(self.table)

    def _selected_row(self) -> Optional[Dict[str, Any]]:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row_index = selected[0].row()
        if 0 <= row_index < len(self._rows):
            return self._rows[row_index]
        return None

    def _on_add(self) -> None:
        raise NotImplementedError

    def _on_edit(self) -> None:
        raise NotImplementedError

    def _on_delete(self) -> None:
        raise NotImplementedError

    def _confirm_delete(self, entity_label: str) -> bool:
        dialog = MessageBox(
            "Silme Onayı",
            f"Seçili {entity_label} kaydını silmek istediğinize emin misiniz?",
            self.window(),
        )
        dialog.yesButton.setText("Sil")
        dialog.cancelButton.setText("İptal")
        return dialog.exec_()

    def _handle_action(self, action: Callable[[], None], success_message: str) -> None:
        try:
            action()
            _show_success(self, "Başarılı", success_message)
            self.refresh()
        except ValidationError as exc:
            _show_error(self, "Doğrulama Hatası", str(exc))
        except AppError as exc:
            _show_error(self, "Hata", str(exc))


class CurrencyTab(ReferenceTabBase):
    def __init__(self, service: ReferenceService, parent: Optional[QWidget] = None) -> None:
        super().__init__(service, ["ID", "Kod", "Sembol", "Scale", "Aktif"], parent)

    def refresh(self) -> None:
        self._rows = self._service.list_currencies(include_inactive=True)
        table_rows = [
            [
                row["id"],
                row["code"],
                row.get("symbol") or "",
                row["scale"],
                _active_label(row["is_active"]),
            ]
            for row in self._rows
        ]
        self._populate_table(table_rows)

    def _on_add(self) -> None:
        dialog = CurrencyDialog(self.window())
        if not dialog.exec_():
            return
        values = dialog.get_values()

        def action() -> None:
            self._service.create_currency(values["code"], values["symbol"], values["scale"])

        self._handle_action(action, "Para birimi eklendi.")

    def _on_edit(self) -> None:
        row = self._selected_row()
        if row is None:
            _show_error(self, "Seçim Gerekli", "Düzenlemek için bir kayıt seçin.")
            return
        dialog = CurrencyDialog(self.window(), data=row)
        if not dialog.exec_():
            return
        values = dialog.get_values()

        def action() -> None:
            self._service.update_currency(
                int(row["id"]),
                values["code"],
                values["symbol"],
                values["scale"],
                values["is_active"],
            )

        self._handle_action(action, "Para birimi güncellendi.")

    def _on_delete(self) -> None:
        row = self._selected_row()
        if row is None:
            _show_error(self, "Seçim Gerekli", "Silmek için bir kayıt seçin.")
            return
        if not self._confirm_delete("para birimi"):
            return

        def action() -> None:
            self._service.delete_currency(int(row["id"]))

        self._handle_action(action, "Para birimi silindi.")


class CategoryTab(ReferenceTabBase):
    def __init__(self, service: ReferenceService, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            service,
            ["ID", "Ad", "Nitelik", "Üst Kategori", "Aktif"],
            parent,
        )

    def refresh(self) -> None:
        self._rows = self._service.list_categories(include_inactive=True)
        table_rows = [
            [
                row["id"],
                row["name"],
                NATURE_LABELS.get(row["nature"], row["nature"]),
                row.get("parent_name") or "—",
                _active_label(row["is_active"]),
            ]
            for row in self._rows
        ]
        self._populate_table(table_rows)

    def _on_add(self) -> None:
        categories = self._service.list_categories(include_inactive=True)
        dialog = CategoryDialog(categories, self.window())
        if not dialog.exec_():
            return
        values = dialog.get_values()

        def action() -> None:
            self._service.create_category(values["name"], values["nature"], values["parent_id"])

        self._handle_action(action, "Kategori eklendi.")

    def _on_edit(self) -> None:
        row = self._selected_row()
        if row is None:
            _show_error(self, "Seçim Gerekli", "Düzenlemek için bir kayıt seçin.")
            return
        categories = self._service.list_categories(include_inactive=True)
        dialog = CategoryDialog(categories, self.window(), data=row)
        if not dialog.exec_():
            return
        values = dialog.get_values()

        def action() -> None:
            self._service.update_category(
                int(row["id"]),
                values["name"],
                values["nature"],
                values["parent_id"],
                values["is_active"],
            )

        self._handle_action(action, "Kategori güncellendi.")

    def _on_delete(self) -> None:
        row = self._selected_row()
        if row is None:
            _show_error(self, "Seçim Gerekli", "Silmek için bir kayıt seçin.")
            return
        if not self._confirm_delete("kategori"):
            return

        def action() -> None:
            self._service.delete_category(int(row["id"]))

        self._handle_action(action, "Kategori silindi.")


class AssetTab(ReferenceTabBase):
    def __init__(self, service: ReferenceService, parent: Optional[QWidget] = None) -> None:
        super().__init__(service, ["ID", "Ad", "Tip", "Aktif"], parent)

    def refresh(self) -> None:
        self._rows = self._service.list_assets(include_inactive=True)
        table_rows = [
            [
                row["id"],
                row["name"],
                row.get("type") or "",
                _active_label(row["is_active"]),
            ]
            for row in self._rows
        ]
        self._populate_table(table_rows)

    def _on_add(self) -> None:
        dialog = AssetDialog(self.window())
        if not dialog.exec_():
            return
        values = dialog.get_values()

        def action() -> None:
            self._service.create_asset(values["name"], values["type"])

        self._handle_action(action, "Varlık eklendi.")

    def _on_edit(self) -> None:
        row = self._selected_row()
        if row is None:
            _show_error(self, "Seçim Gerekli", "Düzenlemek için bir kayıt seçin.")
            return
        dialog = AssetDialog(self.window(), data=row)
        if not dialog.exec_():
            return
        values = dialog.get_values()

        def action() -> None:
            self._service.update_asset(
                int(row["id"]),
                values["name"],
                values["type"],
                values["is_active"],
            )

        self._handle_action(action, "Varlık güncellendi.")

    def _on_delete(self) -> None:
        row = self._selected_row()
        if row is None:
            _show_error(self, "Seçim Gerekli", "Silmek için bir kayıt seçin.")
            return
        if not self._confirm_delete("varlık"):
            return

        def action() -> None:
            self._service.delete_asset(int(row["id"]))

        self._handle_action(action, "Varlık silindi.")


class ComponentTypeTab(ReferenceTabBase):
    def __init__(self, service: ReferenceService, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            service,
            ["ID", "Kod", "Ad", "Nitelik", "Varsayılan Gider Kategorisi", "Aktif"],
            parent,
        )

    def _expense_categories(self) -> List[Dict[str, Any]]:
        return [
            category
            for category in self._service.list_categories()
            if category["nature"] == "expense"
        ]

    def refresh(self) -> None:
        self._rows = self._service.list_component_types(include_inactive=True)
        table_rows = [
            [
                row["id"],
                row["code"],
                row["name"],
                NATURE_LABELS.get(row["nature"], row["nature"]),
                row.get("default_category_name") or "—",
                _active_label(row["is_active"]),
            ]
            for row in self._rows
        ]
        self._populate_table(table_rows)

    def _on_add(self) -> None:
        dialog = ComponentTypeDialog(
            self.window(),
            expense_categories=self._expense_categories(),
        )
        if not dialog.exec_():
            return
        values = dialog.get_values()

        def action() -> None:
            self._service.create_component_type(
                values["code"],
                values["name"],
                values["nature"],
                values["default_category_id"],
            )

        self._handle_action(action, "Bileşen tipi eklendi.")

    def _on_edit(self) -> None:
        row = self._selected_row()
        if row is None:
            _show_error(self, "Seçim Gerekli", "Düzenlemek için bir kayıt seçin.")
            return
        dialog = ComponentTypeDialog(
            self.window(),
            data=row,
            expense_categories=self._expense_categories(),
        )
        if not dialog.exec_():
            return
        values = dialog.get_values()

        def action() -> None:
            self._service.update_component_type(
                int(row["id"]),
                values["code"],
                values["name"],
                values["nature"],
                values["is_active"],
                values["default_category_id"],
            )

        self._handle_action(action, "Bileşen tipi güncellendi.")

    def _on_delete(self) -> None:
        row = self._selected_row()
        if row is None:
            _show_error(self, "Seçim Gerekli", "Silmek için bir kayıt seçin.")
            return
        if not self._confirm_delete("bileşen tipi"):
            return

        def action() -> None:
            self._service.delete_component_type(int(row["id"]))

        self._handle_action(action, "Bileşen tipi silindi.")


class DefinitionsPage(QWidget):
    """Bankalar modülü tanım yönetimi sayfası."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service = ReferenceService()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.setSpacing(16)

        layout.addWidget(TitleLabel("Tanımlar", self))

        tabs = QTabWidget(self)
        self._currency_tab = CurrencyTab(self._service, tabs)
        self._category_tab = CategoryTab(self._service, tabs)
        self._asset_tab = AssetTab(self._service, tabs)
        self._component_tab = ComponentTypeTab(self._service, tabs)

        tabs.addTab(self._currency_tab, "Para Birimleri")
        tabs.addTab(self._category_tab, "Kategoriler")
        tabs.addTab(self._asset_tab, "Varlıklar")
        tabs.addTab(self._component_tab, "Taksit Bileşen Tipleri")
        layout.addWidget(tabs)

        self._currency_tab.refresh()
        self._category_tab.refresh()
        self._asset_tab.refresh()
        self._component_tab.refresh()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._currency_tab.refresh()
        self._category_tab.refresh()
        self._asset_tab.refresh()
        self._component_tab.refresh()
