# Binary protocol constants for ChronosMatch IPC

from chronosmatch.models.order import Order

# Protocol version – can be incremented if layout changes
PROTOCOL_VERSION: int = 1

# Fixed record size (bytes) – matches Order.RECORD_SIZE
RECORD_SIZE: int = Order.RECORD_SIZE

# Byte offsets within a serialized order record (little‑endian)
OFFSET_ORDER_ID = 0  # uint64, 8 bytes
OFFSET_SIDE = OFFSET_ORDER_ID + 8  # uint8, 1 byte
OFFSET_PRICE = OFFSET_SIDE + 1  # double, 8 bytes
OFFSET_QUANTITY = OFFSET_PRICE + 8  # uint32, 4 bytes
OFFSET_TIMESTAMP = OFFSET_QUANTITY + 4  # uint64, 8 bytes

__all__ = [
    "PROTOCOL_VERSION",
    "RECORD_SIZE",
    "OFFSET_ORDER_ID",
    "OFFSET_SIDE",
    "OFFSET_PRICE",
    "OFFSET_QUANTITY",
    "OFFSET_TIMESTAMP",
]
