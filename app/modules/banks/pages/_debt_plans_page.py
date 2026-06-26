"""Borç planları sayfa tabanı."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, ComboBox, MessageBox, PrimaryPushButton, PushButton, TitleLabel

from app.core.constants import PLAN_KIND_LABELS
from app.core.exceptions import AppError, ValidationError
from app.modules.banks.dialogs.add_debt_plan_dialog import AddDebtPlanDialog
from app.modules.banks.dialogs.debt_plan_detail_dialog import DebtPlanDetailDialog
from app.modules.banks.pages._ui_helpers import active_label, show_error, show_success
from app.ui.table_utils import autosize_columns
from app.services.bank_service import BankService
from app.services.debt_plan_service import DebtPlanService
from app.services.reference_service import ReferenceService


class DebtPlansPageBase(QWidget):
    """Kredi / taksitli avans plan listesi tabanı."""

    def __init__(
        self,
        page_title: str,
        allowed_kinds: List[str],
        default_plan_kind: str,
        lock_plan_kind: bool = False,
        show_kind_column: bool = True,
        show_kind_filter: bool = False,
        show_source_column: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._page_title = page_title
        self._allowed_kinds = allowed_kinds
        self._default_plan_kind = default_plan_kind
        self._lock_plan_kind = lock_plan_kind
        self._show_kind_column = show_kind_column
        self._show_kind_filter = show_kind_filter
        self._show_source_column = show_source_column
        self._service = DebtPlanService()
        self._bank_service = BankService()
        self._reference_service = ReferenceService()
        self._rows: List[Dict[str, Any]] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.setSpacing(16)
        layout.addWidget(TitleLabel(self._page_title, self))

        if self._show_kind_filter:
            filter_row = QHBoxLayout()
            filter_row.addWidget(BodyLabel("Tür Filtresi:", self))
            self.kind_filter = ComboBox(self)
            self.kind_filter.addItem("Tümü", userData=None)
            for kind in self._allowed_kinds:
                self.kind_filter.addItem(PLAN_KIND_LABELS[kind], userData=kind)
            self.kind_filter.currentIndexChanged.connect(self.refresh)
            filter_row.addWidget(self.kind_filter)
            filter_row.addStretch()
            layout.addLayout(filter_row)

        button_row = QHBoxLayout()
        self.add_button = PrimaryPushButton("Ekle", self)
        self.edit_button = PushButton("Düzenle", self)
        self.delete_button = PushButton("Sil", self)
        self.detail_button = PushButton("Detay", self)
        self.refresh_button = PushButton("Yenile", self)
        for button in (
            self.add_button,
            self.edit_button,
            self.delete_button,
            self.detail_button,
            self.refresh_button,
        ):
            button_row.addWidget(button)
        button_row.addStretch()
        layout.addLayout(button_row)

        headers = ["#", "Banka", "Plan Adı", "Ana Para", "Para Birimi", "Başlangıç Tarihi",
                   "Taksit Sayısı", "Ödenmemiş Toplam", "Sonraki Vade", "Aktif", "Not"]
        if self._show_kind_column:
            headers.insert(1, "Tür")
        if self._show_source_column:
            headers.insert(3 if self._show_kind_column else 2, "Kaynak")

        self.table = QTableWidget(self)
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        self.add_button.clicked.connect(self._on_add)
        self.edit_button.clicked.connect(self._on_edit)
        self.delete_button.clicked.connect(self._on_delete)
        self.detail_button.clicked.connect(self._on_detail)
        self.refresh_button.clicked.connect(self.refresh)

    def refresh(self) -> None:
        if len(self._allowed_kinds) == 1:
            self._rows = self._service.list_debt_plans_by_kind(
                self._allowed_kinds[0],
                include_inactive=True,
            )
        elif self._show_kind_filter:
            selected_kind = self.kind_filter.currentData()
            if selected_kind is None:
                all_rows: List[Dict[str, Any]] = []
                for kind in self._allowed_kinds:
                    all_rows.extend(
                        self._service.list_debt_plans_by_kind(kind, include_inactive=True)
                    )
                self._rows = sorted(all_rows, key=lambda r: (r.get("start_date") or "", r["name"]))
            else:
                self._rows = self._service.list_debt_plans_by_kind(
                    selected_kind,
                    include_inactive=True,
                )
        else:
            self._rows = self._service.list_debt_plans(include_inactive=True)
            self._rows = [r for r in self._rows if r["plan_kind"] in self._allowed_kinds]

        self.table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            values = [
                row_index + 1,
                row["bank_name"],
                row["name"],
                row["principal_amount_display"]["display"],
                row["currency_code"],
                row.get("start_date") or "",
                row.get("installment_count") or 0,
                row["unpaid_total_display"]["display"],
                row.get("next_due_date") or "—",
                active_label(row["is_active"]),
                row.get("note") or "",
            ]
            if self._show_kind_column:
                values.insert(1, PLAN_KIND_LABELS.get(row["plan_kind"], row["plan_kind"]))
            if self._show_source_column:
                insert_at = 3 if self._show_kind_column else 2
                values.insert(insert_at, self._format_plan_source(row))
            for col_index, value in enumerate(values):
                self.table.setItem(row_index, col_index, QTableWidgetItem(str(value)))
        autosize_columns(self.table)

    @staticmethod
    def _format_plan_source(row: Dict[str, Any]) -> str:
        card_name = row.get("source_card_name")
        kmh_name = row.get("source_kmh_name")
        if card_name:
            return str(card_name)
        if kmh_name:
            return str(kmh_name)
        return "—"

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()

    def _selected_row(self) -> Optional[Dict[str, Any]]:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row_index = selected[0].row()
        if 0 <= row_index < len(self._rows):
            return self._rows[row_index]
        return None

    def _handle_action(self, action: Callable[[], None], success_message: str) -> None:
        try:
            action()
            show_success(self, "Başarılı", success_message)
            self.refresh()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))
        except AppError as exc:
            show_error(self, "Hata", str(exc))

    def _on_add(self) -> None:
        banks = self._bank_service.list_banks()
        currencies = self._reference_service.list_currencies()
        components = self._reference_service.list_component_types()
        if not banks or not currencies or not components:
            show_error(self, "Eksik Tanım", "Banka, para birimi ve bileşen tipleri tanımlı olmalıdır.")
            return
        dialog = AddDebtPlanDialog(
            banks,
            currencies,
            components,
            self.window(),
            default_plan_kind=self._default_plan_kind,
            lock_plan_kind=self._lock_plan_kind,
        )
        if not dialog.exec_():
            return

        def action() -> None:
            self._service.create_debt_plan(dialog.get_plan_data())

        self._handle_action(action, "Borç planı eklendi.")

    def _on_edit(self) -> None:
        row = self._selected_row()
        if row is None:
            show_error(self, "Seçim Gerekli", "Düzenlemek için bir plan seçin.")
            return
        plan = self._service.get_debt_plan(int(row["id"]))
        if plan is None:
            show_error(self, "Hata", "Plan bulunamadı.")
            return
        banks = self._bank_service.list_banks(include_inactive=True)
        currencies = self._reference_service.list_currencies()
        components = self._reference_service.list_component_types()
        dialog = AddDebtPlanDialog(
            banks,
            currencies,
            components,
            self.window(),
            data=plan,
            default_plan_kind=self._default_plan_kind,
            lock_plan_kind=self._lock_plan_kind,
        )
        if not dialog.exec_():
            return

        def action() -> None:
            self._service.update_debt_plan(int(row["id"]), dialog.get_plan_data())

        self._handle_action(action, "Borç planı güncellendi.")

    def _on_delete(self) -> None:
        row = self._selected_row()
        if row is None:
            show_error(self, "Seçim Gerekli", "Silmek için bir plan seçin.")
            return
        dialog = MessageBox(
            "Silme Onayı",
            f"'{row['name']}' planını silmek istediğinize emin misiniz?",
            self.window(),
        )
        dialog.yesButton.setText("Sil")
        dialog.cancelButton.setText("İptal")
        if not dialog.exec_():
            return

        def action() -> None:
            self._service.delete_debt_plan(int(row["id"]))

        self._handle_action(action, "Borç planı silindi.")

    def _on_detail(self) -> None:
        row = self._selected_row()
        if row is None:
            show_error(self, "Seçim Gerekli", "Detay için bir plan seçin.")
            return
        plan = self._service.get_debt_plan(int(row["id"]))
        if plan is None:
            show_error(self, "Hata", "Plan bulunamadı.")
            return
        DebtPlanDetailDialog(
            plan,
            debt_plan_service=self._service,
            on_changed=self.refresh,
            parent=self.window(),
        ).exec_()
