"""Modüller arası gevşek bağlı haberleşme için basit olay yayıncısı."""

from collections import defaultdict
from typing import Any, Callable, DefaultDict, List


class EventBus:
    """Basit publish/subscribe olay yolu."""

    def __init__(self) -> None:
        self._subscribers: DefaultDict[str, List[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, event_type: str, callback: Callable[[Any], None]) -> None:
        """Belirtilen olay türüne abone ol."""
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[Any], None]) -> None:
        """Aboneliği kaldır."""
        if callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)

    def publish(self, event_type: str, data: Any = None) -> None:
        """Olayı tüm abonelere ilet."""
        for callback in list(self._subscribers[event_type]):
            callback(data)


# Uygulama genelinde paylaşılan tek örnek
event_bus = EventBus()
