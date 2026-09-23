"""One bounded continuation of a stopped initial set, with separate evidence."""
import json
import re
from dataclasses import replace

from sqlalchemy import select

from app.modules.tasks.attempts import ExecutionAttempt
from app.modules.tasks.claims import locked_execution, valid
from app.modules.tasks.models import RoundRecord
from .diagnostics import _safe_read, cli_failure_code
from .events import parse_events
from .observation import EventTail

PROMPT = '''请继续完成当前换图任务，沿用本会话和当前工作目录中保存的素材、候选图片及处理进度。

先检查上一轮的实际结果和停止原因。若已有满足用户要求的图片，请保留并复用，不要整批重新生成。

如果上一轮因自检不合格而停止，请对照原图和参考素材重新核实：
判断应基于具体、可观察的缺陷，不要仅因主观疑虑、无法保证完全一致，或追求用户未要求的额外完美而否决结果。

如果现有结果已经满足用户明确提出的要求，请停止修改并交付。
如果确有缺陷，请只修复对应图片和问题区域，保留其他已符合要求的内容。实际执行修复并检查改善情况，不要仅重复上一轮失败说明后结束，也不要重复已经证明无效的操作。

继续遵守用户明确提出的修改范围、尺寸和质量要求，不得忽略已确认的缺陷或将不合格候选冒充成品。

完成后，在最终回复中按原底图顺序展示全部成品图片，并提供各自的文件链接。已完成的图片也需要一并列出，不能只交付本次补修的图片。

如果仍存在无法解决的问题，请保存当前最佳结果和进度，并具体说明剩余问题及必要条件。'''

_BLOCKED_ERROR = re.compile(
    r'\b(?:401|403|429)\b|unauthorized|authentication|invalid[ _-](?:api[ _-])?key|'
    r'not logged in|quota|usage[ _-]limit|rate[ _-]limit|insufficient[ _-](?:credit|balance)|'
    r'credits? (?:exhausted|remaining)|额度|余额不足|认证失败|鉴权失败|用量.*上限', re.I)


def initial_set(session, task, round):
    return (round.target is None and task.mode in ('wallpaper', 'product')
            and bool(task.template_snapshot)
            and session.scalar(select(RoundRecord.id).where(
                RoundRecord.task_id == task.id, RoundRecord.id != round.id).limit(1)) is None)


def can_continue(summary, receipt, control, home, remaining):
    # execute() returns only after the exact child has been reaped.
    if (type(receipt.get('exit_code')) is not int or receipt.get('reason')
            or remaining < 1 or not summary.session_id
            or summary.error not in (None, 'cli_error', 'turn_failed')):
        return False
    sessions = home / 'sessions'
    if sessions.is_symlink() or not any(sessions.rglob(f'*{summary.session_id}*')):
        return False
    if cli_failure_code(control / 'stderr.log') in ('authentication_failed', 'rate_limited'):
        return False
    try:
        stderr = _safe_read(control / 'stderr.log', 32 * 1024, tail=True,
                            allow_windows_fallback=True).decode('utf-8', errors='replace')
    except FileNotFoundError:
        stderr = ''
    except (OSError, ValueError):
        return False
    if _BLOCKED_ERROR.search(stderr):
        return False
    try:
        events = _safe_read(control / 'events.jsonl', 64 * 1024 * 1024,
                            allow_windows_fallback=True).decode('utf-8')
        for line in events.splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get('type') == 'thread.started' and event.get('thread_id') != summary.session_id:
                return False  # Later failure events must not hide an earlier session mismatch.
            if event.get('type') in ('error', 'turn.failed') and _BLOCKED_ERROR.search(json.dumps(event, ensure_ascii=False)):
                return False
    except (OSError, ValueError, AttributeError):
        return False
    return True


def prepare_continuation(factory, job_id, token, attempt_id, workspace, observer, summary, code):
    """Consume the sole continuation before spawn; keep work/home and the first baseline."""
    old = workspace.control
    control = old.with_name(old.name + '-intervention-1')
    control.mkdir(mode=0o700)  # Existing evidence is never overwritten or replayed.
    for name in ('baseline.json', 'delivery.json'):
        (control / name).write_bytes((old / name).read_bytes())
    (control / 'intervention.json').write_text(json.dumps(
        {'count': 1, 'previousControl': old.name, 'usage': summary.usage, 'reason': code}))
    with factory.begin() as session:
        task, round, job = locked_execution(session, job_id)
        attempt = session.get(ExecutionAttempt, attempt_id)
        if (not valid(task, round, job, token) or not attempt or attempt.claim_token != token
                or round.execution_config.get('autoInterventionCount', 0)):
            return False
        round.execution_config = {**round.execution_config, 'autoInterventionCount': 1}
        attempt.workspace = str(control)
        attempt.status, attempt.finished_at = 'starting', None
        attempt.process_id = attempt.boot_id = attempt.process_start = None
        attempt.exit_code = attempt.error = None
    workspace.control = control
    observer.tail, observer.last_tick = EventTail(), 0.0
    observer.event('首次换套图未完成，自动继续处理（1/1）')
    observer.save()
    return True


def invocation_summary(control, expected_session=None):
    """Recovery and normal completion both include the first invocation's known usage."""
    summary = parse_events(control / 'events.jsonl', expected_session)
    marker = control / 'intervention.json'
    if not marker.exists():
        return summary
    data = json.loads(_safe_read(marker, 64 * 1024, allow_windows_fallback=True))
    if data.get('count') != 1:
        raise ValueError('Invalid intervention record')
    previous = data.get('usage')
    if previous is not None and (not isinstance(previous, dict) or any(
            not isinstance(k, str) or type(v) is not int or v < 0 for k, v in previous.items())):
        raise ValueError('Invalid intervention usage')
    usage = None if previous is None and summary.usage is None else dict(previous or {})
    for key, value in (summary.usage or {}).items():
        usage[key] = usage.get(key, 0) + value
    return replace(summary, usage=usage)
