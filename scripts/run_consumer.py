import argparse
from pathlib import Path

from chronosmatch.ipc.ring_buffer import RingBuffer


def main(path: Path):
    ring = RingBuffer(path=path)
    count = 0
    try:
        while True:
            order = ring.pop()
            if order is None:
                break
            count += 1
        print(f"Consumed {count} orders from {path}")
    finally:
        ring.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ring buffer consumer demo")
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("./src/chronosmatch/ipc/mmap.dat"),
        help="Path to mmap file used by ring buffer",
    )
    args = parser.parse_args()
    main(args.path)
