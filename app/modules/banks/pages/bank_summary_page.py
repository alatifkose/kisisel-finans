"""Banka Özeti sayfası."""

from __future__ import annotations

from typing import Any, Dict, List

from PyQt5.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    SubtitleLabel,
    TitleLabel,
)

from app.core.constants import COMING_SOON_MESSAGE, DIRECTION_LABELS, SOURCE_LABELS, SOURCE_MANUAL
from app.core.event_bus import event_bus
from app.core.exceptions import AppError, ValidationError
from app.modules.banks.dialogs.bank_account_dialogs import AccountDialog
from app.modules.banks.pages._ui_helpers import (
    active_label,
    show_error,
    show_info,
    show_success,
    switch_to_route,
)
from app.modules.banks.widgets.bank_management import BankManagementSection
from app.services.account_service import AccountService
from app.services.bank_service import BankService
from app.services.reference_service import ReferenceService
from app.services.summary_service import SummaryService


class _SummaryCard(CardWidget):
    def __init__(
        self,
        title: str,
        value: str = "—",
        note: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        layout.addWidget(CaptionLabel(title, self))
        self.value_label = StrongBodyLabel(value, self)
        self.value_label.setWordWrap(True)
        layout.addWidget(self.value_label)
        if note:
            note_label = CaptionLabel(note, self)
            note_label.setWordWrap(True)
            layout.addWidget(note_label)


class BankSummaryPage(QWidget):
    """Bankalar modülü özet sayfası."""

    _LIQUIDITY_NOTE = (
        "Nakit hesap bakiyeleri ve KMH kullanılabilir limit (counts_as_liquidity=1). "
        "Kredi kartı alışveriş limiti likiditeye dahil edilmez."
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._summary_service = SummaryService()
        self._bank_service = BankService()
        self._account_service = AccountService()
        self._reference_service = ReferenceService()
        self._summary_cards: Dict[str, _SummaryCard] = {}
        self._build_ui()
        self.refresh()
        event_bus.subscribe("account_balance_changed", self._on_data_changed)
        event_bus.subscribe("transaction_created", self._on_data_changed)
        event_bus.subscribe("transaction_updated", self._on_data_changed)
        event_bus.subscribe("transaction_deleted", self._on_data_changed)
        event_bus.subscribe("installment_paid", self._on_data_changed)
        event_bus.subscribe("installment_unpaid", self._on_data_changed)
        event_bus.subscribe("transfer_created", self._on_data_changed)
        event_bus.subscribe("transfer_deleted", self._on_data_changed)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(36, 24, 36, 24)
        root.setSpacing(20)

        header_row = QHBoxLayout()
        header_row.addWidget(TitleLabel("Banka Özeti", self))
        header_row.addStretch()
        self.refresh_button = PushButton("Yenile", self)
        self.refresh_button.clicked.connect(self.refresh)
        header_row.addWidget(self.refresh_button)
        root.addLayout(header_row)

        cards_layout = QGridLayout()
        cards_layout.setSpacing(16)
        card_defs = [
            ("cash", "Toplam Nakit", "—", ""),
            ("liquidity", "Kullanılabilir Likidite", "—", self._LIQUIDITY_NOTE),
            ("accounts", "Aktif Hesap Sayısı", "—", ""),
            ("monthly", "Bu Ay Nakit Akışı", "—", ""),
            ("debt", "Borç Durumu", "—", ""),
            ("net", "Net Finansal Durum", "—", ""),
        ]
        for index, (key, title, value, note) in enumerate(card_defs):
            card = _SummaryCard(title, value, note, parent=self)
            self._summary_cards[key] = card
            cards_layout.addWidget(card, index // 2, index % 2)
        root.addLayout(cards_layout)

        root.addWidget(SubtitleLabel("KMH / Ek Hesap Özeti", self))
        self.kmh_table = QTableWidget(self)
        self.kmh_table.setColumnCount(7)
        self.kmh_table.setHorizontalHeaderLabels(
            ["Banka", "Hesap", "KMH", "Limit", "Kullanılan", "Kullanılabilir", "Aktif"]
        )
        self.kmh_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.kmh_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.kmh_table.verticalHeader().setVisible(False)
        root.addWidget(self.kmh_table)

        root.addWidget(SubtitleLabel("Hesap Bakiyeleri", self))
        self.accounts_table = QTableWidget(self)
        self.accounts_table.setColumnCount(6)
        self.accounts_table.setHorizontalHeaderLabels(
            ["Banka", "Hesap", "Para Birimi", "Güncel Bakiye", "Takip Modu", "Aktif"]
        )
        self.accounts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.accounts_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.accounts_table.verticalHeader().setVisible(False)
        root.addWidget(self.accounts_table)

        root.addWidget(SubtitleLabel("Son İşlemler", self))
        self.transactions_table = QTableWidget(self)
        self.transactions_table.setColumnCount(7)
        self.transactions_table.setHorizontalHeaderLabels(
            ["Tarih", "Banka", "Hesap", "Yön", "Tutar", "Açıklama", "Kaynak"]
        )
        self.transactions_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.transactions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.transactions_table.verticalHeader().setVisible(False)
        root.addWidget(self.transactions_table)

        root.addWidget(SubtitleLabel("Hızlı Erişim", self))
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)
        for label, handler, is_primary in (
            ("Banka Ekle", self._open_add_bank_dialog, True),
            ("Hesap Ekle", self._open_add_account_dialog, False),
            ("Hareket Ekle", self._go_to_transactions, False),
            ("Tüm Hesaplar", self._go_to_accounts_page, False),
        ):
            button = PrimaryPushButton(label, self) if is_primary else PushButton(label, self)
            button.clicked.connect(handler)
            actions_layout.addWidget(button)
        actions_layout.addStretch()
        root.addLayout(actions_layout)

        self._bank_management = BankManagementSection(self)
        root.addWidget(self._bank_management)

    def _on_data_changed(self, _data=None) -> None:
        self.refresh()

    def refresh(self) -> None:
        summary = self._summary_service.get_bank_summary()
        self._update_summary_cards(summary)
        self._populate_kmh_table(summary.get("kmh_snapshot") or [])
        self._populate_accounts_table(summary["accounts_snapshot"])
        self._populate_transactions_table(summary["recent_transactions"])
        self._bank_management.refresh()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()

    def _update_summary_cards(self, summary: Dict[str, Any]) -> None:
        cash_lines = self._format_balance_lines(summary["cash_balances"], "total_balance")
        self._summary_cards["cash"].value_label.setText(cash_lines or "—")
        self._summary_cards["liquidity"].value_label.setText(
            self._format_liquidity_lines(summary.get("liquidity") or []) or "—"
        )

        counts = summary["account_counts"]
        self._summary_cards["accounts"].value_label.setText(
            f"Banka: {counts['active_bank_count']}\n"
            f"Hesap: {counts['active_account_count']}\n"
            f"Ledger: {counts['ledger_account_count']} | "
            f"Snapshot: {counts['snapshot_account_count']}"
        )

        monthly_lines = self._format_monthly_lines(summary["monthly_totals"])
        self._summary_cards["monthly"].value_label.setText(monthly_lines or "—")

        self._summary_cards["debt"].value_label.setText(
            self._format_debt_card(summary)
        )

        try_cash = self._summary_service.get_try_cash_display(summary["cash_balances"])
        net_text = self._summary_service.get_try_net_display(summary)
        if try_cash:
            net_text = f"{try_cash}\n{net_text}"
        self._summary_cards["net"].value_label.setText(net_text)

    @staticmethod
    def _format_debt_card(summary: Dict[str, Any]) -> str:
        lines: List[str] = []

        card_debts = summary.get("credit_card_debts") or []
        if card_debts:
            lines.append("Kredi Kartı Borcu:")
            for row in card_debts:
                amount = row["statement_debt_total_display"]
                symbol = amount.get("currency_symbol") or ""
                suffix = f" {symbol}".rstrip()
                lines.append(f"- {row['currency_code']}: {amount['display']}{suffix}")
        else:
            lines.append("Kredi Kartı Borcu: —")

        kmh_debts = summary.get("kmh_debts") or []
        if kmh_debts:
            lines.append("KMH Kullanılan:")
            for row in kmh_debts:
                amount = row["used_total_display"]
                symbol = amount.get("currency_symbol") or ""
                suffix = f" {symbol}".rstrip()
                lines.append(f"- {row['currency_code']}: {amount['display']}{suffix}")
        else:
            lines.append("KMH Kullanılan: —")

        min_payments = summary.get("credit_card_min_payments") or []
        if min_payments:
            lines.append("Asgari Ödeme:")
            for row in min_payments:
                amount = row["min_payment_total_display"]
                symbol = amount.get("currency_symbol") or ""
                suffix = f" {symbol}".rstrip()
                lines.append(f"- {row['currency_code']}: {amount['display']}{suffix}")

        card_limits = summary.get("credit_card_limits") or []
        if card_limits:
            lines.append("Kart Limitleri (likidite değil):")
            for row in card_limits:
                amount = row["total_limit_display"]
                symbol = amount.get("currency_symbol") or ""
                suffix = f" {symbol}".rstrip()
                lines.append(f"- {row['currency_code']}: {amount['display']}{suffix}")

        unpaid = summary.get("debt_unpaid_totals") or []
        if unpaid:
            lines.append("Borç Planları:")
            for row in unpaid:
                amount = row["unpaid_total_display"]
                symbol = amount.get("currency_symbol") or ""
                suffix = f" {symbol}".rstrip()
                lines.append(
                    f"- {row['currency_code']}: {amount['display']}{suffix} ödenmemiş"
                )
        else:
            lines.append("Borç Planları: —")

        upcoming_items: List[str] = []
        for item in summary.get("upcoming_installments") or []:
            amount = item["total_amount_display"]
            symbol = amount.get("currency_symbol") or ""
            suffix = f" {symbol}".rstrip()
            upcoming_items.append(
                f"- {item['due_date']} — {item['plan_name']} — {amount['display']}{suffix}"
            )
        for item in summary.get("upcoming_card_due_dates") or []:
            amount = item["min_payment_display"]
            symbol = amount.get("currency_symbol") or ""
            suffix = f" {symbol}".rstrip()
            label = f"{item['bank_name']} / {item['card_name']}"
            upcoming_items.append(
                f"- {item['due_date']} — {label} (asgari) — {amount['display']}{suffix}"
            )
        if upcoming_items:
            lines.append("Yaklaşan Ödemeler:")
            lines.extend(upcoming_items[:8])
        return "\n".join(lines)

    @staticmethod
    def _format_liquidity_lines(rows: List[Dict[str, Any]]) -> str:
        if not rows:
            return ""
        lines: List[str] = []
        for row in rows:
            code = row["currency_code"]
            cash = row["cash_total"]
            kmh = row["kmh_available_total"]
            total = row["total_liquidity"]
            cash_suffix = f" {cash.get('currency_symbol', '')}".rstrip()
            kmh_suffix = f" {kmh.get('currency_symbol', '')}".rstrip()
            total_suffix = f" {total.get('currency_symbol', '')}".rstrip()
            lines.append(f"{code} Nakit: {cash['display']}{cash_suffix}")
            if int(kmh.get("raw", 0)) != 0:
                lines.append(f"{code} KMH: {kmh['display']}{kmh_suffix}")
            lines.append(f"{code} Toplam: {total['display']}{total_suffix}")
        return "\n".join(lines)

    @staticmethod
    def _format_balance_lines(rows: List[Dict[str, Any]], amount_key: str) -> str:
        if not rows:
            return ""
        lines: List[str] = []
        for row in rows:
            amount = row[amount_key]
            symbol = amount.get("currency_symbol") or ""
            suffix = f" {symbol}".rstrip()
            lines.append(f"{row['currency_code']}: {amount['display']}{suffix}")
        return "\n".join(lines)

    @staticmethod
    def _format_monthly_lines(rows: List[Dict[str, Any]]) -> str:
        if not rows:
            return ""
        lines: List[str] = []
        for row in rows:
            code = row["currency_code"]
            income = row["income_total"]["display"]
            expense = row["expense_total"]["display"]
            cost = row["cost_total"]["display"]
            lines.append(
                f"{code} — Gelir: {income} | Gider: {expense} | Masraf: {cost}"
            )
        return "\n".join(lines)

    def _populate_kmh_table(self, rows: List[Dict[str, Any]]) -> None:
        self.kmh_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.get("bank_name") or "",
                row.get("account_name") or "",
                row.get("name") or "",
                row["kmh_limit_display"]["display"],
                row["used_amount_display"]["display"],
                row["available_amount_display"]["display"],
                active_label(row.get("is_active", True)),
            ]
            for col_index, value in enumerate(values):
                self.kmh_table.setItem(
                    row_index, col_index, QTableWidgetItem(str(value))
                )

    def _populate_accounts_table(self, rows: List[Dict[str, Any]]) -> None:
        self.accounts_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            balance = row["current_balance_display"]
            values = [
                row["bank_name"],
                row["account_name"],
                row["currency_code"],
                f"{balance['display']} {balance.get('currency_symbol', '')}".strip(),
                row["tracking_mode"],
                active_label(row["is_active"]),
            ]
            for col_index, value in enumerate(values):
                self.accounts_table.setItem(
                    row_index, col_index, QTableWidgetItem(str(value))
                )

    def _populate_transactions_table(self, rows: List[Dict[str, Any]]) -> None:
        self.transactions_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            amount = row["amount"]
            values = [
                row["txn_date"],
                row["bank_name"],
                row["account_name"],
                DIRECTION_LABELS.get(row["direction"], row["direction"]),
                f"{amount['display']} {amount.get('currency_symbol', '')}".strip(),
                row.get("description") or "",
                SOURCE_LABELS.get(row.get("source_type") or SOURCE_MANUAL, row.get("source_type") or SOURCE_MANUAL),
            ]
            for col_index, value in enumerate(values):
                self.transactions_table.setItem(
                    row_index, col_index, QTableWidgetItem(str(value))
                )

    def _open_add_bank_dialog(self) -> None:
        self._bank_management._open_add_bank_dialog()

    def _open_add_account_dialog(self) -> None:
        banks = self._bank_service.list_banks()
        if not banks:
            show_error(self, "Banka Gerekli", "Önce en az bir banka eklemelisiniz.")
            return
        currencies = self._reference_service.list_currencies()
        if not currencies:
            show_error(self, "Para Birimi Gerekli", "Önce en az bir para birimi tanımlayın.")
            return
        dialog = AccountDialog(banks, currencies, self.window())
        if not dialog.exec_():
            return
        values = dialog.get_values()
        try:
            self._account_service.create_account(
                values["bank_id"],
                values["name"],
                values["currency_id"],
                values["opening_balance_text"],
                values["note"],
                values["tracking_mode"],
            )
            show_success(self, "Başarılı", "Hesap eklendi.")
            self.refresh()
        except ValidationError as exc:
            show_error(self, "Doğrulama Hatası", str(exc))
        except AppError as exc:
            show_error(self, "Hata", str(exc))

    def _go_to_transactions(self) -> None:
        if not switch_to_route(self, "transactions"):
            show_info(self, "Hareket Ekle", COMING_SOON_MESSAGE)

    def _go_to_accounts_page(self) -> None:
        if not switch_to_route(self, "accounts"):
            show_info(self, "Hesaplar", "Hesaplar sayfasına geçilemedi.")
