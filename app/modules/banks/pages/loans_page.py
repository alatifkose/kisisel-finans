"""Krediler sayfası."""

from app.core.constants import PlanKind
from app.modules.banks.pages._debt_plans_page import DebtPlansPageBase


class LoansPage(DebtPlansPageBase):
    def __init__(self, parent=None) -> None:
        super().__init__(
            page_title="Krediler",
            allowed_kinds=[PlanKind.LOAN],
            default_plan_kind=PlanKind.LOAN,
            lock_plan_kind=True,
            show_kind_column=False,
            show_kind_filter=False,
            parent=parent,
        )
