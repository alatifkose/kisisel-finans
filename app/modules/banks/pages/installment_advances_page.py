"""Taksitli Avanslar sayfası."""

from app.core.constants import PlanKind
from app.modules.banks.pages._debt_plans_page import DebtPlansPageBase


class InstallmentAdvancesPage(DebtPlansPageBase):
    def __init__(self, parent=None) -> None:
        super().__init__(
            page_title="Taksitli Avanslar",
            allowed_kinds=[PlanKind.KMH_INSTALLMENT, PlanKind.CASH_ADVANCE_INSTALLMENT],
            default_plan_kind=PlanKind.CASH_ADVANCE_INSTALLMENT,
            lock_plan_kind=False,
            show_kind_column=True,
            show_kind_filter=True,
            show_source_column=True,
            parent=parent,
        )
