from app.core.host_metrics import (
    parse_cpu_times,
    read_host_cpu_percent,
    read_host_disk,
    read_host_load,
)


def test_parse_cpu_times_sums_busy_and_idle() -> None:
    # user nice system idle iowait irq softirq steal
    assert parse_cpu_times("cpu  100 0 50 800 50 0 0 0 0 0") == (1000, 850)


def test_parse_cpu_times_rejects_other_lines() -> None:
    assert parse_cpu_times("intr 12345") is None


def test_disk_and_load_report_something_on_any_posix_host() -> None:
    disk = read_host_disk("/")
    assert disk is not None and disk.total_bytes >= disk.used_bytes > 0
    load = read_host_load()
    assert load is not None and load.cpu_count >= 1


async def test_cpu_percent_is_none_or_a_percentage() -> None:
    value = await read_host_cpu_percent()
    assert value is None or 0.0 <= value <= 100.0
