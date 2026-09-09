import datetime as dt
import json
from scripts import watchdog

UTC = dt.timezone.utc


def at(value):
    return dt.datetime.fromisoformat(value).replace(tzinfo=UTC)


def run(created, status='completed', conclusion='success', **extra):
    return {'created_at': created + 'Z', 'status': status, 'conclusion': conclusion,
            'html_url': 'https://github.com/example/run/1', **extra}


def test_planned_overnight_pause_is_not_a_dead_cron():
    previous = run('2026-09-08T19:20:00')
    assert watchdog.workflow_issue(previous, 'publisher', 5, at('2026-09-09T06:55:00'), publishing=True) is None
    assert watchdog.workflow_issue(previous, 'publisher', 5, at('2026-09-09T08:00:00'), publishing=True) is None


def test_actual_five_hour_gap_is_reported_as_delay_not_proven_death():
    issue = watchdog.workflow_issue(run('2026-09-08T11:57:24'), 'publisher', 5,
                                     at('2026-09-08T16:59:49'), publishing=True)
    assert 'עיכוב' in issue
    assert '5.0' in issue
    assert 'cron אולי מת' not in issue


def test_recovered_run_clears_the_gap():
    assert watchdog.workflow_issue(run('2026-09-08T17:02:56'), 'publisher', 5,
                                   at('2026-09-08T17:10:00'), publishing=True) is None


def test_night_does_not_hide_failure_or_missing_daytime_runs():
    failure = run('2026-09-08T19:20:00', conclusion='failure')
    assert 'נכשלה' in watchdog.workflow_issue(failure, 'publisher', 5, at('2026-09-09T02:00:00'), publishing=True)
    assert watchdog.workflow_issue(run('2026-09-07T19:20:00'), 'publisher', 5,
                                   at('2026-09-09T06:00:00'), publishing=True)


def test_running_and_queued_jobs_are_distinguished_from_scheduler_silence():
    assert watchdog.workflow_issue(run('2026-09-08T13:00:00', 'in_progress', None,
        run_started_at='2026-09-08T18:00:00Z'), 'publisher', 5, at('2026-09-08T18:05:00'), publishing=True) is None
    waiting = run('2026-09-08T16:00:00', 'queued', None)
    assert 'בתור' in watchdog.workflow_issue(waiting, 'publisher', 5, at('2026-09-08T18:05:00'), publishing=True)


def test_daily_workflows_keep_wall_clock_threshold():
    issue = watchdog.workflow_issue(run('2026-09-07T13:00:00'), 'daily', 26, at('2026-09-08T16:00:00'))
    assert issue is not None


def test_skipped_job_is_not_a_successful_heartbeat():
    assert watchdog.workflow_issue(run('2026-09-08T18:00:00', conclusion='skipped'),
        'publisher', 5, at('2026-09-08T18:05:00'), publishing=True)


def test_workflows_only_does_not_send_email_or_touch_queue(monkeypatch):
    monkeypatch.setattr(watchdog.sys, 'argv', ['watchdog.py', '--workflows-only'])
    monkeypatch.setattr(watchdog, 'check_workflows', lambda: [])
    def forbidden(*args, **kwargs):
        raise AssertionError('read-only check attempted side effects')
    monkeypatch.setattr(watchdog, 'send_graph', forbidden)
    monkeypatch.setattr(watchdog, 'check_duplicates', forbidden)
    monkeypatch.setattr(watchdog.queue, '_req', forbidden)
    assert watchdog.main() == 0
