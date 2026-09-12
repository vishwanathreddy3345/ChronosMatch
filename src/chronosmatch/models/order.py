from __future__ import annotations

import enum
import struct
from dataclasses import dataclass
from typing import ClassVar, Tuple


class Side(enum.Enum):
    """Order side enumeration."""

    BUY = 0
    SELL = 1

    @classmethod
    def from_int(cls, value: int) -> "Side":
        """Convert integer to :class:`Side`.

        Raises:
            ValueError: If the integer does not map to a valid side.
        """
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(f"Invalid side value {value!r}") from exc

    def __int__(self) -> int:
        return self.value


@dataclass(slots=True)
class Order:
    """Compact binary‑serializable order representation.

    Fields:
        order_id: 64‑bit unsigned integer identifier.
        side: :class:`Side` (BUY/SELL).
        price: Floating‑point price; stored as IEEE‑754 double.
        quantity: 32‑bit unsigned integer.
        timestamp: 64‑bit unsigned integer nanosecond epoch.
    """

    order_id: int
    side: Side
    price: float
    quantity: int
    timestamp: int

    #: Struct format ``<Q B d I Q`` (little‑endian, no padding).
    _STRUCT: ClassVar[struct.Struct] = struct.Struct("<Q B d I Q")

    #: Size of a serialized order in bytes.
    RECORD_SIZE: ClassVar[int] = _STRUCT.size

    def __post_init__(self) -> None:
        if not isinstance(self.side, Side):
            raise TypeError("side must be a Side enum instance")
        if not (0 <= self.order_id < 2**64):
            raise ValueError("order_id out of range for uint64")
        if not (0 <= self.quantity < 2**32):
            raise ValueError("quantity out of range for uint32")
        if not (0 <= self.timestamp < 2**64):
            raise ValueError("timestamp out of range for uint64")
        # price is a double; no explicit range check beyond being a float.

    def to_bytes(self) -> bytes:
        """Serialize the order to a fixed‑size binary record.

        Returns:
            ``bytes`` of length :attr:`RECORD_SIZE`.
        """
        return self._STRUCT.pack(
            self.order_id,
            int(self.side),
            self.price,
            self.quantity,
            self.timestamp,
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> "Order":
        """Deserialize a binary record into an :class:`Order`.

        Args:
            data: Bytes object of length :attr:`RECORD_SIZE`.

        Raises:
            ValueError: If ``data`` is of incorrect length.
        """
        if len(data) != cls.RECORD_SIZE:
            raise ValueError(
                f"Invalid data length {len(data)}; expected {cls.RECORD_SIZE} bytes"
            )
        unpacked: Tuple[int, int, float, int, int] = cls._STRUCT.unpack(data)
        order_id, side_int, price, quantity, timestamp = unpacked
        side = Side.from_int(side_int)
        return cls(
            order_id=order_id,
            side=side,
            price=price,
            quantity=quantity,
            timestamp=timestamp,
        )
