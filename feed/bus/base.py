from typing import Callable, Iterable, TypedDict


class Event(TypedDict):
    type: str
    payload: dict


EventHandler = Callable[[Event], None]


class BusConsumer:
    def start(self, topics_or_bindings: Iterable[str], handler: EventHandler) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        pass
