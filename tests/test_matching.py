from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from chronosmatch.engine.matching import MatchingEngine
from chronosmatch.engine.order_book import LimitOrderBook
from chronosmatch.ipc.ring_buffer import RingBuffer
from chronosmatch.models.order import Order, Side
from chronosmatch.pipeline.week1 import Week1Pipeline
from chronosmatch.simulator.async_market import AsyncMarketSimulator


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


def test_matching_engine_initial_state():
    engine = MatchingEngine()
    assert isinstance(engine.book, LimitOrderBook)
    assert engine.processed_count == 0
    assert engine.best_bid is None
    assert engine.best_ask is None
    assert engine.spread is None
    assert engine.depth() == {}


def test_process_buy_order_on_bid_side():
    engine = MatchingEngine()
    order = make_order(1, Side.BUY, price=100.0, quantity=10, timestamp=100)
    engine.process_order(order)

    assert engine.processed_count == 1
    assert engine.best_bid == 100.0
    assert engine.best_ask is None
    assert engine.spread is None

    bids = engine.depth(Side.BUY)
    assert 100.0 in bids
    assert bids[100.0] == (order,)
    assert engine.depth(Side.SELL) == {}


def test_process_sell_order_on_ask_side():
    engine = MatchingEngine()
    order = make_order(1, Side.SELL, price=105.5, quantity=5, timestamp=100)
    engine.process_order(order)

    assert engine.processed_count == 1
    assert engine.best_ask == 105.5
    assert engine.best_bid is None
    assert engine.spread is None

    asks = engine.depth(Side.SELL)
    assert 105.5 in asks
    assert asks[105.5] == (order,)
    assert engine.depth(Side.BUY) == {}


def test_multiple_price_levels_and_best_prices():
    engine = MatchingEngine()
    # Insert bids at different price levels
    b1 = make_order(1, Side.BUY, price=98.0)
    b2 = make_order(2, Side.BUY, price=101.5)
    b3 = make_order(3, Side.BUY, price=99.0)
    for b in (b1, b2, b3):
        engine.process_order(b)

    # Highest bid should be 101.5
    assert engine.best_bid == 101.5

    # Insert asks at different price levels
    a1 = make_order(4, Side.SELL, price=105.0)
    a2 = make_order(5, Side.SELL, price=102.5)
    a3 = make_order(6, Side.SELL, price=108.0)
    for a in (a1, a2, a3):
        engine.process_order(a)

    # Lowest ask should be 102.5
    assert engine.best_ask == 102.5
    assert engine.spread == pytest.approx(1.0)
    assert engine.processed_count == 6

    # Verify depth sorting
    bids = engine.depth(Side.BUY)
    assert list(bids.keys()) == [101.5, 99.0, 98.0]
    asks = engine.depth(Side.SELL)
    assert list(asks.keys()) == [102.5, 105.0, 108.0]


def test_fifo_priority_at_identical_prices():
    engine = MatchingEngine()
    # Orders at identical price with different timestamps / IDs
    o1 = make_order(1, Side.BUY, price=100.0, timestamp=10)
    o2 = make_order(2, Side.BUY, price=100.0, timestamp=20)
    o3 = make_order(3, Side.BUY, price=100.0, timestamp=30)
    for o in (o1, o2, o3):
        engine.process_order(o)

    bids = engine.depth(Side.BUY)
    assert bids[100.0] == (o1, o2, o3)

    s1 = make_order(4, Side.SELL, price=110.0, timestamp=15)
    s2 = make_order(5, Side.SELL, price=110.0, timestamp=25)
    for s in (s1, s2):
        engine.process_order(s)

    asks = engine.depth(Side.SELL)
    assert asks[110.0] == (s1, s2)


def test_invalid_orders_handled_consistently():
    engine = MatchingEngine()
    with pytest.raises(TypeError, match="must be an Order instance"):
        engine.process_order(None)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="must be an Order instance"):
        engine.process_order("not_an_order")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="must be an Order instance"):
        engine.process_order(12345)  # type: ignore[arg-type]

    assert engine.processed_count == 0


def test_consume_one_from_ring_buffer(tmp_path: Path):
    buf_file = tmp_path / "rb_consume_one.dat"
    ring = RingBuffer(path=buf_file, capacity=4)
    engine = MatchingEngine()

    # Empty buffer returns None
    assert engine.consume_one(ring) is None
    assert engine.processed_count == 0

    # Push order to ring buffer
    order = make_order(1, Side.BUY, price=50.0, quantity=100)
    ring.push(order)

    # Consume single order
    consumed = engine.consume_one(ring)
    assert consumed == order
    assert engine.processed_count == 1
    assert engine.best_bid == 50.0

    # Buffer should now be empty
    assert engine.consume_one(ring) is None

    ring.close()
    if buf_file.exists():
        buf_file.unlink()


def test_consume_from_ring_buffer_async(tmp_path: Path):
    buf_file = tmp_path / "rb_async_consume.dat"
    ring = RingBuffer(path=buf_file, capacity=10)
    sim = AsyncMarketSimulator(
        buffer_path=buf_file,
        buffer_capacity=10,
        count=5,
        rate=1000.0,
        seed=999,
    )
    engine = MatchingEngine()

    async def run_producer_consumer():
        producer_task = asyncio.create_task(sim.run())
        consumer_task = asyncio.create_task(
            engine.consume_from_ring_buffer(ring, expected_count=5)
        )
        consumed = await consumer_task
        await producer_task
        return consumed

    consumed = asyncio.run(run_producer_consumer())
    assert len(consumed) == 5
    assert engine.processed_count == 5
    assert engine.best_bid is not None or engine.best_ask is not None

    sim.close()
    ring.close()
    if buf_file.exists():
        buf_file.unlink()


def test_orders_flow_from_pipeline_into_book(tmp_path: Path):
    buf_file = tmp_path / "week1_pipeline_matching.dat"
    engine = MatchingEngine()
    count = 10

    pipeline = Week1Pipeline(
        buffer_path=buf_file,
        buffer_capacity=10,
        count=count,
        rate=2000.0,
        seed=42,
        matching_engine=engine,
    )

    orders = asyncio.run(pipeline.run())
    assert len(orders) == count
    assert engine.processed_count == count
    assert pipeline.matching_engine is engine

    # Verify every order is present in the engine book
    buy_orders = [o for o in orders if o.side == Side.BUY]
    sell_orders = [o for o in orders if o.side == Side.SELL]

    if buy_orders:
        expected_best_bid = max(o.price for o in buy_orders)
        assert engine.best_bid == expected_best_bid
        for bo in buy_orders:
            assert bo in engine.depth(Side.BUY)[bo.price]

    if sell_orders:
        expected_best_ask = min(o.price for o in sell_orders)
        assert engine.best_ask == expected_best_ask
        for so in sell_orders:
            assert so in engine.depth(Side.SELL)[so.price]


def test_matching_engine_run_pipeline_helper(tmp_path: Path):
    buf_file = tmp_path / "run_pipeline_helper.dat"
    engine = MatchingEngine()
    count = 6

    orders = asyncio.run(
        engine.run_pipeline(
            buffer_path=buf_file,
            buffer_capacity=10,
            count=count,
            rate=2000.0,
            seed=777,
        )
    )

    assert len(orders) == count
    assert engine.processed_count == count
    assert not buf_file.exists()
