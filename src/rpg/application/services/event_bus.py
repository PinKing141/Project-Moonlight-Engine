from collections import defaultdict
import logging
from typing import Callable, DefaultDict, List, Type


class EventBus:
    def __init__(self) -> None:
        self._subscribers: DefaultDict[Type[object], List[tuple[int, int, Callable[[object], None]]]] = defaultdict(list)
        self._next_order = 0
        self._last_publish_errors: List[Exception] = []
        self._logger = logging.getLogger(__name__)

    def subscribe(self, event_type: Type[object], handler: Callable[[object], None], *, priority: int = 100) -> None:
        self._subscribers[event_type].append((int(priority), self._next_order, handler))
        self._next_order += 1
        self._subscribers[event_type].sort(key=lambda row: (row[0], row[1]))

    def publish(self, event: object) -> None:
        self._last_publish_errors = []
        event_type = type(event)
        for priority, _, handler in self._subscribers[event_type]:
            try:
                handler(event)
            except Exception as exc:
                self._last_publish_errors.append(exc)
                handler_name = getattr(handler, "__qualname__", getattr(handler, "__name__", repr(handler)))
                self._logger.exception(
                    "Event handler failed and was isolated",
                    extra={
                        "event_type": event_type.__name__,
                        "handler": handler_name,
                        "priority": priority,
                    },
                )

    def last_publish_errors(self) -> List[Exception]:
        return list(self._last_publish_errors)
