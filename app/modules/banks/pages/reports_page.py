"""Raporlar sayfası."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, MessageBox, PushButton, TitleLabel

from app.core.constants import INSTALLMENT_STATUS_LABELS
from app.core.exceptions import AppError, ValidationError
from app.modules.banks.pages._ui_helpers import show_error, show_success
from app.services.account_service import AccountService
from app.services.audit_service import AuditService
from app.services.report_service import ReportService


def _fill_table(table: QTableWidget, rows: List[List[str]]) -> None:
    table.setRowCount(len(rows))
    for row_index, values in enumerate(rows):
        for col_index, value in enumerate(values):
            table.setItem(row_index, col_index, QTableWidgetItem(str(value)))


def _make_date_edit(default: Optional[QDate] = None) -> QDateEdit:
    edit = QDateEdit()
    edit.setCalendarPopup(True)
    edit.setDisplayFormat("yyyy-MM-dd")
    edit.setDate(default or QDate.currentDate())
    return edit


class ReportsPage(QWidget):
    """Finansal raporlar, reconcile ve audit log."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._report_service = ReportService()
        self._account_service = AccountService()
        self._audit_service = AuditService()
        self._reconcile_rows: List[Dict[str, Any]] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.setSpacing(16)
        layout.addWidget(TitleLabel("Raporlar", self))

        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)

        self._build_cashflow_tab()
        self._build_category_tab()
        self._build_asset_tab()
        self._build_financing_tab()
        self._build_principal_tab()
        self._build_transfer_tab()
        self._build_calendar_tab()
        self._build_reconcile_tab()
        self._build_audit_tab()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_current_tab()

    def _refresh_current_tab(self) -> None:
        index = self.tabs.currentIndex()
        refreshers = [
            self._refresh_cashflow,
            self._refresh_category,
            self._refresh_asset,
            self._refresh_financing,
            self._refresh_principal,
            self._refresh_transfer,
            self._refresh_calendar,
            self._refresh_reconcile,
            self._refresh_audit,
        ]
        if 0 <= index < len(refreshers):
            refreshers[index]()

    def _add_tab(
        self,
        title: str,
        note: str,
        filter_widget: QWidget,
        table: QTableWidget,
        refresh_handler: Callable[[], None],
    ) -> None:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setSpacing(12)
        tab_layout.addWidget(BodyLabel(note, tab))

        filter_row = QHBoxLayout()
        filter_row.addWidget(filter_widget)
        refresh_button = PushButton("Yenile", tab)
        refresh_button.clicked.connect(refresh_handler)
        filter_row.addWidget(refresh_button)
        filter_row.addStretch()
        tab_layout.addLayout(filter_row)
        tab_layout.addWidget(table)

        self.tabs.addTab(tab, title)
        self.tabs.currentChanged.connect(lambda _: self._refresh_current_tab())

    def _build_cashflow_tab(self) -> None:
        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addWidget(BodyLabel("Yıl:", filter_widget))
        self.cashflow_year = QSpinBox(filter_widget)
        self.cashflow_year.setRange(2000, 2100)
        self.cashflow_year.setValue(date.today().year)
        filter_layout.addWidget(self.cashflow_year)
        filter_layout.addWidget(BodyLabel("Ay:", filter_widget))
        self.cashflow_month = QSpinBox(filter_widget)
        self.cashflow_month.setRange(1, 12)
        self.cashflow_month.setValue(date.today().month)
        filter_layout.addWidget(self.cashflow_month)

        self.cashflow_table = QTableWidget()
        self.cashflow_table.setColumnCount(5)
        self.cashflow_table.setHorizontalHeaderLabels(
            ["Para Birimi", "Gelir", "Gider", "Masraf", "Net Nakit Akışı"]
        )
        self.cashflow_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cashflow_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self._add_tab(
            "Nakit Akışı",
            "Gelir, gider ve masraf toplamları. Anapara ve transfer dahil değildir.",
            filter_widget,
            self.cashflow_table,
            self._refresh_cashflow,
        )

    def _build_category_tab(self) -> None:
        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addWidget(BodyLabel("Başlangıç:", filter_widget))
        self.category_start = _make_date_edit(QDate(date.today().year, date.today().month, 1))
        filter_layout.addWidget(self.category_start)
        filter_layout.addWidget(BodyLabel("Bitiş:", filter_widget))
        self.category_end = _make_date_edit()
        filter_layout.addWidget(self.category_end)

        self.category_table = QTableWidget()
        self.category_table.setColumnCount(5)
        self.category_table.setHorizontalHeaderLabels(
            ["Kategori", "Nitelik", "Para Birimi", "Toplam", "İşlem Sayısı"]
        )
        self.category_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.category_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self._add_tab(
            "Kategori",
            "Kategori bazında gelir/gider/masraf. Anapara ve transfer hariç.",
            filter_widget,
            self.category_table,
            self._refresh_category,
        )

    def _build_asset_tab(self) -> None:
        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addWidget(BodyLabel("Başlangıç:", filter_widget))
        self.asset_start = _make_date_edit(QDate(date.today().year, date.today().month, 1))
        filter_layout.addWidget(self.asset_start)
        filter_layout.addWidget(BodyLabel("Bitiş:", filter_widget))
        self.asset_end = _make_date_edit()
        filter_layout.addWidget(self.asset_end)

        self.asset_table = QTableWidget()
        self.asset_table.setColumnCount(6)
        self.asset_table.setHorizontalHeaderLabels(
            ["Varlık", "Varlık Tipi", "Nitelik", "Para Birimi", "Toplam", "İşlem Sayısı"]
        )
        self.asset_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.asset_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self._add_tab(
            "Varlık",
            "Varlık bazında hareketler. Anapara ve transfer hariç.",
            filter_widget,
            self.asset_table,
            self._refresh_asset,
        )

    def _build_financing_tab(self) -> None:
        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addWidget(BodyLabel("Başlangıç:", filter_widget))
        self.financing_start = _make_date_edit(QDate(date.today().year, 1, 1))
        filter_layout.addWidget(self.financing_start)
        filter_layout.addWidget(BodyLabel("Bitiş:", filter_widget))
        self.financing_end = _make_date_edit()
        filter_layout.addWidget(self.financing_end)

        self.financing_table = QTableWidget()
        self.financing_table.setColumnCount(3)
        self.financing_table.setHorizontalHeaderLabels(
            ["Bileşen Tipi", "Para Birimi", "Toplam"]
        )
        self.financing_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.financing_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self._add_tab(
            "Finansman Gideri",
            "Taksit ödemelerindeki faiz, vergi, sigorta vb. expense bileşenleri. Anapara hariç.",
            filter_widget,
            self.financing_table,
            self._refresh_financing,
        )

    def _build_principal_tab(self) -> None:
        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addWidget(BodyLabel("Başlangıç:", filter_widget))
        self.principal_start = _make_date_edit(QDate(date.today().year, 1, 1))
        filter_layout.addWidget(self.principal_start)
        filter_layout.addWidget(BodyLabel("Bitiş:", filter_widget))
        self.principal_end = _make_date_edit()
        filter_layout.addWidget(self.principal_end)

        self.principal_table = QTableWidget()
        self.principal_table.setColumnCount(3)
        self.principal_table.setHorizontalHeaderLabels(
            ["Para Birimi", "Ödenen Anapara", "İşlem Sayısı"]
        )
        self.principal_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.principal_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self._add_tab(
            "Anapara Ödemeleri",
            "Bu tutarlar gider değildir; borç azaltımıdır.",
            filter_widget,
            self.principal_table,
            self._refresh_principal,
        )

    def _build_transfer_tab(self) -> None:
        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addWidget(BodyLabel("Başlangıç:", filter_widget))
        self.transfer_start = _make_date_edit(QDate(date.today().year, date.today().month, 1))
        filter_layout.addWidget(self.transfer_start)
        filter_layout.addWidget(BodyLabel("Bitiş:", filter_widget))
        self.transfer_end = _make_date_edit()
        filter_layout.addWidget(self.transfer_end)

        self.transfer_table = QTableWidget()
        self.transfer_table.setColumnCount(9)
        self.transfer_table.setHorizontalHeaderLabels(
            [
                "Tarih",
                "Kaynak Hesap",
                "Kaynak Tutar",
                "Kaynak PB",
                "Hedef Hesap",
                "Hedef Tutar",
                "Hedef PB",
                "Kur",
                "Açıklama",
            ]
        )
        self.transfer_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.transfer_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self._add_tab(
            "Transferler",
            "Transferler gelir/gider değildir; hesaplar arası yer değiştirmedir.",
            filter_widget,
            self.transfer_table,
            self._refresh_transfer,
        )

    def _build_calendar_tab(self) -> None:
        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addWidget(BodyLabel("Başlangıç:", filter_widget))
        self.calendar_start = _make_date_edit()
        filter_layout.addWidget(self.calendar_start)
        filter_layout.addWidget(BodyLabel("Bitiş:", filter_widget))
        self.calendar_end = _make_date_edit(QDate.currentDate().addMonths(3))
        filter_layout.addWidget(self.calendar_end)

        self.calendar_table = QTableWidget()
        self.calendar_table.setColumnCount(7)
        self.calendar_table.setHorizontalHeaderLabels(
            ["Tarih", "Tür", "Banka", "Başlık", "Para Birimi", "Tutar", "Durum"]
        )
        self.calendar_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.calendar_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self._add_tab(
            "Ödeme Takvimi",
            "Planlanan taksitler ve kart ekstre son ödeme tarihleri.",
            filter_widget,
            self.calendar_table,
            self._refresh_calendar,
        )

    def _build_reconcile_tab(self) -> None:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setSpacing(12)
        tab_layout.addWidget(
            BodyLabel(
                "Ledger hesaplarda kayıtlı bakiye ile hareketlerden türetilen bakiye karşılaştırılır.",
                tab,
            )
        )

        button_row = QHBoxLayout()
        refresh_button = PushButton("Yenile", tab)
        refresh_button.clicked.connect(self._refresh_reconcile)
        self.reconcile_fix_button = PushButton("Seçili Hesabı Düzelt", tab)
        self.reconcile_fix_button.clicked.connect(self._on_reconcile_fix)
        button_row.addWidget(refresh_button)
        button_row.addWidget(self.reconcile_fix_button)
        button_row.addStretch()
        tab_layout.addLayout(button_row)

        self.reconcile_table = QTableWidget(tab)
        self.reconcile_table.setColumnCount(10)
        self.reconcile_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Banka",
                "Hesap",
                "Para Birimi",
                "Takip Modu",
                "Açılış",
                "Kayıtlı Bakiye",
                "Hesaplanan Bakiye",
                "Fark",
                "Durum",
            ]
        )
        self.reconcile_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.reconcile_table.setSelectionMode(QTableWidget.SingleSelection)
        self.reconcile_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.reconcile_table.setEditTriggers(QTableWidget.NoEditTriggers)
        tab_layout.addWidget(self.reconcile_table)

        self.tabs.addTab(tab, "Reconcile")

    def _build_audit_tab(self) -> None:
        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addWidget(BodyLabel("Son kayıt sayısı:", filter_widget))
        self.audit_limit = QSpinBox(filter_widget)
        self.audit_limit.setRange(50, 1000)
        self.audit_limit.setValue(200)
        filter_layout.addWidget(self.audit_limit)

        self.audit_table = QTableWidget()
        self.audit_table.setColumnCount(6)
        self.audit_table.setHorizontalHeaderLabels(
            ["ID", "Tarih", "Varlık Tipi", "Varlık ID", "İşlem", "Eski → Yeni"]
        )
        self.audit_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.audit_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self._add_tab(
            "Audit Log",
            "Kritik değişiklik kayıtları (create/update/delete).",
            filter_widget,
            self.audit_table,
            self._refresh_audit,
        )

    def _date_str(self, edit: QDateEdit) -> str:
        return edit.date().toString("yyyy-MM-dd")

    def _amount_display(self, amount: Dict[str, Any]) -> str:
        symbol = amount.get("currency_symbol") or ""
        suffix = f" {symbol}".rstrip()
        return f"{amount['display']}{suffix}"

    def _refresh_cashflow(self) -> None:
        try:
            rows = self._report_service.get_cashflow_report(
                self.cashflow_year.value(),
                self.cashflow_month.value(),
            )
            table_rows = [
                [
                    row["currency_code"],
                    self._amount_display(row["income_total_display"]),
                    self._amount_display(row["expense_total_display"]),
                    self._amount_display(row["cost_total_display"]),
                    self._amount_display(row["net_cashflow_display"]),
                ]
                for row in rows
            ]
            _fill_table(self.cashflow_table, table_rows)
        except ValidationError as exc:
            show_error(self, "Hata", str(exc))

    def _refresh_category(self) -> None:
        try:
            rows = self._report_service.get_category_report(
                self._date_str(self.category_start),
                self._date_str(self.category_end),
            )
            table_rows = [
                [
                    row["category_name"],
                    row["nature_label"],
                    row["currency_code"],
                    self._amount_display(row["total_amount_display"]),
                    row["transaction_count"],
                ]
                for row in rows
            ]
            _fill_table(self.category_table, table_rows)
        except ValidationError as exc:
            show_error(self, "Hata", str(exc))

    def _refresh_asset(self) -> None:
        try:
            rows = self._report_service.get_asset_report(
                self._date_str(self.asset_start),
                self._date_str(self.asset_end),
            )
            table_rows = [
                [
                    row["asset_name"],
                    row["asset_type"],
                    row["nature_label"],
                    row["currency_code"],
                    self._amount_display(row["total_amount_display"]),
                    row["transaction_count"],
                ]
                for row in rows
            ]
            _fill_table(self.asset_table, table_rows)
        except ValidationError as exc:
            show_error(self, "Hata", str(exc))

    def _refresh_financing(self) -> None:
        try:
            rows = self._report_service.get_financing_expense_report(
                self._date_str(self.financing_start),
                self._date_str(self.financing_end),
            )
            table_rows = [
                [
                    row["component_type_name"],
                    row["currency_code"],
                    self._amount_display(row["total_amount_display"]),
                ]
                for row in rows
            ]
            _fill_table(self.financing_table, table_rows)
        except ValidationError as exc:
            show_error(self, "Hata", str(exc))

    def _refresh_principal(self) -> None:
        try:
            rows = self._report_service.get_principal_payment_report(
                self._date_str(self.principal_start),
                self._date_str(self.principal_end),
            )
            table_rows = [
                [
                    row["currency_code"],
                    self._amount_display(row["total_principal_paid_display"]),
                    row["transaction_count"],
                ]
                for row in rows
            ]
            _fill_table(self.principal_table, table_rows)
        except ValidationError as exc:
            show_error(self, "Hata", str(exc))

    def _refresh_transfer(self) -> None:
        try:
            rows = self._report_service.get_transfer_report(
                self._date_str(self.transfer_start),
                self._date_str(self.transfer_end),
            )
            table_rows = [
                [
                    row["transfer_date"],
                    f"{row['from_bank_name']} / {row['from_account_name']}",
                    self._amount_display(row["from_amount_display"]),
                    row["from_currency_code"],
                    f"{row['to_bank_name']} / {row['to_account_name']}",
                    self._amount_display(row["to_amount_display"]),
                    row["to_currency_code"],
                    row.get("exchange_rate") or "—",
                    row.get("description") or "",
                ]
                for row in rows
            ]
            _fill_table(self.transfer_table, table_rows)
        except ValidationError as exc:
            show_error(self, "Hata", str(exc))

    def _refresh_calendar(self) -> None:
        try:
            rows = self._report_service.get_payment_calendar(
                self._date_str(self.calendar_start),
                self._date_str(self.calendar_end),
            )
            table_rows = []
            for row in rows:
                status = row.get("status") or ""
                status_label = INSTALLMENT_STATUS_LABELS.get(status, status)
                if status == "statement":
                    status_label = "Ekstre"
                elif status == "overdue":
                    status_label = "Gecikmiş"
                table_rows.append(
                    [
                        row["item_date"],
                        row["type_label"],
                        row["bank_name"],
                        row["title"],
                        row["currency_code"],
                        self._amount_display(row["amount_display"]),
                        status_label,
                    ]
                )
            _fill_table(self.calendar_table, table_rows)
        except ValidationError as exc:
            show_error(self, "Hata", str(exc))

    def _refresh_reconcile(self) -> None:
        try:
            self._reconcile_rows = self._report_service.get_reconcile_report()
            table_rows = []
            for row in self._reconcile_rows:
                status = row["status"]
                if status == "snapshot_skipped":
                    status_label = "Snapshot — atlandı"
                elif status == "ok":
                    status_label = "OK"
                else:
                    status_label = "Drift"
                table_rows.append(
                    [
                        row["account_id"],
                        row["bank_name"],
                        row["account_name"],
                        row["currency_code"],
                        row["tracking_mode"],
                        self._amount_display(row["opening_balance_display"]),
                        self._amount_display(row["current_balance_display"]),
                        self._amount_display(row["calculated_balance_display"]),
                        self._amount_display(row["difference_display"]),
                        status_label,
                    ]
                )
            _fill_table(self.reconcile_table, table_rows)
        except ValidationError as exc:
            show_error(self, "Hata", str(exc))

    def _selected_reconcile_row(self) -> Optional[Dict[str, Any]]:
        selected = self.reconcile_table.selectionModel().selectedRows()
        if not selected:
            return None
        row_index = selected[0].row()
        if 0 <= row_index < len(self._reconcile_rows):
            return self._reconcile_rows[row_index]
        return None

    def _on_reconcile_fix(self) -> None:
        row = self._selected_reconcile_row()
        if row is None:
            show_error(self, "Seçim Gerekli", "Düzeltmek için bir hesap seçin.")
            return
        if row["status"] != "drift":
            show_error(self, "Düzeltme Engellendi", "Yalnızca drift olan ledger hesaplar düzeltilebilir.")
            return
        dialog = MessageBox(
            "Bakiye Düzeltme",
            "Bu işlem current_balance değerini hareketlerden hesaplanan bakiye ile "
            "değiştirecek. Devam edilsin mi?",
            self.window(),
        )
        dialog.yesButton.setText("Düzelt")
        dialog.cancelButton.setText("İptal")
        if not dialog.exec_():
            return
        try:
            self._account_service.fix_account_balance_from_reconcile(int(row["account_id"]))
            show_success(self, "Başarılı", "Hesap bakiyesi reconcile değerine sabitlendi.")
            self._refresh_reconcile()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))
        except AppError as exc:
            show_error(self, "Hata", str(exc))

    def _refresh_audit(self) -> None:
        rows = self._audit_service.list_logs(self.audit_limit.value())
        table_rows = [
            [
                row["id"],
                row["created_at"],
                row["entity_type"],
                row["entity_id"],
                row["action"],
                f"{row['old_value_display']} → {row['new_value_display']}",
            ]
            for row in rows
        ]
        _fill_table(self.audit_table, table_rows)
