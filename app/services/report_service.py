"""Rapor iş mantığı."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from app.core.constants import NATURE_LABELS, TrackingMode
from app.core.exceptions import ValidationError
from app.core.money import format_amount_with_grouping
from app.core.validators import is_non_empty_text
from app.repositories.report_repository import ReportRepository
from app.services.account_service import AccountService


class ReportService:
    """Finansal raporlar ve reconcile."""

    def __init__(
        self,
        report_repo: Optional[ReportRepository] = None,
        account_service: Optional[AccountService] = None,
    ) -> None:
        self._report_repo = report_repo or ReportRepository()
        self._account_service = account_service or AccountService()

    def get_cashflow_report(self, year: int, month: int) -> List[Dict[str, Any]]:
        self._validate_year_month(year, month)
        rows = self._report_repo.get_cashflow_by_month(year, month)
        return self._format_cashflow_rows(rows)

    def get_cashflow_report_by_range(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        self._validate_date_range(start_date, end_date)
        rows = self._report_repo.get_cashflow_by_date_range(start_date, end_date)
        return self._format_cashflow_rows(rows)

    def get_category_report(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        self._validate_date_range(start_date, end_date)
        rows = self._report_repo.get_category_report(start_date, end_date)
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            formatted.append(
                {
                    **row,
                    "nature_label": NATURE_LABELS.get(row["nature"], row["nature"]),
                    "total_amount_display": self.format_amount(
                        int(row["total_amount"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                }
            )
        return formatted

    def get_asset_report(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        self._validate_date_range(start_date, end_date)
        rows = self._report_repo.get_asset_report(start_date, end_date)
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            formatted.append(
                {
                    **row,
                    "nature_label": NATURE_LABELS.get(row["nature"], row["nature"]),
                    "total_amount_display": self.format_amount(
                        int(row["total_amount"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                }
            )
        return formatted

    def get_financing_expense_report(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        self._validate_date_range(start_date, end_date)
        rows = self._report_repo.get_financing_expense_report(start_date, end_date)
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            formatted.append(
                {
                    **row,
                    "total_amount_display": self.format_amount(
                        int(row["total_amount"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                }
            )
        return formatted

    def get_financing_expense_details(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        self._validate_date_range(start_date, end_date)
        rows = self._report_repo.get_financing_expense_details(start_date, end_date)
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            formatted.append(
                {
                    **row,
                    "amount_display": self.format_amount(
                        int(row["amount"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                }
            )
        return formatted

    def get_principal_payment_report(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        self._validate_date_range(start_date, end_date)
        rows = self._report_repo.get_principal_payment_report(start_date, end_date)
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            formatted.append(
                {
                    **row,
                    "total_principal_paid_display": self.format_amount(
                        int(row["total_principal_paid"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                }
            )
        return formatted

    def get_transfer_report(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        self._validate_date_range(start_date, end_date)
        rows = self._report_repo.get_transfer_report(start_date, end_date)
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            formatted.append(
                {
                    **row,
                    "from_amount_display": self.format_amount(
                        int(row["from_amount"]),
                        int(row["from_scale"]),
                        row["from_currency_code"],
                        row.get("from_currency_symbol") or "",
                    ),
                    "to_amount_display": self.format_amount(
                        int(row["to_amount"]),
                        int(row["to_scale"]),
                        row["to_currency_code"],
                        row.get("to_currency_symbol") or "",
                    ),
                }
            )
        return formatted

    def get_payment_calendar(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        self._validate_date_range(start_date, end_date)
        rows = self._report_repo.get_payment_calendar(start_date, end_date)
        return self._format_calendar_rows(rows)

    def get_overdue_payments(self, as_of_date: Optional[str] = None) -> List[Dict[str, Any]]:
        target = as_of_date or date.today().isoformat()
        rows = self._report_repo.get_overdue_payments(target)
        return self._format_calendar_rows(rows)

    def get_reconcile_report(self) -> List[Dict[str, Any]]:
        return self._account_service.reconcile_all_accounts()

    def format_amount(
        self,
        raw: int,
        scale: int,
        currency_code: str,
        currency_symbol: str = "",
    ) -> Dict[str, Any]:
        return {
            "raw": raw,
            "display": format_amount_with_grouping(raw, scale),
            "currency_code": currency_code,
            "currency_symbol": currency_symbol,
            "scale": scale,
        }

    def format_report_amounts(
        self,
        rows: List[Dict[str, Any]],
        amount_key: str,
    ) -> List[Dict[str, Any]]:
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            if amount_key not in row:
                formatted.append(row)
                continue
            raw = int(row[amount_key])
            scale = int(row["scale"])
            formatted.append(
                {
                    **row,
                    f"{amount_key}_display": self.format_amount(
                        raw,
                        scale,
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                }
            )
        return formatted

    def _format_cashflow_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            income = int(row["income_total"])
            expense = int(row["expense_total"])
            cost = int(row["cost_total"])
            net = income - expense - cost
            scale = int(row["scale"])
            code = row["currency_code"]
            symbol = row.get("currency_symbol") or ""
            formatted.append(
                {
                    **row,
                    "net_cashflow": net,
                    "income_total_display": self.format_amount(income, scale, code, symbol),
                    "expense_total_display": self.format_amount(expense, scale, code, symbol),
                    "cost_total_display": self.format_amount(cost, scale, code, symbol),
                    "net_cashflow_display": self.format_amount(net, scale, code, symbol),
                }
            )
        return formatted

    def _format_calendar_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            item_type = row["item_type"]
            type_label = "Taksit" if item_type == "installment" else "Kart Ekstresi"
            formatted.append(
                {
                    **row,
                    "type_label": type_label,
                    "amount_display": self.format_amount(
                        int(row["amount"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                }
            )
        return formatted

    @staticmethod
    def _validate_date_range(start_date: str, end_date: str) -> None:
        if not is_non_empty_text(start_date) or not is_non_empty_text(end_date):
            raise ValidationError("Başlangıç ve bitiş tarihi zorunludur.")
        if start_date > end_date:
            raise ValidationError("Başlangıç tarihi bitiş tarihinden büyük olamaz.")

    @staticmethod
    def _validate_year_month(year: int, month: int) -> None:
        if year < 1900 or year > 9999:
            raise ValidationError("Geçersiz yıl.")
        if month < 1 or month > 12:
            raise ValidationError("Geçersiz ay.")
