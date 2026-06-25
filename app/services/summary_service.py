"""Banka özeti iş mantığı."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from app.core.money import format_amount_with_grouping
from app.repositories.credit_card_repository import CreditCardRepository
from app.repositories.debt_plan_repository import DebtPlanRepository
from app.repositories.kmh_repository import KmhRepository
from app.repositories.summary_repository import SummaryRepository


class SummaryService:
    """Banka özeti verilerini UI için hazırlar."""

    NOT_AVAILABLE_YET = {
        "credit_card_debt": False,
        "kmh_debt": False,
        "loan_debt": False,
        "debt_plans": False,
    }

    def __init__(
        self,
        summary_repo: Optional[SummaryRepository] = None,
        debt_plan_repo: Optional[DebtPlanRepository] = None,
        credit_card_repo: Optional[CreditCardRepository] = None,
        kmh_repo: Optional[KmhRepository] = None,
    ) -> None:
        self._summary_repo = summary_repo or SummaryRepository()
        self._debt_plan_repo = debt_plan_repo or DebtPlanRepository()
        self._credit_card_repo = credit_card_repo or CreditCardRepository()
        self._kmh_repo = kmh_repo or KmhRepository()

    def get_bank_summary(self) -> Dict[str, Any]:
        today = date.today()
        cash_balances = self.get_cash_balances()
        return {
            "cash_balances": cash_balances,
            "liquidity": self.get_available_liquidity(),
            "account_counts": self._summary_repo.get_account_counts(),
            "monthly_totals": self.get_monthly_totals(today.year, today.month),
            "recent_transactions": self.get_recent_transactions(),
            "accounts_snapshot": self._format_accounts_snapshot(
                self._summary_repo.get_accounts_snapshot()
            ),
            "debt_unpaid_totals": self.get_debt_unpaid_totals(),
            "upcoming_installments": self.get_upcoming_debt_installments(5),
            "credit_card_debts": self.get_credit_card_debts_by_currency(),
            "credit_card_min_payments": self.get_credit_card_min_payments_by_currency(),
            "credit_card_limits": self.get_total_card_limits_by_currency(),
            "kmh_debts": self.get_kmh_debts_by_currency(),
            "kmh_available_liquidity": self.get_kmh_available_liquidity_by_currency(),
            "kmh_snapshot": self.get_kmh_snapshot(),
            "upcoming_card_due_dates": self.get_upcoming_card_due_dates(5),
            "not_available_yet": dict(self.NOT_AVAILABLE_YET),
        }

    def get_cash_balances(self) -> List[Dict[str, Any]]:
        rows = self._summary_repo.get_cash_balances_by_currency()
        return [self._format_currency_amount_row(row, "total_balance") for row in rows]

    def get_available_liquidity(self) -> List[Dict[str, Any]]:
        """Nakit bakiye + KMH kullanılabilir limit (para birimi bazında)."""
        cash_by_currency: Dict[int, Dict[str, Any]] = {}
        for row in self.get_cash_balances():
            cash_by_currency[int(row["currency_id"])] = row

        kmh_by_currency: Dict[int, Dict[str, Any]] = {}
        for row in self.get_kmh_available_liquidity_by_currency():
            kmh_by_currency[int(row["currency_id"])] = row

        currency_ids = sorted(set(cash_by_currency) | set(kmh_by_currency))
        breakdown: List[Dict[str, Any]] = []
        for currency_id in currency_ids:
            cash_row = cash_by_currency.get(currency_id)
            kmh_row = kmh_by_currency.get(currency_id)

            if cash_row:
                currency_code = cash_row["currency_code"]
                currency_symbol = cash_row.get("currency_symbol") or ""
                scale = int(cash_row["scale"])
                cash_raw = int(cash_row["total_balance"]["raw"])
            elif kmh_row:
                currency_code = kmh_row["currency_code"]
                currency_symbol = kmh_row.get("currency_symbol") or ""
                scale = int(kmh_row["scale"])
                cash_raw = 0
            else:
                continue

            kmh_raw = int(kmh_row["available_total"]) if kmh_row else 0
            total_raw = cash_raw + kmh_raw

            breakdown.append(
                {
                    "currency_id": currency_id,
                    "currency_code": currency_code,
                    "currency_symbol": currency_symbol,
                    "scale": scale,
                    "cash_total": self.format_summary_amounts(
                        cash_raw, scale, currency_code, currency_symbol
                    ),
                    "kmh_available_total": self.format_summary_amounts(
                        kmh_raw, scale, currency_code, currency_symbol
                    ),
                    "total_liquidity": self.format_summary_amounts(
                        total_raw, scale, currency_code, currency_symbol
                    ),
                }
            )
        return breakdown

    def get_monthly_totals(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        today = date.today()
        target_year = year if year is not None else today.year
        target_month = month if month is not None else today.month
        rows = self._summary_repo.get_monthly_transaction_totals(target_year, target_month)
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            formatted.append(
                {
                    "currency_id": row["currency_id"],
                    "currency_code": row["currency_code"],
                    "currency_symbol": row.get("currency_symbol") or "",
                    "scale": int(row["scale"]),
                    "income_total": self.format_summary_amounts(
                        int(row["income_total"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                    "expense_total": self.format_summary_amounts(
                        int(row["expense_total"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                    "cost_total": self.format_summary_amounts(
                        int(row["cost_total"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                }
            )
        return formatted

    def get_kmh_debts_by_currency(self) -> List[Dict[str, Any]]:
        rows = self._kmh_repo.get_kmh_debts_by_currency()
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            if int(row.get("used_total") or 0) == 0:
                continue
            formatted.append(
                {
                    **row,
                    "used_total_display": self.format_summary_amounts(
                        int(row["used_total"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                }
            )
        return formatted

    def get_kmh_available_liquidity_by_currency(self) -> List[Dict[str, Any]]:
        rows = self._kmh_repo.get_kmh_available_liquidity_by_currency()
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            if int(row.get("available_total") or 0) == 0:
                continue
            formatted.append(
                {
                    **row,
                    "available_total_display": self.format_summary_amounts(
                        int(row["available_total"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                }
            )
        return formatted

    def get_kmh_snapshot(self) -> List[Dict[str, Any]]:
        rows = self._kmh_repo.get_kmh_snapshot()
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            scale = int(row["scale"])
            code = row["currency_code"]
            symbol = row.get("currency_symbol") or ""
            formatted.append(
                {
                    **row,
                    "kmh_limit_display": self.format_summary_amounts(
                        int(row["kmh_limit"]), scale, code, symbol
                    ),
                    "used_amount_display": self.format_summary_amounts(
                        int(row["used_amount"]), scale, code, symbol
                    ),
                    "available_amount_display": self.format_summary_amounts(
                        int(row["available_amount"]), scale, code, symbol
                    ),
                }
            )
        return formatted

    def get_credit_card_debts_by_currency(self) -> List[Dict[str, Any]]:
        rows = self._credit_card_repo.get_credit_card_debts_by_currency()
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            if int(row.get("statement_debt_total") or 0) == 0:
                continue
            formatted.append(
                {
                    **row,
                    "statement_debt_total_display": self.format_summary_amounts(
                        int(row["statement_debt_total"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                }
            )
        return formatted

    def get_credit_card_min_payments_by_currency(self) -> List[Dict[str, Any]]:
        rows = self._credit_card_repo.get_credit_card_debts_by_currency()
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            if int(row.get("min_payment_total") or 0) == 0:
                continue
            formatted.append(
                {
                    **row,
                    "min_payment_total_display": self.format_summary_amounts(
                        int(row["min_payment_total"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                }
            )
        return formatted

    def get_total_card_limits_by_currency(self) -> List[Dict[str, Any]]:
        rows = self._credit_card_repo.get_total_card_limits_by_currency()
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            formatted.append(
                {
                    **row,
                    "total_limit_display": self.format_summary_amounts(
                        int(row["total_limit"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                }
            )
        return formatted

    def get_upcoming_card_due_dates(self, limit: int = 5) -> List[Dict[str, Any]]:
        rows = self._credit_card_repo.get_upcoming_card_due_dates(limit)
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            formatted.append(
                {
                    **row,
                    "min_payment_display": self.format_summary_amounts(
                        int(row["min_payment"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                }
            )
        return formatted

    def get_try_net_display(self, summary: Dict[str, Any]) -> str:
        """TRY nakit eksi TRY kredi kartı borcu eksi TRY KMH kullanılan eksi TRY plan borcu."""
        try_cash_raw = 0
        for row in summary.get("cash_balances") or []:
            if row["currency_code"] == "TRY":
                try_cash_raw = int(row["total_balance"]["raw"])
                break

        card_debt_raw = 0
        for row in summary.get("credit_card_debts") or []:
            if row["currency_code"] == "TRY":
                card_debt_raw = int(row["statement_debt_total"])
                break

        kmh_debt_raw = 0
        for row in summary.get("kmh_debts") or []:
            if row["currency_code"] == "TRY":
                kmh_debt_raw = int(row["used_total"])
                break

        plan_debt_raw = 0
        for row in summary.get("debt_unpaid_totals") or []:
            if row["currency_code"] == "TRY":
                plan_debt_raw = int(row["unpaid_total"])
                break

        if try_cash_raw == 0 and card_debt_raw == 0 and kmh_debt_raw == 0 and plan_debt_raw == 0:
            return "TRY net: —"

        net_raw = try_cash_raw - card_debt_raw - kmh_debt_raw - plan_debt_raw
        scale = 2
        symbol = "₺"
        for row in summary.get("cash_balances") or []:
            if row["currency_code"] == "TRY":
                scale = int(row["total_balance"]["scale"])
                symbol = row["total_balance"].get("currency_symbol") or "₺"
                break

        net_display = self.format_summary_amounts(net_raw, scale, "TRY", symbol)
        return (
            f"TRY net: {net_display['display']} {symbol}".strip()
            + "\n(Nakit − KK borcu − KMH kullanılan − plan borcu)"
        )

    def get_recent_transactions(self, limit: int = 10) -> List[Dict[str, Any]]:
        rows = self._summary_repo.get_recent_transactions(limit)
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            amount = self.format_summary_amounts(
                int(row["total_amount"]),
                int(row["scale"]),
                row["currency_code"],
                row.get("currency_symbol") or "",
            )
            formatted.append({**row, "amount": amount})
        return formatted

    def get_debt_unpaid_totals(self) -> List[Dict[str, Any]]:
        rows = self._debt_plan_repo.get_unpaid_totals_by_currency()
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            formatted.append(
                {
                    **row,
                    "unpaid_total_display": self.format_summary_amounts(
                        int(row["unpaid_total"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                }
            )
        return formatted

    def get_upcoming_debt_installments(self, limit: int = 5) -> List[Dict[str, Any]]:
        rows = self._debt_plan_repo.get_upcoming_installments(limit)
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            formatted.append(
                {
                    **row,
                    "total_amount_display": self.format_summary_amounts(
                        int(row["total_amount"]),
                        int(row["scale"]),
                        row["currency_code"],
                        row.get("currency_symbol") or "",
                    ),
                }
            )
        return formatted

    def format_summary_amounts(
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

    def format_currency_lines(self, rows: List[Dict[str, Any]], amount_key: str) -> str:
        """Para birimi bazlı satırları tek metin bloğuna çevirir."""
        if not rows:
            return "—"
        lines: List[str] = []
        for row in rows:
            amount = row.get(amount_key, {})
            if isinstance(amount, dict):
                display = amount.get("display", "0")
                symbol = amount.get("currency_symbol") or amount.get("currency_code", "")
            else:
                display = self.format_summary_amounts(
                    int(row.get(amount_key, 0)),
                    int(row["scale"]),
                    row["currency_code"],
                    row.get("currency_symbol") or "",
                )["display"]
                symbol = row.get("currency_symbol") or row["currency_code"]
            suffix = f" {symbol}".rstrip()
            lines.append(f"{row['currency_code']}: {display}{suffix}")
        return "\n".join(lines)

    def get_try_cash_display(self, cash_balances: List[Dict[str, Any]]) -> Optional[str]:
        for row in cash_balances:
            if row["currency_code"] == "TRY":
                amount = row["total_balance"]
                symbol = amount.get("currency_symbol") or "₺"
                return f"{amount['display']} {symbol}".strip()
        return None

    def _format_currency_amount_row(
        self,
        row: Dict[str, Any],
        amount_key: str,
    ) -> Dict[str, Any]:
        return {
            "currency_id": row["currency_id"],
            "currency_code": row["currency_code"],
            "currency_symbol": row.get("currency_symbol") or "",
            "scale": int(row["scale"]),
            amount_key: self.format_summary_amounts(
                int(row[amount_key]),
                int(row["scale"]),
                row["currency_code"],
                row.get("currency_symbol") or "",
            ),
            "account_count": int(row.get("account_count", 0)),
        }

    def _format_accounts_snapshot(
        self,
        rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        formatted: List[Dict[str, Any]] = []
        for row in rows:
            balance = self.format_summary_amounts(
                int(row["current_balance"]),
                int(row["scale"]),
                row["currency_code"],
                row.get("currency_symbol") or "",
            )
            formatted.append({**row, "current_balance_display": balance})
        return formatted
