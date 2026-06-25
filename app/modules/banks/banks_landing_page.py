"""Bankalar modülü giriş / özet sayfası."""

from __future__ import annotations

from typing import Dict, List

from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
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

from app.core.constants import COMING_SOON_MESSAGE
from app.core.exceptions import AppError, ValidationError
from app.modules.banks.dialogs.bank_account_dialogs import AccountDialog
from app.modules.banks.pages._ui_helpers import show_error, show_info, show_success, switch_to_route
from app.modules.banks.widgets.bank_management import BankManagementSection
from app.services.account_service import AccountService
from app.services.bank_service import BankService
from app.services.reference_service import ReferenceService
from app.services.summary_service import SummaryService


class _SummaryCard(CardWidget):
    """Özet kartı — çok satırlı değer destekler."""

    def __init__(self, title: str, value: str = "—", note: str = "", parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        layout.addWidget(CaptionLabel(title, self))
        self.value_label = StrongBodyLabel(value, self)
        self.value_label.setWordWrap(True)
        layout.addWidget(self.value_label)
        self.note_label: CaptionLabel | None = None
        if note:
            self.note_label = CaptionLabel(note, self)
            self.note_label.setWordWrap(True)
            layout.addWidget(self.note_label)


class BanksLandingPage(QWidget):
    """Bankalar giriş sayfası — özet kartları ve banka yönetimi."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._summary_service = SummaryService()
        self._bank_service = BankService()
        self._account_service = AccountService()
        self._reference_service = ReferenceService()
        self._summary_cards: Dict[str, _SummaryCard] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 24, 36, 24)
        root.setSpacing(24)

        header = QVBoxLayout()
        header.setSpacing(8)
        header.addWidget(TitleLabel("Finansal omurgayı buradan kuracağız", self))
        subtitle = BodyLabel(
            "Banka hesapları, kredi kartları, KMH, krediler, taksitli avanslar "
            "ve para hareketleri bu modülde yönetilecek.",
            self,
        )
        subtitle.setWordWrap(True)
        header.addWidget(subtitle)
        root.addLayout(header)

        cards_layout = QGridLayout()
        cards_layout.setSpacing(16)
        for index, (key, title) in enumerate(
            (
                ("cash", "Toplam Nakit"),
                ("debt", "Toplam Borç"),
                ("liquidity", "Kullanılabilir Likidite"),
                ("net", "Net Durum"),
            )
        ):
            card = _SummaryCard(title, parent=self)
            self._summary_cards[key] = card
            cards_layout.addWidget(card, index // 2, index % 2)
        root.addLayout(cards_layout)

        actions_label = SubtitleLabel("Hızlı Erişim", self)
        root.addWidget(actions_label)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)
        for label, handler, is_primary in (
            ("Banka Ekle", self._open_add_bank_via_section, True),
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

    def refresh(self) -> None:
        summary = self._summary_service.get_bank_summary()
        cash_lines = self._format_balance_lines(summary["cash_balances"])
        self._summary_cards["cash"].value_label.setText(cash_lines or "—")
        self._summary_cards["liquidity"].value_label.setText(
            self._format_liquidity_lines(summary.get("liquidity") or []) or "—"
        )

        debt_parts: List[str] = []
        card_debts = summary.get("credit_card_debts") or []
        if card_debts:
            debt_parts.append("KK Borcu:")
            for row in card_debts:
                amount = row["statement_debt_total_display"]
                symbol = amount.get("currency_symbol") or ""
                suffix = f" {symbol}".rstrip()
                debt_parts.append(f"{row['currency_code']}: {amount['display']}{suffix}")
        kmh_debts = summary.get("kmh_debts") or []
        if kmh_debts:
            debt_parts.append("KMH Kullanılan:")
            for row in kmh_debts:
                amount = row["used_total_display"]
                symbol = amount.get("currency_symbol") or ""
                suffix = f" {symbol}".rstrip()
                debt_parts.append(f"{row['currency_code']}: {amount['display']}{suffix}")
        plan_lines = self._format_debt_lines(summary.get("debt_unpaid_totals") or [])
        if plan_lines:
            debt_parts.append("Plan Borcu:")
            debt_parts.append(plan_lines)
        self._summary_cards["debt"].value_label.setText(
            "\n".join(debt_parts) if debt_parts else "—"
        )
        try_cash = self._summary_service.get_try_cash_display(summary["cash_balances"])
        self._summary_cards["net"].value_label.setText(
            self._summary_service.get_try_net_display(summary)
            if summary.get("credit_card_debts")
            or summary.get("kmh_debts")
            or summary.get("debt_unpaid_totals")
            else (try_cash or "TRY nakit: —")
        )
        self._bank_management.refresh()

    @staticmethod
    def _format_debt_lines(rows) -> str:
        if not rows:
            return ""
        lines = []
        for row in rows:
            amount = row["unpaid_total_display"]
            symbol = amount.get("currency_symbol") or ""
            suffix = f" {symbol}".rstrip()
            lines.append(f"{row['currency_code']}: {amount['display']}{suffix}")
        return "\n".join(lines)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()

    @staticmethod
    def _format_balance_lines(rows) -> str:
        if not rows:
            return ""
        lines = []
        for row in rows:
            amount = row["total_balance"]
            symbol = amount.get("currency_symbol") or ""
            suffix = f" {symbol}".rstrip()
            lines.append(f"{row['currency_code']}: {amount['display']}{suffix}")
        return "\n".join(lines)

    @staticmethod
    def _format_liquidity_lines(rows) -> str:
        if not rows:
            return ""
        lines = []
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

    def _open_add_bank_via_section(self) -> None:
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
