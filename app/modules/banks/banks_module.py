"""Bankalar modülü — navigasyon kaydı ve sayfa yönetimi."""

from typing import List, Tuple, Type

from PyQt5.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, FluentWindow

from app.modules.banks.pages.accounts_page import AccountsPage
from app.modules.banks.pages.bank_summary_page import BankSummaryPage
from app.modules.banks.pages.credit_cards_page import CreditCardsPage
from app.modules.banks.pages.definitions_page import DefinitionsPage
from app.modules.banks.pages.installment_advances_page import InstallmentAdvancesPage
from app.modules.banks.pages.kmh_page import KmhPage
from app.modules.banks.pages.loans_page import LoansPage
from app.modules.banks.pages.reports_page import ReportsPage
from app.modules.banks.pages.transactions_page import TransactionsPage
from app.modules.banks.pages.transfers_page import TransfersPage
from app.ui.theme import apply_page_basics

BankNavItem = Tuple[str, Type[QWidget], FluentIcon, str]

BANK_SUMMARY_ROUTE = "bank_summary"

BANK_NAV_ITEMS: List[BankNavItem] = [
    (BANK_SUMMARY_ROUTE, BankSummaryPage, FluentIcon.HOME, "Banka Özeti"),
    ("accounts", AccountsPage, FluentIcon.FOLDER, "Hesaplar"),
    ("credit_cards", CreditCardsPage, FluentIcon.ALBUM, "Kredi Kartları"),
    ("kmh", KmhPage, FluentIcon.CONNECT, "KMH / Ek Hesap"),
    ("loans", LoansPage, FluentIcon.DOCUMENT, "Krediler"),
    ("installment_advances", InstallmentAdvancesPage, FluentIcon.CALENDAR, "Taksitli Avanslar"),
    ("transactions", TransactionsPage, FluentIcon.HISTORY, "Para Hareketleri"),
    ("transfers", TransfersPage, FluentIcon.SEND, "Transferler"),
    ("definitions", DefinitionsPage, FluentIcon.SETTING, "Tanımlar"),
    ("reports", ReportsPage, FluentIcon.PIE_SINGLE, "Raporlar"),
]


class BanksModule:
    """Bankalar alt modülünün sayfalarını ana pencereye kaydeder."""

    def __init__(self, window: FluentWindow) -> None:
        self._window = window
        self._pages: List[QWidget] = []

    def register(self) -> None:
        """Sol navigasyona Bankalar sayfalarını ekle."""
        for route_key, page_cls, icon, label in BANK_NAV_ITEMS:
            page = page_cls(self._window)
            page.setObjectName(route_key)
            apply_page_basics(page)
            self._window.addSubInterface(page, icon, label)
            self._pages.append(page)

    @property
    def pages(self) -> List[QWidget]:
        return self._pages

    @property
    def landing_page(self) -> QWidget:
        return self._pages[0] if self._pages else None
