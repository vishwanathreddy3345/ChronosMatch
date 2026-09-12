import argparse
from pathlib import Path

from chronosmatch.ipc.ring_buffer import RingBuffer
from chronosmatch.models.order import Order, Side


def main(count: int, path: Path):
    ring = RingBuffer(path=path)
    try:
        for i in range(count):
            order = Order(
                order_id=i,
                side=Side.BUY if i % 2 == 0 else Side.SELL,
                price=100.0 + (i % 10),
                quantity=1 + (i % 5),
                timestamp=0,
            )
            ring.push(order)
        print(f"Produced {count} orders into {path}")
    finally:
        ring.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ring buffer producer demo")
    parser.add_argument(
        "--count",
        type=int,
        default=1000,
        help="Number of orders to produce",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("./src/chronosmatch/ipc/mmap.dat"),
        help="Path to mmap file used by ring buffer",
    )
    args = parser.parse_args()
    main(args.count, args.path)
