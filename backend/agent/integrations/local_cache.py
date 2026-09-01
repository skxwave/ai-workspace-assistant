from collections import OrderedDict
from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True, slots=True)
class _Slot[T]:
    value: T
    expires_at: float


class TtlLruCache[T]:
    def __init__(self, max_size: int) -> None:
        self._max_size = max_size
        self._slots: OrderedDict[str, _Slot[T]] = OrderedDict()

    def get(self, key: str) -> T | None:
        slot = self._slots.get(key)
        if slot is None:
            return None
        if monotonic() >= slot.expires_at:
            del self._slots[key]
            return None
        self._slots.move_to_end(key)
        return slot.value

    def set(self, key: str, value: T, ttl: float) -> None:
        self._slots[key] = _Slot(value, monotonic() + ttl)
        self._slots.move_to_end(key)
        while len(self._slots) > self._max_size:
            self._slots.popitem(last=False)

    def discard(self, key: str) -> None:
        self._slots.pop(key, None)
