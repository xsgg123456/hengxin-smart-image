import sys

import pytest

from process_group_linux_probe import run


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='requires real Linux /proc and process groups')
def test_real_process_group_survives_leader_exit():
    run()
