from types import SimpleNamespace

import pytest

from app.overseas.studio.execution import StudioProtocol


@pytest.mark.parametrize('previous', [None, 'original-session'])
def test_studio_pins_model_and_effort_for_new_and_resumed_turns(previous):
    args = StudioProtocol().arguments(SimpleNamespace(previous_session=previous))
    assert args[args.index('--model') + 1] == 'gpt-6-astra'
    assert args[args.index('-c') + 1] == 'model_reasoning_effort="high"'
    assert args[args.index('--sandbox') + 1] == 'workspace-write'
    assert args[-1] == '-' and '--json' in args
    assert ('resume' in args) == bool(previous)
    if previous:
        assert args[-2] == previous
    assert '--last' not in args
