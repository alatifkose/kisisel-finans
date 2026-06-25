"""Uygulama genelinde kullanılan sabit değerler."""

APP_NAME = "Kişisel Finans ve Muhasebe"
APP_VERSION = "0.1.0"

# Üst seviye modüller
MODULE_FINANS = "finans"
MODULE_MUHASEBE = "muhasebe"
MODULE_TRADE = "trade"
MODULE_BILIM = "bilim"

ACTIVE_MODULES = {MODULE_FINANS}

MODULE_LABELS = {
    MODULE_FINANS: "Finans",
    MODULE_MUHASEBE: "Muhasebe",
    MODULE_TRADE: "Trade",
    MODULE_BILIM: "Bilim",
}

INACTIVE_MODULE_MESSAGE = "Bu modül henüz aktif değil."
COMING_SOON_MESSAGE = "Bu özellik sonraki aşamada eklenecek."


class Nature:
    INCOME = "income"
    EXPENSE = "expense"
    COST = "cost"
    PRINCIPAL = "principal"
    TRANSFER = "transfer"


class PlanKind:
    LOAN = "loan"
    KMH_INSTALLMENT = "kmh_installment"
    CASH_ADVANCE_INSTALLMENT = "ca_installment"


class InstallmentStatus:
    PLANNED = "planned"
    PARTIAL = "partial"
    PAID = "paid"


class Direction:
    IN = "in"
    OUT = "out"


class TrackingMode:
    LEDGER = "ledger"
    SNAPSHOT = "snapshot"


NATURE_LABELS = {
    Nature.INCOME: "Gelir",
    Nature.EXPENSE: "Gider",
    Nature.COST: "Masraf",
    Nature.PRINCIPAL: "Anapara",
    Nature.TRANSFER: "Transfer",
}

VALID_CATEGORY_NATURES = [
    Nature.INCOME,
    Nature.EXPENSE,
    Nature.COST,
]

VALID_COMPONENT_NATURES = [
    Nature.PRINCIPAL,
    Nature.EXPENSE,
]

VALID_MANUAL_TRANSACTION_NATURES = [
    Nature.INCOME,
    Nature.EXPENSE,
    Nature.COST,
]

DIRECTION_LABELS = {
    Direction.IN: "Giriş",
    Direction.OUT: "Çıkış",
}

SOURCE_MANUAL = "manual"
SOURCE_INSTALLMENT = "installment"
SOURCE_TRANSFER = "transfer"

SOURCE_LABELS = {
    SOURCE_MANUAL: "Manuel",
    SOURCE_INSTALLMENT: "Taksit Ödemesi",
    SOURCE_TRANSFER: "Transfer",
}

PLAN_KIND_LABELS = {
    PlanKind.LOAN: "Kredi",
    PlanKind.KMH_INSTALLMENT: "Taksitli KMH / Ek Hesap",
    PlanKind.CASH_ADVANCE_INSTALLMENT: "Taksitli Nakit Avans",
}

INSTALLMENT_STATUS_LABELS = {
    InstallmentStatus.PLANNED: "Planlandı",
    InstallmentStatus.PARTIAL: "Kısmi Ödendi",
    InstallmentStatus.PAID: "Ödendi",
}

VALID_PLAN_KINDS = [
    PlanKind.LOAN,
    PlanKind.KMH_INSTALLMENT,
    PlanKind.CASH_ADVANCE_INSTALLMENT,
]
