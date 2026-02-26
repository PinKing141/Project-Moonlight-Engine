from collections import defaultdict
from typing import Callable, DefaultDict, List, Type


class EventBus:
    def __init__(self) -> None:
        self._subscribers: DefaultDict[Type[object], List[Callable[[object], None]]] = defaultdict(list)

    def subscribe(self, event_type: Type[object], handler: Callable[[object], None]) -> None:
        self._subscribers[event_type].append(handler)

    def publish(self, event: object) -> None:
        for handler in self._subscribers[type(event)]:
            handler(event)
