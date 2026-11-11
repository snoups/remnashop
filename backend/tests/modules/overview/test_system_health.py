from app.modules.overview.dto import AttentionKind
from app.modules.overview.system_health import (
    ALERT_AFTER_CHECKS,
    RESTORE_AFTER_CHECKS,
    HealthProblem,
    HealthState,
    advance,
)

_WORKER = HealthProblem(kind=AttentionKind.PROCESS_DOWN, subject="worker")
_MEMORY = HealthProblem(kind=AttentionKind.HOST_MEMORY_HIGH, value=97)


def _run(checks: list[list[HealthProblem]]) -> tuple[HealthState, list[str], list[str]]:
    state = HealthState(streaks={}, alerted={})
    degraded: list[str] = []
    restored: list[str] = []
    for problems in checks:
        transition = advance(state, problems)
        state = transition.state
        degraded += [p.key for p in transition.degraded]
        restored += transition.restored
    return state, degraded, restored


def test_alerts_once_after_the_streak_and_restores_after_good_checks() -> None:
    down = ALERT_AFTER_CHECKS[AttentionKind.PROCESS_DOWN]
    state, degraded, restored = _run([[_WORKER]] * (down + 3) + [[]] * RESTORE_AFTER_CHECKS + [[]])
    assert degraded == [_WORKER.key]
    assert restored == [_WORKER.key]
    assert state == HealthState(streaks={}, alerted={})


def test_a_good_check_resets_the_streak() -> None:
    need = ALERT_AFTER_CHECKS[AttentionKind.HOST_MEMORY_HIGH]
    _, degraded, _ = _run(([[_MEMORY]] * (need - 1) + [[]]) * 3)
    assert degraded == []


def test_a_relapse_while_recovering_keeps_the_alert_without_repeating_it() -> None:
    down = ALERT_AFTER_CHECKS[AttentionKind.PROCESS_DOWN]
    checks = [[_WORKER]] * down + [[]] * (RESTORE_AFTER_CHECKS - 1) + [[_WORKER]]
    state, degraded, restored = _run(checks + [[]] * (RESTORE_AFTER_CHECKS - 1))
    assert degraded == [_WORKER.key]
    assert restored == []
    assert _WORKER.key in state.alerted
