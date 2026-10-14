"""Bounded, isolated real CLI regression; run as overseas service user, never touches SQL."""
import json
import tempfile
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings
from app.execution.events import parse_events
from app.execution.process import execute
from app.execution.workspace import prepare_workspace, sandbox_command
from app.execution.output_collector import snapshot_outputs
from app.overseas.studio.execution import StudioProtocol
from app.overseas.studio.delivery import collect_delivery


def invoke(root, conversation, previous, prompt):
    settings = get_settings()
    workspace = prepare_workspace(root, conversation, uuid4(), settings.codex_auth_file)
    workspace.use_skill = False
    workspace.previous_session = previous
    workspace.baseline = snapshot_outputs(workspace.home / '.codex', previous) if previous else {}
    args = StudioProtocol().arguments(workspace)
    command = sandbox_command(workspace, settings.codex_binary, args, settings.codex_bwrap_binary)
    receipt = execute(command, prompt, workspace.control, 240, lambda: False, lambda *args: None)
    summary = parse_events(workspace.control / 'events.jsonl', previous)
    if receipt['exit_code'] != 0 or receipt['reason'] or summary.error or not summary.turn_completed:
        # Only CLI-generated diagnostics from this synthetic test; never dump auth or settings.
        print(json.dumps(dict(failed=True, receipt=receipt, summary_error=summary.error,
                              stderr=(workspace.control / 'stderr.log').read_text()[-3000:]), ensure_ascii=False))
        raise RuntimeError('Isolated CLI regression failed')
    contexts = []
    for file in (workspace.home / '.codex' / 'sessions').rglob('*.jsonl'):
        for line in file.open():
            value = json.loads(line)
            if value.get('type') == 'turn_context':
                payload = value['payload']
                contexts.append(dict(model=payload.get('model'), effort=payload.get('effort')))
    assert contexts and all(c == dict(model='gpt-6-astra', effort='high') for c in contexts), contexts
    return workspace, summary, contexts


def main():
    report = {}
    with tempfile.TemporaryDirectory(prefix='hx-astra-smoke-') as temporary:
        root = Path(temporary)
        identity, marker = uuid4(), 'HX-' + uuid4().hex
        workspace, first, contexts = invoke(root, identity, None,
            'This is an isolated deployment test. Remember this token: ' + marker +
            '. Reply with the token only. Do not call tools.')
        assert marker in first.final_text
        report['new_conversation'] = dict(session=first.session_id, contexts=contexts)
        workspace, second, contexts = invoke(root, identity, first.session_id,
            'Reply only with the exact token from my previous message. Do not call tools.')
        assert second.session_id == first.session_id and marker in second.final_text
        report['resume'] = dict(same_session=True, context_retained=True, contexts=contexts)
        workspace, third, contexts = invoke(root, identity, first.session_id,
            'Deployment image smoke test: use the native image generation tool to make exactly one '
            'simple image of a blue circle on a white background. Do not use SVG or Python to draw it. '
            'Deliver the image in your final answer with a Markdown image link to its actual local file. '
            'This is a synthetic test, no other changes needed.')
        images, warnings = collect_delivery(workspace, third)
        assert len(images) == 1 and not warnings, dict(images=len(images), warnings=warnings)
        report['image_delivery'] = dict(count=len(images), contexts=contexts,
            width=images[0][1].width, height=images[0][1].height)
        workspace, fourth, contexts = invoke(root, uuid4(), None,
            'Isolated new conversation test: no token has been provided in this conversation. '
            'Reply exactly NO_PRIOR_TOKEN and do not call tools.')
        assert fourth.session_id != first.session_id and marker not in fourth.final_text
        assert fourth.final_text.strip() == 'NO_PRIOR_TOKEN'
        report['new_session'] = dict(distinct_session=True, contexts=contexts)
    assert not root.exists()
    report['temporary_files_removed'] = True
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
