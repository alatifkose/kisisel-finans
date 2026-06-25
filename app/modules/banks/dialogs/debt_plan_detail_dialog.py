"""Borç planı detay dialogu."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, MessageBox, PrimaryPushButton, PushButton, SubtitleLabel

from app.core.constants import INSTALLMENT_STATUS_LABELS, InstallmentStatus, NATURE_LABELS, PLAN_KIND_LABELS
from app.core.exceptions import AppError, ValidationError
from app.modules.banks.dialogs.pay_installment_dialog import PayInstallmentDialog
from app.modules.banks.pages._ui_helpers import show_error, show_success
from app.services.account_service import AccountService
from app.services.debt_plan_service import DebtPlanService
from app.services.reference_service import ReferenceService


class DebtPlanDetailDialog(QDialog):
    """Borç planı detay görünümü; taksit ödeme ve geri alma destekler."""

    def __init__(
        self,
        plan: Dict[str, Any],
        debt_plan_service: Optional[DebtPlanService] = None,
        account_service: Optional[AccountService] = None,
        reference_service: Optional[ReferenceService] = None,
        on_changed: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._plan = plan
        self._installments: List[Dict[str, Any]] = plan.get("installments") or []
        self._service = debt_plan_service or DebtPlanService()
        self._account_service = account_service or AccountService()
        self._reference_service = reference_service or ReferenceService()
        self._on_changed = on_changed

        self.setWindowTitle("Plan Detayı")
        self.setModal(True)
        self.setMinimumSize(860, 680)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(SubtitleLabel(plan["name"], self))

        info = QFormLayout()
        info.addRow("Banka", BodyLabel(plan["bank_name"], self))
        info.addRow(
            "Plan Türü",
            BodyLabel(PLAN_KIND_LABELS.get(plan["plan_kind"], plan["plan_kind"]), self),
        )
        info.addRow("Ana Para", BodyLabel(plan["principal_amount_display"]["display"], self))
        info.addRow("Para Birimi", BodyLabel(plan["currency_code"], self))
        info.addRow(
            "Kaynak",
            BodyLabel(self._format_plan_source(plan), self),
        )
        info.addRow("Başlangıç Tarihi", BodyLabel(str(plan.get("start_date") or "—"), self))
        info.addRow("Taksit Sayısı", BodyLabel(str(plan.get("installment_count") or 0), self))
        info.addRow("Not", BodyLabel(str(plan.get("note") or "—"), self))
        layout.addLayout(info)

        totals = plan.get("totals") or {}
        totals_text = (
            f"Toplam taksit: {totals.get('installment_total_sum_display', {}).get('display', '—')}\n"
            f"Anapara bileşeni: {totals.get('principal_component_total_display', {}).get('display', '—')}\n"
            f"Gider bileşeni: {totals.get('expense_component_total_display', {}).get('display', '—')}\n"
            f"Ödenmemiş: {totals.get('unpaid_total_display', {}).get('display', '—')}\n"
            f"Sonraki vade: {totals.get('next_due_date') or '—'}"
        )
        layout.addWidget(BodyLabel(totals_text, self))

        layout.addWidget(SubtitleLabel("Taksitler", self))
        self.inst_table = QTableWidget(self)
        self.inst_table.setColumnCount(8)
        self.inst_table.setHorizontalHeaderLabels(
            [
                "Sıra",
                "Vade",
                "Toplam",
                "Kalan Anapara",
                "Durum",
                "Ödeme Tarihi",
                "İşlem ID",
                "Not",
            ]
        )
        self.inst_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.inst_table.verticalHeader().setVisible(False)
        self.inst_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.inst_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.inst_table)

        layout.addWidget(SubtitleLabel("Seçili Taksit Bileşenleri", self))
        self.comp_table = QTableWidget(self)
        self.comp_table.setColumnCount(3)
        self.comp_table.setHorizontalHeaderLabels(["Bileşen Tipi", "Nitelik", "Tutar"])
        self.comp_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.comp_table.verticalHeader().setVisible(False)
        self.comp_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.comp_table)

        button_row = QHBoxLayout()
        self.pay_button = PrimaryPushButton("Taksit Öde", self)
        self.unpay_button = PushButton("Ödemeyi Geri Al", self)
        self.close_button = PushButton("Kapat", self)
        button_row.addWidget(self.pay_button)
        button_row.addWidget(self.unpay_button)
        button_row.addStretch()
        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)

        self._populate_installments()
        self.inst_table.itemSelectionChanged.connect(self._on_selection)
        self.pay_button.clicked.connect(self._on_pay)
        self.unpay_button.clicked.connect(self._on_unpay)
        self.close_button.clicked.connect(self.accept)

        if self._installments:
            self.inst_table.selectRow(0)
            self._show_components(self._installments[0])
        self._sync_action_buttons()

    def _populate_installments(self) -> None:
        self.inst_table.setRowCount(len(self._installments))
        for row_index, inst in enumerate(self._installments):
            remaining_display = inst.get("remaining_principal_after_display", {}).get("display", "—")
            values = [
                inst["seq"],
                inst["due_date"],
                inst["total_amount_display"]["display"],
                remaining_display,
                INSTALLMENT_STATUS_LABELS.get(inst["status"], inst["status"]),
                inst.get("paid_date") or "—",
                inst.get("paid_transaction_id") or "—",
                inst.get("note") or "",
            ]
            for col_index, value in enumerate(values):
                self.inst_table.setItem(row_index, col_index, QTableWidgetItem(str(value)))

    def _selected_installment(self) -> Optional[Dict[str, Any]]:
        selected = self.inst_table.selectionModel().selectedRows()
        if not selected:
            return None
        row_index = selected[0].row()
        if 0 <= row_index < len(self._installments):
            return self._installments[row_index]
        return None

    def _on_selection(self) -> None:
        inst = self._selected_installment()
        if inst is not None:
            self._show_components(inst)
        self._sync_action_buttons()

    def _sync_action_buttons(self) -> None:
        inst = self._selected_installment()
        if inst is None:
            self.pay_button.setEnabled(False)
            self.unpay_button.setEnabled(False)
            return
        status = str(inst.get("status"))
        self.pay_button.setEnabled(status == InstallmentStatus.PLANNED)
        self.unpay_button.setEnabled(status == InstallmentStatus.PAID)

    def _show_components(self, installment: Dict[str, Any]) -> None:
        components = installment.get("components") or []
        self.comp_table.setRowCount(len(components))
        for row_index, comp in enumerate(components):
            values = [
                comp.get("component_name") or comp.get("component_code") or "",
                NATURE_LABELS.get(comp.get("component_nature"), comp.get("component_nature", "")),
                comp["amount_display"]["display"],
            ]
            for col_index, value in enumerate(values):
                self.comp_table.setItem(row_index, col_index, QTableWidgetItem(str(value)))

    def _reload_plan(self) -> None:
        plan = self._service.get_debt_plan(int(self._plan["id"]))
        if plan is None:
            return
        self._plan = plan
        self._installments = plan.get("installments") or []
        self._populate_installments()
        if self._installments:
            self.inst_table.selectRow(0)
            self._show_components(self._installments[0])
        self._sync_action_buttons()
        if self._on_changed:
            self._on_changed()

    def _on_pay(self) -> None:
        inst = self._selected_installment()
        if inst is None:
            show_error(self, "Seçim Gerekli", "Ödenecek taksiti seçin.")
            return

        installment = self._service.get_installment_for_payment(int(inst["id"]))
        if installment is None:
            show_error(self, "Hata", "Taksit bulunamadı.")
            return

        accounts = [
            account
            for account in self._account_service.list_accounts()
            if int(account["currency_id"]) == int(installment["currency_id"])
        ]
        if not accounts:
            show_error(
                self,
                "Hesap Gerekli",
                "Bu para biriminde aktif hesap bulunamadı.",
            )
            return

        expense_categories = [
            category
            for category in self._reference_service.list_categories()
            if category["nature"] == "expense"
        ]
        dialog = PayInstallmentDialog(
            installment,
            accounts,
            expense_categories,
            self.window(),
        )
        if not dialog.exec_():
            return

        payment = dialog.get_payment_data()
        try:
            self._service.pay_installment(
                payment["installment_id"],
                payment["account_id"],
                payment["paid_date"],
                payment["category_overrides"],
            )
            show_success(self, "Başarılı", "Taksit ödemesi kaydedildi.")
            self._reload_plan()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))
        except AppError as exc:
            show_error(self, "Hata", str(exc))

    def _on_unpay(self) -> None:
        inst = self._selected_installment()
        if inst is None:
            show_error(self, "Seçim Gerekli", "Geri alınacak taksiti seçin.")
            return

        dialog = MessageBox(
            "Ödemeyi Geri Al",
            f"{inst['seq']}. taksit ödemesini geri almak istediğinize emin misiniz?",
            self.window(),
        )
        dialog.yesButton.setText("Geri Al")
        dialog.cancelButton.setText("İptal")
        if not dialog.exec_():
            return

        try:
            self._service.unpay_installment(int(inst["id"]))
            show_success(self, "Başarılı", "Taksit ödemesi geri alındı.")
            self._reload_plan()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))
        except AppError as exc:
            show_error(self, "Hata", str(exc))

    @staticmethod
    def _format_plan_source(plan: Dict[str, Any]) -> str:
        card_name = plan.get("source_card_name")
        kmh_name = plan.get("source_kmh_name")
        if card_name:
            return str(card_name)
        if kmh_name:
            return str(kmh_name)
        return "—"
