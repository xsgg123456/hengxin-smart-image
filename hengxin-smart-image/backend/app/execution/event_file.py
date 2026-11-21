"""Read semantic evidence and historical CLI JSONL with a bounded record size."""
from pathlib import Path
from app.execution.safe_stream import reader

# One legacy event could occupy the entire original 64 MiB stream.
MAX_EVENT_LINE = 64 * 1024 * 1024
COMPACTED = 'platform.log_compacted'
COMPACTED_NOTICE = '本轮详细日志已精简，任务继续执行。'
LIVE_POLL_RECORDS = 256


def read_line(stream):
    raw = stream.readline(MAX_EVENT_LINE + 1)
    if len(raw) > MAX_EVENT_LINE and not raw.endswith(b'\n'):
        raise ValueError('CLI event exceeds the record limit')
    return raw


def lines(path):
    with reader(Path(path).absolute()) as stream:
        while raw := read_line(stream):
            if raw.strip():
                yield raw.decode('utf-8')
