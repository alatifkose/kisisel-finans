"""Bankalar modülü ortak UI yardımcıları."""

from __future__ import annotations

from typing import Any

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget
from qfluentwidgets import InfoBar, InfoBarPosition


def active_label(value: Any) -> str:
    return "Evet" if bool(value) else "Hayır"


def show_error(parent: QWidget, title: str, message: str) -> None:
    InfoBar.error(
        title=title,
        content=message,
        orient=Qt.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP,
        duration=4000,
        parent=parent.window(),
    )


def show_success(parent: QWidget, title: str, message: str) -> None:
    InfoBar.success(
        title=title,
        content=message,
        orient=Qt.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP,
        duration=2500,
        parent=parent.window(),
    )


def show_info(parent: QWidget, title: str, message: str) -> None:
    InfoBar.info(
        title=title,
        content=message,
        orient=Qt.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP,
        duration=3000,
        parent=parent.window(),
    )


def switch_to_route(parent: QWidget, route_key: str) -> bool:
    """Ana pencerede route_key objectName'li sayfaya geç."""
    window = parent.window()
    target = window.findChild(QWidget, route_key)
    if target is not None and hasattr(window, "switchTo"):
        window.switchTo(target)
        return True
    return False
