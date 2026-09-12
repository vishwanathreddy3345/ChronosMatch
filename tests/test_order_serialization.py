import pytest

from chronosmatch.models.order import Order, Side


def test_order_round_trip_max_values():
    # Use maximum values fitting the struct format
    max_uint64 = (1 << 64) - 1
    max_uint32 = (1 << 32) - 1
    order = Order(
        order_id=max_uint64,
        side=Side.SELL,
        price=1e308,
        quantity=max_uint32,
        timestamp=max_uint64,
    )
    data = order.to_bytes()
    restored = Order.from_bytes(data)
    assert restored == order


def test_order_invalid_side_int():
    # Manually craft bytes with invalid side value (2)
    max_uint64 = (1 << 64) - 1
    invalid_side = 2
    price = 123.45
    quantity = 10
    timestamp = 0
    import struct

    data = struct.pack(
        "<Q B d I Q",
        max_uint64,
        invalid_side,
        price,
        quantity,
        timestamp,
    )
    with pytest.raises(ValueError):
        Order.from_bytes(data)


def test_order_from_bytes_invalid_length():
    with pytest.raises(ValueError):
        Order.from_bytes(b"too short")
