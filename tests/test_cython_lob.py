import random
from chronosmatch.engine import LimitOrderBook, CythonLimitOrderBook
from chronosmatch.models.order import Order, Side


def deterministic_orders():
    # deterministic set of orders covering various cases
    return [
        Order(order_id=1, side=Side.BUY, price=100.0, quantity=10, timestamp=1),
        Order(order_id=2, side=Side.SELL, price=101.0, quantity=5, timestamp=2),
        Order(order_id=3, side=Side.BUY, price=99.5, quantity=7, timestamp=3),
        Order(order_id=4, side=Side.SELL, price=101.0, quantity=3, timestamp=4),
        Order(order_id=5, side=Side.BUY, price=100.0, quantity=2, timestamp=5),
    ]


def test_cython_lob_behaviour_matches_python():
    py_book = LimitOrderBook()
    cy_book = CythonLimitOrderBook()
    for order in deterministic_orders():
        py_book.add_order(order)
        cy_book.add_order(order)

    # best bid/ask
    assert py_book.best_bid == cy_book.best_bid
    assert py_book.best_ask == cy_book.best_ask
    assert py_book.spread == cy_book.spread

    # depth snapshots should be equivalent (price levels and order counts)
    py_depth = py_book.depth()
    cy_depth = cy_book.depth()
    assert set(py_depth.keys()) == set(cy_depth.keys())
    for price in py_depth:
        assert len(py_depth[price]) == len(cy_depth[price])
        # ensure FIFO order of order IDs
        assert [o.order_id for o in py_depth[price]] == [
            o.order_id for o in cy_depth[price]
        ]

    # removal
    py_book.remove_order(1)
    cy_book.remove_order(1)
    assert py_book.best_bid == cy_book.best_bid
    assert py_book.depth() == cy_book.depth()


def test_cython_lob_performance_no_assertion():
    """Benchmark both implementations without using pytest-benchmark.
    Prints the measured nanosecond durations; no assertions are made.
    """
    import time

    orders = [
        Order(
            order_id=i,
            side=random.choice([Side.BUY, Side.SELL]),
            price=random.uniform(90, 110),
            quantity=1,
            timestamp=i,
        )
        for i in range(2000)
    ]

    def run(book):
        for o in orders:
            book.add_order(o)

    # Python implementation timing
    start = time.perf_counter_ns()
    run(LimitOrderBook())
    py_ns = time.perf_counter_ns() - start

    # Cython implementation timing
    start = time.perf_counter_ns()
    run(CythonLimitOrderBook())
    cy_ns = time.perf_counter_ns() - start

    print(f"Python LimitOrderBook time: {py_ns} ns")
    print(f"Cython LimitOrderBook time: {cy_ns} ns")
