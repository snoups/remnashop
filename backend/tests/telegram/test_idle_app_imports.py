import subprocess
import sys
from pathlib import Path


def test_the_idle_bot_never_loads_aiogram() -> None:
    # without a token the process serves only /health and a restart listener;
    # aiogram's models alone cost ~200 MB of RSS
    code = (
        "import sys\n"
        "for name in ('aiogram', 'aiogram_dialog', 'fluentogram'):\n"
        "    sys.modules[name] = None\n"
        "import runpy\n"
        "runpy.run_module('app.telegram.__main__', run_name='not_main')\n"
        "from app.core.config import AppConfig\n"
        "from app.telegram.idle_app import get_idle_app\n"
        "get_idle_app(AppConfig.get())\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=Path(__file__).parents[2]
    )
    assert result.returncode == 0, result.stderr
