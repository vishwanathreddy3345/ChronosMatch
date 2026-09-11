# ChronosMatch

Zero‑Copy High‑Frequency Trading Engine – educational demo.

## Overview

ChronosMatch demonstrates low‑latency techniques in Python:

- Memory‑mapped zero‑copy inter‑process communication (IPC)
- Binary serialization with `struct`
- Ring‑buffer architecture
- Async market‑data generation
- Cython‑accelerated matching engine
- SQLite persistence
- Terminal dashboard using `curses`

The project is deliberately synthetic – it uses generated market data only.

## Project Structure

```
ChronosMatch/
├─ src/chronosmatch/            # Python package
│   ├─ __init__.py
│   ├─ models/
│   ├─ ipc/
│   ├─ market/
│   ├─ engine/
│   ├─ persistence/
│   ├─ monitoring/
│   ├─ ui/
│   └─ application.py
├─ cython/chronosmatch/        # Cython sources
├─ tests/                       # Test suite
├─ benchmarks/                  # Benchmark scripts
├─ docs/                        # Documentation
├─ scripts/                     # Helper scripts
├─ pyproject.toml               # Build & tool configuration
├─ .gitignore
└─ LICENSE
```

## Getting Started

```bash
# Clone the repository (once hosted)
git clone <repo-url>
cd ChronosMatch

# Create a virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows PowerShell

# Upgrade pip and install build requirements
pip install --upgrade pip
pip install -e .[dev]
```

## Running the Simulator

```bash
python -m scripts.run_simulator
```

## Running the Dashboard

```bash
python -m scripts.run_dashboard
```

## Testing

```bash
pytest -v
```

## Benchmarking

```bash
python -m benchmarks.benchmark_python
python -m benchmarks.benchmark_cython
```

## License

MIT License – see `LICENSE` file.
