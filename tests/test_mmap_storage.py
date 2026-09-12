from pathlib import Path

from chronosmatch.ipc.mmap_storage import MMapStorage
from chronosmatch.models.order import Order, Side


def test_mmap_storage_write_and_read(tmp_path: Path):
    # Use a temporary file for mmap storage
    storage_path = tmp_path / "test_mmap.dat"
    storage = MMapStorage(path=storage_path, capacity=10)
    try:
        order = Order(
            order_id=1,
            side=Side.BUY,
            price=100.5,
            quantity=10,
            timestamp=123456789,
        )
        data = order.to_bytes()
        storage.write(0, data)
        read_back = storage.read(0, len(data))
        assert read_back == data
    finally:
        storage.close()
        # cleanup file
        if storage_path.exists():
            storage_path.unlink()
