"""One acceptance path for stopped invocations, independent of process diagnostics."""
import json

from .delivery_snapshot import freeze_delivery, load_delivery
from .diagnostics import _safe_read
from .final_delivery import collect_final_outputs
from .output_collector import OutputCollectionError


UNCERTAIN_DELIVERY = frozenset(('final_delivery_uncertain', 'unreadable_event_stream'))


def accept_delivery(control, task_id, round_id, session_id, expected, receipt):
    # A snapshot is a platform-authored receipt, written only after the child stopped
    # and the complete delivery passed validation. Never reinterpret its model files.
    images = load_delivery(control, task_id, round_id, session_id, expected)
    if images is not None:
        return images
    if not isinstance(receipt, dict) or type(receipt.get('exit_code')) is not int:
        raise OutputCollectionError('final_delivery_uncertain')
    if receipt.get('reason') == 'cancelled':
        raise OutputCollectionError('cancelled')
    baseline = json.loads(_safe_read(control / 'baseline.json', 64 * 1024 * 1024,
                                    allow_windows_fallback=True))
    work = control.parents[1] / 'rounds' / str(round_id)
    home = control.parents[1] / 'home' / '.codex'
    images = collect_final_outputs(work, home, control / 'events.jsonl',
                                   session_id, baseline, expected)
    freeze_delivery(control, task_id, round_id, session_id, images)
    return images
