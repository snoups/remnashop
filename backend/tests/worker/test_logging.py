import importlib

import pytest
from taskiq import TaskiqState


@pytest.mark.parametrize(
    ("module_name", "process"),
    [("app.worker.lifespan", "worker"), ("app.worker.scheduler", "scheduler")],
)
async def test_each_worker_process_logs_to_its_own_file(
    module_name: str, process: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = importlib.import_module(module_name)
    calls: list[str] = []
    monkeypatch.setattr(module, "setup_logger", lambda config, name: calls.append(name))

    await module._setup_logging(TaskiqState())

    assert calls == [process]
