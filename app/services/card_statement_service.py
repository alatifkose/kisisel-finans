"""Türetilen kredi kartı ekstresi (Aşama 4).

Saklanmaz; kart hareketleri (card_entries) + karta bağlı taksitler
(debt_plans.source_card_id) kesim gününe göre dönemlere yerleştirilip
devir bakiyesiyle birlikte hesaplanır.

Dönem borcu = devir (önceki dönem kapanışı) + harcamalar − ödemeler.
(Enpara/Garanti/Bankkart ekstreleriyle doğrulanan formül.)
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any, Dict, List, Optional

from app.core.constants import (
    CARD_DEBT_DECREASING_ENTRY_TYPES,
    CARD_ENTRY_TYPE_LABELS,
    PLAN_KIND_LABELS,
)
from app.core.money import format_amount_with_grouping
from app.repositories.card_entry_repository import CardEntryRepository
from app.repositories.credit_card_repository import CreditCardRepository
from app.repositories.debt_plan_repository import DebtPlanRepository


def _parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _last_day(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _on_day(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, _last_day(year, month)))


def _next_month(year: int, month: int) -> tuple:
    return (year + 1, 1) if month == 12 else (year, month + 1)


class CardStatementService:
    """Kart hareketleri + taksitlerden dönemsel ekstreyi türetir."""

    DEFAULT_STATEMENT_DAY = 1

    def __init__(
        self,
        card_entry_repo: Optional[CardEntryRepository] = None,
        debt_plan_repo: Optional[DebtPlanRepository] = None,
        credit_card_repo: Optional[CreditCardRepository] = None,
    ) -> None:
        self._entry_repo = card_entry_repo or CardEntryRepository()
        self._debt_plan_repo = debt_plan_repo or DebtPlanRepository()
        self._credit_card_repo = credit_card_repo or CreditCardRepository()

    def get_statements(self, credit_card_id: int) -> List[Dict[str, Any]]:
        card = self._credit_card_repo.get_credit_card(credit_card_id)
        if card is None:
            return []
        scale = int(card["scale"])
        code = card["currency_code"]
        symbol = card.get("currency_symbol") or ""
        statement_day = (
            int(card["statement_day"]) if card.get("statement_day")
            else self.DEFAULT_STATEMENT_DAY
        )
        due_day = int(card["due_day"]) if card.get("due_day") else None

        items = self._collect_items(credit_card_id)
        if not items:
            return []

        for item in items:
            item["cut"] = self._period_cut(item["date"], statement_day)
        # Aynı dönemde önce harcamalar, sonra ödemeler; tarihe göre sıralı.
        items.sort(key=lambda x: (x["cut"], x["date"], 1 if x["is_payment"] else 0))

        periods: List[Dict[str, Any]] = []
        opening = 0
        for cut in sorted({item["cut"] for item in items}):
            period_items = [item for item in items if item["cut"] == cut]
            charges = sum(i["amount"] for i in period_items if not i["is_payment"])
            payments = sum(i["amount"] for i in period_items if i["is_payment"])
            closing = opening + charges - payments
            due = self._due_date(cut, due_day) if due_day else None
            periods.append({
                "cut_date": cut.isoformat(),
                "due_date": due.isoformat() if due else None,
                "opening_balance": opening,
                "charges": charges,
                "payments": payments,
                "period_debt": closing,
                "currency_code": code,
                "currency_symbol": symbol,
                "scale": scale,
                "opening_balance_display": format_amount_with_grouping(opening, scale),
                "charges_display": format_amount_with_grouping(charges, scale),
                "payments_display": format_amount_with_grouping(payments, scale),
                "period_debt_display": format_amount_with_grouping(closing, scale),
                "lines": [self._format_line(i, scale) for i in period_items],
            })
            opening = closing
        return periods

    def get_current_statement_debt(self, credit_card_id: int) -> int:
        """En güncel dönemin kapanış (dönem) borcu = kartın güncel toplam borcu."""
        periods = self.get_statements(credit_card_id)
        return int(periods[-1]["period_debt"]) if periods else 0

    def _collect_items(self, credit_card_id: int) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for entry in self._entry_repo.list_entries_by_card(credit_card_id):
            d = _parse_date(entry["txn_date"])
            if d is None:
                continue
            etype = entry["entry_type"]
            amount = int(entry["amount"])
            is_payment = etype in CARD_DEBT_DECREASING_ENTRY_TYPES
            items.append({
                "date": d,
                "kind": "entry",
                "type_label": CARD_ENTRY_TYPE_LABELS.get(etype, etype),
                "description": entry.get("description") or "",
                "category_name": entry.get("category_name"),
                "amount": amount,
                "signed": -amount if is_payment else amount,
                "is_payment": is_payment,
            })
        for ins in self._debt_plan_repo.get_installments_by_source_card(credit_card_id):
            d = _parse_date(ins["due_date"])
            if d is None:
                continue
            amount = int(ins["total_amount"])
            seq = int(ins["seq"])
            count = int(ins["installment_count"] or 0)
            label = PLAN_KIND_LABELS.get(ins["plan_kind"], ins["plan_kind"])
            desc = f"{ins['plan_name']} ({seq}/{count})" if count else ins["plan_name"]
            items.append({
                "date": d,
                "kind": "installment",
                "type_label": label,
                "description": desc,
                "category_name": None,
                "amount": amount,
                "signed": amount,
                "is_payment": False,
                "installment_seq": seq,
                "installment_status": ins["status"],
            })
        return items

    def _period_cut(self, d: date, statement_day: int) -> date:
        cut_this = _on_day(d.year, d.month, statement_day)
        if d <= cut_this:
            return cut_this
        y, m = _next_month(d.year, d.month)
        return _on_day(y, m, statement_day)

    def _due_date(self, cut: date, due_day: int) -> date:
        if due_day >= cut.day:
            return _on_day(cut.year, cut.month, due_day)
        y, m = _next_month(cut.year, cut.month)
        return _on_day(y, m, due_day)

    def _format_line(self, item: Dict[str, Any], scale: int) -> Dict[str, Any]:
        return {
            "date": item["date"].isoformat(),
            "kind": item["kind"],
            "type_label": item["type_label"],
            "description": item["description"],
            "category_name": item.get("category_name"),
            "amount": item["amount"],
            "signed": item["signed"],
            "is_payment": item["is_payment"],
            "amount_display": format_amount_with_grouping(item["amount"], scale),
            "signed_display": format_amount_with_grouping(item["signed"], scale),
        }
