"""Ana uygulama penceresi."""

from qfluentwidgets import FluentWindow

from app.core.constants import APP_NAME, MODULE_FINANS
from app.modules.banks.banks_module import BANK_SUMMARY_ROUTE, BanksModule
from app.ui.home_page import HomePage
from app.ui.navigation import TopModuleBar


class MainWindow(FluentWindow):
    """qfluentwidgets tabanlı ana pencere."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)

        # Sol üstteki hamburger (daralt/genişlet) butonu gereksiz; sidebar
        # her zaman açık kalsın.
        self.navigationInterface.setMenuButtonVisible(False)
        self.navigationInterface.setCollapsible(False)

        self._home_page = HomePage(self)
        self.stackedWidget.addWidget(self._home_page)

        self._banks_module = BanksModule(self)
        self._banks_module.register()

        self._ensure_stacked_navigation_sync()
        self._module_bar = TopModuleBar(self.show_banks, self)
        self.titleBar.hBoxLayout.insertWidget(0, self._module_bar, 0)

        self.show_home()

    def _ensure_stacked_navigation_sync(self) -> None:
        """Home sayfası nav dışında eklendiği için stackedWidget senkronunu kur."""
        if getattr(self, "_stacked_nav_synced", False):
            return
        self.stackedWidget.currentChanged.connect(self._on_stacked_page_changed)
        self._stacked_nav_synced = True

    def _on_stacked_page_changed(self, index: int) -> None:
        widget = self.stackedWidget.widget(index)
        if widget is None or widget.objectName() == "home":
            return
        if self.navigationInterface.isVisible():
            self.navigationInterface.setCurrentItem(widget.objectName())
        self._updateStackedBackground()

    def _sync_title_bar_layout(self) -> None:
        nav_offset = 46 if self.navigationInterface.isVisible() else 0
        self.titleBar.move(nav_offset, 0)
        self.titleBar.resize(self.width() - nav_offset, self.titleBar.height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_title_bar_layout()

    def show_home(self) -> None:
        """Ana giriş ekranını göster; Bankalar sidebar gizli kalır."""
        self.navigationInterface.hide()
        self.switchTo(self._home_page)
        self._module_bar.clear_module_selection()
        self._sync_title_bar_layout()

    def show_banks(self) -> None:
        """Bankalar modülünü aç; varsayılan sayfa Banka Özeti."""
        landing = self._banks_module.landing_page
        if landing is None:
            return

        self.navigationInterface.show()
        self.switchTo(landing)
        self.navigationInterface.setCurrentItem(BANK_SUMMARY_ROUTE)
        self._updateStackedBackground()
        self._module_bar.select_module(MODULE_FINANS)
        self._sync_title_bar_layout()
