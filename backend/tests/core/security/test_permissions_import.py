import subprocess
import sys


def test_event_log_tasks_module_imports_cleanly_in_a_fresh_interpreter() -> None:
    """A circular import shows up only when a fresh process imports
    app.modules.event_log.tasks first, as `taskiq worker` does; pytest's own
    import order never hits it."""
    result = subprocess.run(
        [sys.executable, "-c", "import app.modules.event_log.tasks"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
