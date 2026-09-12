import struct
import threading
from pathlib import Path
from typing import Optional

from .mmap_storage import MMapStorage
from .protocol import RECORD_SIZE
from ..models.order import Order

# Offsets for ring‑buffer metadata (head and tail indices, each uint64)
_META_FORMAT = "<QQ"  # little‑endian, two unsigned long long (8 bytes each)
_META_SIZE = struct.calcsize(_META_FORMAT)

# Data region starts after metadata
_DATA_OFFSET = _META_SIZE


class RingBuffer:
    """Fixed‑capacity, zero‑copy ring buffer built on a memory‑mapped file.

    The buffer stores serialized :class:`Order` records. ``head`` points to the
    next write position, ``tail`` points to the next read position. The buffer is
    *full* when advancing ``head`` would equal ``tail``; it is *empty* when ``head``
    equals ``tail``.
    """

    def __init__(
        self,
        path: Optional[Path] = None,
        capacity: Optional[int] = None,
    ) -> None:
        # Store the user‑intended capacity
        self._user_capacity = capacity if capacity is not None else 1_048_576
        # Internal storage uses capacity+1 to differentiate full vs empty
        internal_capacity = self._user_capacity + 1
        # Underlying mmap storage (includes metadata + data region)
        self._storage = MMapStorage(
            path=path,
            capacity=internal_capacity,
            extra_bytes=_META_SIZE,
        )
        self._lock = threading.Lock()
        # Initialise metadata if file is newly created (all zeros is fine)
        if self._storage.capacity * RECORD_SIZE + _META_SIZE != self._storage._size:
            raise RuntimeError("MMapStorage size mismatch for RingBuffer")
        self._ensure_meta_initialized()

    def _ensure_meta_initialized(self) -> None:
        # If the first 16 bytes are all zero, treat as initial state (head=tail=0)
        data = self._storage.read(0, _META_SIZE)
        if data == b"\x00" * _META_SIZE:
            # No explicit init needed; zeros already represent empty buffer
            return
        # Otherwise, assume metadata already set
        return

    def _read_meta(self) -> tuple[int, int]:
        raw = self._storage.read(0, _META_SIZE)
        head, tail = struct.unpack(_META_FORMAT, raw)
        return head, tail

    def _write_meta(self, head: int, tail: int) -> None:
        raw = struct.pack(_META_FORMAT, head, tail)
        self._storage.write(0, raw)

    def _data_offset(self, index: int) -> int:
        """Calculate byte offset for a given *record* index.

        ``index`` is a logical position in the circular buffer (0 ≤ index < capacity).
        """
        return _DATA_OFFSET + (index % self._storage.capacity) * RECORD_SIZE

    def is_empty(self) -> bool:
        head, tail = self._read_meta()
        return head == tail

    def is_full(self) -> bool:
        head, tail = self._read_meta()
        # Number of elements currently in buffer
        count = (head - tail) % self._storage.capacity
        return count == self._user_capacity

    def push(self, order: Order) -> None:
        """Write ``order`` to the buffer.

        Raises:
            BufferError: If the buffer is full.
        """
        with self._lock:
            head, tail = self._read_meta()
            if self.is_full():
                raise BufferError("Ring buffer is full")
            offset = self._data_offset(head)
            self._storage.write(offset, order.to_bytes())
            # Advance head
            new_head = (head + 1) % self._storage.capacity
            self._write_meta(new_head, tail)

    def pop(self) -> Optional[Order]:
        """Read the next order from the buffer.

        Returns ``None`` if the buffer is empty.
        """
        with self._lock:
            head, tail = self._read_meta()
            if self.is_empty():
                return None
            offset = self._data_offset(tail)
            data = self._storage.read(offset, RECORD_SIZE)
            order = Order.from_bytes(data)
            # Advance tail
            new_tail = (tail + 1) % self._storage.capacity
            self._write_meta(head, new_tail)
            return order

    def close(self) -> None:
        self._storage.close()

    # Convenience properties
    @property
    def capacity(self) -> int:
        """User‑visible capacity (number of orders that can be stored)."""
        return self._user_capacity

    @property
    def record_size(self) -> int:
        return RECORD_SIZE
