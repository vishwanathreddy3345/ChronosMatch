from __future__ import annotations

from pathlib import Path
import pytest

from benchmarks.benchmark_pipeline import (
    format_benchmark_result,
    main,
    parse_args,
    run_pipeline_benchmark,
)


def test_benchmark_returns_valid_measurements(tmp_path: Path):
    tmp_file = tmp_path / "bench_test.dat"
    result = run_pipeline_benchmark(
        count=25,
        rate=float("inf"),
        buffer_capacity=10,
        seed=123,
        buffer_path=tmp_file,
    )

    assert result.order_count == 25
    assert result.elapsed_ns > 0
    assert result.elapsed_ms > 0
    assert result.orders_per_sec > 0
    assert result.avg_latency_ns > 0
    # Consistency of calculations
    expected_ms = result.elapsed_ns / 1_000_000.0
    assert result.elapsed_ms == pytest.approx(expected_ms)
    expected_latency = result.elapsed_ns / 25
    assert result.avg_latency_ns == pytest.approx(expected_latency)


def test_benchmark_exercises_real_pipeline(tmp_path: Path):
    tmp_file = tmp_path / "bench_real.dat"
    result = run_pipeline_benchmark(
        count=40,
        rate=float("inf"),
        buffer_capacity=15,
        seed=42,
        buffer_path=tmp_file,
    )

    assert result.order_count == 40
    # Orders were processed through MatchingEngine into LimitOrderBook
    assert result.best_bid is not None or result.best_ask is not None


def test_benchmark_invalid_configuration():
    with pytest.raises(ValueError, match="count must be a positive integer"):
        run_pipeline_benchmark(count=0)

    with pytest.raises(ValueError, match="count must be a positive integer"):
        run_pipeline_benchmark(count=-10)

    with pytest.raises(ValueError, match="rate must be positive"):
        run_pipeline_benchmark(count=10, rate=0.0)

    with pytest.raises(ValueError, match="rate must be positive"):
        run_pipeline_benchmark(count=10, rate=-100.0)

    with pytest.raises(ValueError, match="buffer_capacity must be a positive integer"):
        run_pipeline_benchmark(count=10, buffer_capacity=0)

    with pytest.raises(ValueError, match="buffer_capacity must be a positive integer"):
        run_pipeline_benchmark(count=10, buffer_capacity=-1)


def test_format_benchmark_result(tmp_path: Path):
    tmp_file = tmp_path / "bench_format.dat"
    result = run_pipeline_benchmark(
        count=15,
        rate=float("inf"),
        buffer_capacity=10,
        seed=1,
        buffer_path=tmp_file,
    )
    formatted = format_benchmark_result(result)

    assert "ChronosMatch Benchmark" in formatted
    assert "-----------------------" in formatted
    assert "Orders:          15" in formatted
    assert "Elapsed:" in formatted
    assert "ms" in formatted
    assert "Throughput:" in formatted
    assert "orders/sec" in formatted
    assert "Avg latency:" in formatted
    assert "ns/order" in formatted


def test_parse_args_defaults():
    args = parse_args([])
    assert args.count == 10_000
    assert args.rate is None
    assert args.buffer_capacity is None
    assert args.seed == 42
    assert args.workloads is None


def test_parse_args_custom():
    args = parse_args(
        [
            "--count",
            "5000",
            "--rate",
            "20000.0",
            "--buffer-capacity",
            "512",
            "--seed",
            "99",
            "--workloads",
            "100",
            "200",
        ]
    )
    assert args.count == 5000
    assert args.rate == 20000.0
    assert args.buffer_capacity == 512
    assert args.seed == 99
    assert args.workloads == [100, 200]


def test_benchmark_cli_single(capsys: pytest.CaptureFixture[str]):
    code = main(["--count", "20", "--seed", "7"])
    assert code == 0
    captured = capsys.readouterr()
    assert "ChronosMatch Benchmark" in captured.out
    assert "Orders:          20" in captured.out


def test_benchmark_cli_workloads(capsys: pytest.CaptureFixture[str]):
    code = main(["--workloads", "10", "20", "--seed", "7"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Running workload size: 10 orders..." in captured.out
    assert "Running workload size: 20 orders..." in captured.out
    assert "Orders:          10" in captured.out
    assert "Orders:          20" in captured.out
