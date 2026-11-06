import socket

from app.worker.lifespan import _start_metrics_server


def test_a_second_process_goes_without_the_taken_metrics_port() -> None:
    with socket.socket() as probe:
        probe.bind(("", 0))
        port = probe.getsockname()[1]

    assert _start_metrics_server(port) is True
    assert _start_metrics_server(port) is False
