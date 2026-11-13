"""Persist the shared, public Codex stream for the owning conversation."""
import os
import time

from sqlalchemy import select

from app.overseas.studio import transcript as common
from .bindings import lock_admission
from .runtime import changed, locked, valid
from .turn_models import Transcript


def append(session, turn, value):
    identity, kind, text, state = value
    last = session.scalar(select(Transcript).where(Transcript.turn_id == turn.id,
        Transcript.item_id == identity).order_by(Transcript.id.desc()).limit(1))
    if last and (last.kind, last.text, last.state) == (kind, text, state):
        return
    session.add(Transcript(turn_id=turn.id, item_id=identity, kind=kind, text=text, state=state))
    if kind == 'message':
        turn.reply = text
    session.flush()


class Monitor:
    def __init__(self, factory, job_id, token, control):
        self.factory, self.job_id, self.token = factory, job_id, token
        self.path, self.last_poll = control / 'events.jsonl', 0.0

    def poll(self, final=False):
        if not final and time.monotonic() - self.last_poll < .5:
            return False
        self.last_poll = time.monotonic()
        with self.factory.begin() as session:
            lock_admission(session)
            state, channel, turn, job = locked(session, self.job_id)
            if not job or not valid(turn, job, self.token):
                return True
            if not self.path.exists():
                return False
            if self.path.is_symlink():
                raise ValueError('Invalid public event file')
            flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
            previous = turn.event_offset
            with os.fdopen(os.open(self.path, flags), 'rb') as stream:
                common.consume(session, turn, channel, stream, final, append_entry=append)
            if turn.event_offset != previous or turn.event_invalid:
                changed(state, channel, turn)
            return turn.event_invalid

    def __call__(self):
        return self.poll()
