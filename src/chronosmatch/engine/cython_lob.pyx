// cython_lob.pyx – minimal Cython wrapper around Python LimitOrderBook

# distutils: language = c

cdef class CythonLimitOrderBook:
    """A thin Cython wrapper that forwards to the pure‑Python LimitOrderBook.
    This provides a Cython extension foundation without changing behaviour.
    """
    cdef object _py_book

    def __cinit__(self):
        from .order_book import LimitOrderBook
        self._py_book = LimitOrderBook()

    def add_order(self, order):
        """Add an Order instance to the book."""
        self._py_book.add_order(order)

    @property
    def best_bid(self):
        return self._py_book.best_bid

    @property
    def best_ask(self):
        return self._py_book.best_ask
