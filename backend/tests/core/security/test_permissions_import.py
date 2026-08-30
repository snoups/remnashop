import subprocess
import sys


def test_event_log_tasks_module_imports_cleanly_in_a_fresh_interpreter() -> None:
    """Regression test for a circular import only reachable via a fresh
    process importing app.modules.event_log.tasks first (exactly what
    `taskiq worker app.worker.broker:broker app.modules.event_log.tasks`
    does) -- pytest's own cumulative import order never reproduces it."""
    result = subprocess.run(
        [sys.executable, "-c", "import app.modules.event_log.tasks"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
