import importlib
import re
import typing
from pathlib import Path
from typing import Any, Final

import pytest
from dishka import Scope
from taskiq import AsyncTaskiqDecoratedTask

import app.modules
from app.core.config import AppConfig
from app.worker.container import create_worker_container

_ENTRYPOINT: Final[Path] = Path(__file__).parents[3] / "docker-entrypoint.sh"
_MODULES_DIR: Final[Path] = Path(app.modules.__file__).parent


def _worker_task_modules() -> set[str]:
    worker_line = next(
        line for line in _ENTRYPOINT.read_text().splitlines() if "taskiq worker" in line
    )
    return set(re.findall(r"app\.modules\.\w+\.tasks", worker_line))


def _scheduler_task_modules() -> set[str]:
    scheduler_line = next(
        line for line in _ENTRYPOINT.read_text().splitlines() if "exec taskiq scheduler" in line
    )
    return set(re.findall(r"app\.modules\.\w+\.tasks", scheduler_line))


def _injected_types(task: AsyncTaskiqDecoratedTask[Any, Any]) -> list[Any]:
    func = task.original_func
    hints = typing.get_type_hints(getattr(func, "__dishka_orig_func__", func), include_extras=True)
    return [
        typing.get_args(hint)[0]
        for hint in hints.values()
        if typing.get_origin(hint) is typing.Annotated
        and type(hint.__metadata__[0]).__name__ == "_FromComponent"
    ]


def test_worker_command_lists_every_tasks_module() -> None:
    on_disk = {f"app.modules.{path.parent.name}.tasks" for path in _MODULES_DIR.glob("*/tasks.py")}
    assert _worker_task_modules() == on_disk


def test_scheduler_command_lists_every_module_with_a_schedule() -> None:
    # a module missing here is executed by the worker but never kicked by the scheduler
    scheduled = {
        f"app.modules.{path.parent.name}.tasks"
        for path in _MODULES_DIR.glob("*/tasks.py")
        if "schedule=" in path.read_text()
    }
    assert scheduled <= _scheduler_task_modules()


@pytest.mark.parametrize("module_name", sorted(_worker_task_modules()))
async def test_worker_container_resolves_every_task_dependency(
    config: AppConfig, module_name: str
) -> None:
    module = importlib.import_module(module_name)
    tasks = [v for v in vars(module).values() if isinstance(v, AsyncTaskiqDecoratedTask)]
    assert tasks, f"{module_name} defines no tasks"

    container = create_worker_container(config)
    async with container(scope=Scope.REQUEST) as request_container:
        for task in tasks:
            for dependency in _injected_types(task):
                await request_container.get(dependency)
    await container.close()
