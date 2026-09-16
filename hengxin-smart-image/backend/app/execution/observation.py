"""Best-effort observation, fenced separately from authoritative execution/results."""
import copy
import json
import logging
import time
from pathlib import Path

from app.models import utcnow
from app.modules.tasks.attempts import ExecutionAttempt
from app.modules.tasks.claims import locked_execution, valid
from .public_messages import public_message

LABELS = {'queued': '等待执行', 'preparing': '准备素材', 'starting': '启动执行器',
          'generating': '模型处理中', 'validating': '校验生成结果', 'storing': '保存图片',
          'publishing': '发布结果', 'completed': '处理结束', 'failed': '执行失败',
          'cancelled': '已取消', 'uncertain': '执行状态待核实'}
TERMINAL = {'succeeded': 'completed', 'partial': 'completed', 'failed': 'failed',
            'cancelled': 'cancelled', 'uncertain': 'uncertain'}
ACTIVITY = {'thread.started': '执行会话已建立', 'turn.started': '模型已开始处理',
            'turn.completed': '模型本轮处理结束，等待结果校验',
            'turn.failed': '模型报告本轮未完成', 'error': '执行器报告异常'}


class EventTail:
    """Read bounded chunks; never keep raw event content in public observations."""
    def __init__(self):
        self.offset, self.pending, self.dropping = 0, b'', False

    def read(self, path):
        messages = []
        try:
            with Path(path).open('rb') as stream:
                stream.seek(self.offset)
                chunk = stream.read(256 * 1024)
                self.offset = stream.tell()
        except OSError:
            return messages
        pieces = (self.pending + chunk).split(b'\n')
        self.pending = pieces.pop()
        for line in pieces:
            if self.dropping:
                self.dropping = False
                continue
            if len(line) > 64 * 1024:
                continue
            try:
                event = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if not isinstance(event, dict):
                continue
            message = public_message(event)
            if message:
                messages.append(message)
                continue
            kind = event.get('type')
            if not isinstance(kind, str):
                continue
            if kind in ACTIVITY:
                messages.append(ACTIVITY[kind])
            elif kind in ('item.started', 'item.completed'):
                item = event.get('item')
                if isinstance(item, dict) and item.get('type') in ('command_execution', 'mcp_tool_call'):
                    messages.append('模型正在调用工具' if kind == 'item.started' else '一次工具调用已结束')
        if len(self.pending) > 64 * 1024:
            self.pending, self.dropping = b'', True
        return messages


class Observer:
    def __init__(self, factory, job_id, token, attempt_id, workspace, total):
        self.factory, self.job_id, self.token, self.attempt_id = factory, job_id, token, attempt_id
        self.workspace, self.tail, self.last_tick = workspace, EventTail(), 0.0
        self.sequence, self.session_id, self.baseline = 0, None, set()
        self.data = {'stage': 'preparing', 'events': [], 'failure': None,
                     'totalImages': total, 'detectedImages': None, 'lastActivityAt': None}

    def event(self, message):
        stamp = utcnow().isoformat()
        self.data['lastActivityAt'] = stamp
        if (self.data['events'] and self.data['events'][-1]['message'] == message
                and self.data['events'][-1]['stage'] == self.data['stage']):
            return
        self.sequence += 1
        self.data['events'] = (self.data['events'] + [dict(sequence=self.sequence,
            stage=self.data['stage'], message=message, at=stamp)])[-100:]

    def phase(self, stage, failure=None):
        self.data['stage'] = stage
        if failure is not None:
            self.data['failure'] = failure
        self.event(LABELS[stage])
        self.save()

    def save(self):
        try:
            with self.factory.begin() as session:
                task, round, job = locked_execution(session, self.job_id)
                row = session.get(ExecutionAttempt, self.attempt_id)
                if (not row or not task or not job or task.current_round_id != round.id
                        or row.claim_token != self.token or job.claim_token != self.token):
                    return
                if round.status in TERMINAL:
                    self.data['stage'] = TERMINAL[round.status]
                elif not valid(task, round, job, self.token):
                    return
                self.data['updatedAt'] = utcnow().isoformat()
                row.observation = copy.deepcopy(self.data)
        except Exception:
            # Observation must not alter claims, publish results or trigger a retry.
            logging.getLogger(__name__).warning('execution_observation_write_failed attempt=%s', self.attempt_id)

    def tick(self, session_id=None, force=False):
        try:
            self._tick(session_id, force)
        except Exception:
            logging.getLogger(__name__).warning('execution_observation_read_failed attempt=%s', self.attempt_id)

    def _tick(self, session_id=None, force=False):
        if not force and time.monotonic() - self.last_tick < 2:
            return
        self.last_tick = time.monotonic()
        self.session_id = session_id or self.session_id
        for message in self.tail.read(self.workspace.control / 'events.jsonl'):
            self.event(message)
        if self.session_id:
            root = self.workspace.home / '.codex' / 'generated_images' / self.session_id
            try:
                if (not root.is_symlink() and not root.parent.is_symlink() and root.exists()
                        and root.resolve().is_relative_to(self.workspace.home.resolve())):
                    names = {p.name for p in root.iterdir() if p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp')
                             and not p.is_symlink() and p.is_file()}
                    count = min(len(names - self.baseline), 10000)
                    if count != self.data['detectedImages']:
                        previous_count = self.data['detectedImages'] or 0
                        self.data['detectedImages'] = count
                        if count > previous_count:
                            self.event('检测到生成图片，尚待结果校验')
            except OSError:
                pass
        self.save()
