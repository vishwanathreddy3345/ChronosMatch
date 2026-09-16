import pytest
from chronosmatch.engine.order_book import LimitOrderBook
from chronosmatch.models.order import Order, Side


def make_order(
    order_id: int,
    side: Side,
    price: float,
    quantity: int = 1,
    timestamp: int = 0,
) -> Order:
    return Order(
        order_id=order_id,
        side=side,
        price=price,
        quantity=quantity,
        timestamp=timestamp,
    )


def test_empty_book():
    book = LimitOrderBook()
    assert book.best_bid is None
    assert book.best_ask is None
    assert book.spread is None
    assert book.depth() == {}


def test_single_buy_order():
    book = LimitOrderBook()
    o = make_order(1, Side.BUY, price=100.0)
    book.add_order(o)
    assert book.best_bid == 100.0
    assert book.best_ask is None
    assert book.spread is None
    depth = book.depth(Side.BUY)
    assert list(depth.keys()) == [100.0]
    assert depth[100.0][0] == o


def test_single_sell_order():
    book = LimitOrderBook()
    o = make_order(1, Side.SELL, price=105.0)
    book.add_order(o)
    assert book.best_ask == 105.0
    assert book.best_bid is None
    assert book.spread is None
    depth = book.depth(Side.SELL)
    assert list(depth.keys()) == [105.0]
    assert depth[105.0][0] == o


def test_multiple_price_levels_buy():
    book = LimitOrderBook()
    book.add_order(make_order(1, Side.BUY, 99.0))
    book.add_order(make_order(2, Side.BUY, 101.0))
    book.add_order(make_order(3, Side.BUY, 100.0))
    # Best bid should be highest price
    assert book.best_bid == 101.0
    # Price levels should be sorted descending in internal list (not exposed directly)
    depth = book.depth(Side.BUY)
    assert list(depth.keys()) == [101.0, 100.0, 99.0]


def test_multiple_price_levels_sell():
    book = LimitOrderBook()
    book.add_order(make_order(1, Side.SELL, 110.0))
    book.add_order(make_order(2, Side.SELL, 108.0))
    book.add_order(make_order(3, Side.SELL, 109.0))
    assert book.best_ask == 108.0
    depth = book.depth(Side.SELL)
    assert list(depth.keys()) == [108.0, 109.0, 110.0]


def test_spread_calculation():
    book = LimitOrderBook()
    book.add_order(make_order(1, Side.BUY, 100.0))
    book.add_order(make_order(2, Side.SELL, 105.0))
    assert book.best_bid == 100.0
    assert book.best_ask == 105.0
    assert book.spread == 5.0


def test_fifo_within_price_level():
    book = LimitOrderBook()
    # Same price, different timestamps / order ids
    book.add_order(make_order(1, Side.BUY, 100.0, timestamp=10))
    book.add_order(make_order(2, Side.BUY, 100.0, timestamp=20))
    depth = book.depth(Side.BUY)
    orders = depth[100.0]
    assert [o.order_id for o in orders] == [1, 2]


def test_price_time_priority_mixed():
    book = LimitOrderBook()
    # Add buys with different prices
    book.add_order(make_order(1, Side.BUY, 99.0))
    book.add_order(make_order(2, Side.BUY, 101.0))
    book.add_order(make_order(3, Side.SELL, 105.0))
    book.add_order(make_order(4, Side.SELL, 103.0))
    assert book.best_bid == 101.0
    assert book.best_ask == 103.0
    assert book.spread == 2.0


def test_invalid_order_type():
    book = LimitOrderBook()
    with pytest.raises(TypeError):
        book.add_order("not an order")


def test_remove_order():
    book = LimitOrderBook()
    o1 = make_order(1, Side.BUY, 100.0)
    o2 = make_order(2, Side.BUY, 100.0)
    book.add_order(o1)
    book.add_order(o2)
    # Remove first order
    book.remove_order(1)
    depth = book.depth(Side.BUY)
    assert len(depth[100.0]) == 1
    assert depth[100.0][0].order_id == 2
    # Remove remaining order, price level should disappear
    book.remove_order(2)
    assert 100.0 not in book.depth(Side.BUY)
    assert book.best_bid is None


def test_remove_nonexistent_order():
    book = LimitOrderBook()
    book.add_order(make_order(1, Side.SELL, 110.0))
    with pytest.raises(KeyError):
        book.remove_order(999)


def test_book_state_after_removals():
    book = LimitOrderBook()
    book.add_order(make_order(1, Side.BUY, 101.0))
    book.add_order(make_order(2, Side.BUY, 102.0))
    book.add_order(make_order(3, Side.SELL, 105.0))
    # Remove best bid
    book.remove_order(2)
    assert book.best_bid == 101.0
    # Remove remaining bid
    book.remove_order(1)
    assert book.best_bid is None
    # Ask side remains
    assert book.best_ask == 105.0
