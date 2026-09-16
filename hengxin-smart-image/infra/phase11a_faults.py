"""Fault injection only inside the disposable acceptance worker process."""
import json
from pathlib import Path
import time
from uuid import UUID

from phase11a_checks import require


def whole_revision_recovery(run, task):
    marker = run.env.root / 'publication-interrupted'
    startup = (
        'import os\nfrom pathlib import Path\n'
        'from app.execution import codex_runner\nfrom app.worker import health\n'
        'health.reconcile_once = lambda *args, **kwargs: None\n'
        'def interrupt_publication(*args, **kwargs):\n'
        f'    Path({str(marker)!r}).write_text(str(os.getpid()))\n'
        '    os._exit(71)\n'
        'codex_runner.publish_results = interrupt_publication\n')
    run.env.stop_worker()
    run.env.start_worker(startup_code=startup)
    response = run.revise(task, None, '整套保持构图，将壁纸细节稍微提升清晰度。')
    require(response.status_code == 202, 'Whole revision not accepted')
    round_id = response.json()['roundId']
    deadline, last = time.monotonic() + 1200, None
    while time.monotonic() < deadline:
        run.evidence.sample([task])
        rows = run.evidence.attempts(task)
        current = next((row for row in rows if str(row['round_id']) == round_id), None)
        observation = run.request('GET', '/api/v1/tasks/' + task + '/execution')
        progress = (observation['stage'], len(observation['events']))
        if progress != last:
            print(json.dumps({'phase': 'whole-revision-fault', 'progress': progress}), flush=True)
            last = progress
        if current and current['round_status'] in ('failed', 'partial', 'cancelled'):
            raise RuntimeError('Whole revision failed before fault injection')
        if marker.exists() and current and current['round_status'] == 'uncertain':
            break
        time.sleep(2)
    require(marker.exists() and current and current['round_status'] == 'uncertain',
            'Did not observe interrupted publication and uncertain gate')
    require(current['exit_code'] == 0 and current['execution_count'] == 1, 'Real CLI did not finish exactly once')
    detail = run.request('GET', '/api/v1/tasks/' + task)
    require(not detail['executionControl']['canRevise'] and not detail['executionControl']['canRetry'],
            'Uncertain execution allowed another round')
    require(run.revise(task, 0, '不应在待核实时重开。').status_code == 409, 'Uncertain gate bypassed')
    job = str(UUID(str(current['job_id'])))
    run.env.command(['-c', 'from app.worker.outbox import publish\n'
                     f'for _ in range(3): publish({job!r})'], app=True)
    time.sleep(6)
    after = [row for row in run.evidence.attempts(task) if str(row['round_id']) == round_id]
    require(len(after) == 1 and after[0]['execution_count'] == 1, 'Redelivery started another CLI')
    run.record('worker-interruption-gate', {'roundId': round_id, 'cliCompletedBeforeCrash': True,
        'uncertainObserved': True, 'revisionRejected': True, 'redeliveries': 3, 'executionCount': 1})
    run.env.stop_worker()
    run.env.start_worker()
    # Normal production reconciliation must recover preserved real output, not generate it again.
    return str(current['id'])


def validate_stop(rows, receipt, reason):
    expected = 'cancelled' if reason == 'cancelled' else 'failed'
    require(len(rows) == 1 and rows[0]['status'] == 'finished'
            and rows[0]['round_status'] == expected and rows[0]['job_status'] == expected,
            'Stopped execution did not reach expected attempt/round/job terminal states')
    require(receipt['reason'] == reason and receipt['exit_code'] != 0, 'Unexpected stop cause')
    if reason == 'timeout':
        require(9 <= receipt['elapsed_seconds'] <= 30, 'Timeout outside configured tolerance')


def verify_cancellation_timeout(run):
    original = run.env.env['CODEX_TIMEOUT_SECONDS']
    for reason in ('cancelled', 'timeout'):
        if reason == 'timeout':
            run.env.env['CODEX_TIMEOUT_SECONDS'] = '10'
            run.env.restart_services()
        task = run.submit('fault-' + reason, run.single)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            run.evidence.sample([task])
            rows = run.evidence.attempts(task)
            if rows and rows[0]['process_id']:
                break
            time.sleep(.2)
        require(rows and rows[0]['status'] == 'running', 'No live CLI to stop')
        if reason == 'cancelled':
            run.request('DELETE', '/api/v1/tasks/' + task)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            rows = run.evidence.attempts(task)
            if rows and rows[0]['status'] == 'finished' and rows[0]['round_status'] in ('failed', 'cancelled'):
                break
            time.sleep(1)
        require(rows and rows[0]['status'] == 'finished', 'Stopped CLI did not finish')
        receipt_path = Path(rows[0]['workspace']) / 'exit.json'
        require(receipt_path.resolve().is_relative_to(run.env.root.resolve()), 'Receipt outside isolated root')
        receipt = json.loads(receipt_path.read_text())
        validate_stop(rows, receipt, reason)
        run.record('real-cli-' + reason, {'taskId': task, 'exitReason': reason,
            'elapsedSeconds': receipt['elapsed_seconds'], 'attempts': run.evidence.round_evidence(task)})
    run.env.env['CODEX_TIMEOUT_SECONDS'] = original
    run.env.restart_services()
