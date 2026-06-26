"""Taksitli Alışveriş sayfası."""

from app.core.constants import PlanKind
from app.modules.banks.pages._debt_plans_page import DebtPlansPageBase


class InstallmentPurchasesPage(DebtPlansPageBase):
    def __init__(self, parent=None) -> None:
        super().__init__(
            page_title="Taksitli Alışveriş",
            allowed_kinds=[PlanKind.PURCHASE_INSTALLMENT],
            default_plan_kind=PlanKind.PURCHASE_INSTALLMENT,
            lock_plan_kind=True,
            show_kind_column=False,
            show_kind_filter=False,
            show_source_column=True,
            parent=parent,
        )
