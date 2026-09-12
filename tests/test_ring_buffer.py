from pathlib import Path

from chronosmatch.ipc.ring_buffer import RingBuffer
from chronosmatch.models.order import Order, Side


def test_ring_buffer_push_pop(tmp_path: Path):
    # Use a temporary mmap file
    mmap_path = tmp_path / "ring.dat"
    buffer = RingBuffer(path=mmap_path, capacity=4)
    try:
        orders = [
            Order(order_id=i, side=Side.BUY, price=100.0 + i, quantity=1, timestamp=0)
            for i in range(3)
        ]
        # push all orders
        for o in orders:
            buffer.push(o)
        # buffer should not be full yet (capacity 4, we pushed 3)
        assert not buffer.is_full()
        # pop them in order
        for expected in orders:
            got = buffer.pop()
            assert got == expected
        # now empty
        assert buffer.is_empty()
        # popping from empty returns None
        assert buffer.pop() is None
    finally:
        buffer.close()
        if mmap_path.exists():
            mmap_path.unlink()
