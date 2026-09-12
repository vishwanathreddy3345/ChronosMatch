import mmap
import os
import threading
from pathlib import Path
from typing import Optional, Any

from .protocol import RECORD_SIZE


class MMapStorage:
    """Simple file‑backed memory‑mapped storage.

    The file is created (or resized) to ``capacity * RECORD_SIZE`` bytes.
    It provides thread‑safe ``read`` and ``write`` operations at arbitrary
    byte offsets. Offsets must be aligned to ``RECORD_SIZE`` when writing
    full order records.
    """

    _lock: threading.Lock
    _mmap: mmap.mmap
    _file: Any
    _capacity: int
    _size: int
    _path: Path

    def __init__(
        self,
        path: Optional[Path] = None,
        capacity: Optional[int] = None,
        extra_bytes: int = 0,
    ) -> None:
        self._lock = threading.Lock()
        # Determine storage location
        self._path = path or Path(__file__).with_name("mmap.dat")
        # Capacity can be overridden via env var
        # Capacity can be overridden via env var
        env_cap = os.getenv("CHRONOSMAP_CAPACITY")
        if capacity is not None:
            self._capacity = capacity
        elif env_cap:
            self._capacity = int(env_cap)
        else:
            self._capacity = 1_048_576  # default 2^20 records
        # Total byte size includes record storage plus any extra bytes (e.g., metadata)
        self._size = self._capacity * RECORD_SIZE + extra_bytes
        self._ensure_file()
        self._mmap = mmap.mmap(
            self._file.fileno(),
            self._size,
            access=mmap.ACCESS_WRITE,
        )

    def _ensure_file(self) -> None:
        """Create the backing file if missing and set its length."""
        # Create parent directories if needed
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Open (or create) the file for read/write binary
        self._file = open(self._path, "r+b" if self._path.exists() else "w+b")
        # Resize to required size
        self._file.truncate(self._size)
        self._file.flush()

    def read(self, offset: int, size: int) -> bytes:
        """Read ``size`` bytes from ``offset``.

        The method acquires a lock to guarantee atomicity against concurrent writes.
        """
        if offset < 0 or offset + size > self._size:
            raise ValueError("Read beyond storage bounds")
        with self._lock:
            self._mmap.seek(offset)
            return self._mmap.read(size)

    def write(self, offset: int, data: bytes) -> None:
        """Write ``data`` at ``offset``.

        ``data`` length must not exceed storage bounds.
        """
        if offset < 0 or offset + len(data) > self._size:
            raise ValueError("Write beyond storage bounds")
        with self._lock:
            self._mmap.seek(offset)
            self._mmap.write(data)
            # Ensure data is flushed to the underlying file
            self._mmap.flush()

    def close(self) -> None:
        """Close the mmap and underlying file."""
        self._mmap.close()
        self._file.close()

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def record_size(self) -> int:
        return RECORD_SIZE
