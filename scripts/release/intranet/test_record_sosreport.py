import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import record_sosreport_20261118 as record


def test_reports_only_exact_single_package_change(monkeypatch):
    def raw(version):
        return json.dumps([['sos', version], ['unrelated', '1']]) + '\n'
    monkeypatch.setattr(record, 'OLD', record.snapshot.sha(raw('4.10.2').encode()))
    monkeypatch.setattr(record, 'NEW', record.snapshot.sha(raw('4.11.2').encode()))
    record.check_packages(raw('4.11.2'))
    with pytest.raises(RuntimeError):
        record.check_packages(raw('4.11.2').replace('unrelated', 'changed'))


@pytest.mark.parametrize('drift', [False, True])
def test_save_only_matches_verified_snapshot(tmp_path, monkeypatch, drift):
    before = {'native': {record.ACCOUNT: {'packages': record.OLD}}, 'unrelated': 1}
    after = copy.deepcopy(before)
    after['native'][record.ACCOUNT]['packages'] = record.NEW
    data = dict(version=2, pending=None, current=before, groups={'shared': {'current': 1, 'previous': 2}})
    u = Mock()
    u.run.side_effect = ['4.11.2-0ubuntu0~24.04.2', '']
    u.contexts.return_value = {record.ACCOUNT: {}}
    tool = SimpleNamespace(u=u, store=SimpleNamespace(root=tmp_path), load=lambda: data,
                           save=Mock(), capture=lambda *a, **k: dict(after, unrelated=2) if drift else after)
    for module in (record.codex_runtime_marker, record.domestic_tasks_marker, record.joint_studio_marker):
        monkeypatch.setattr(module, 'guard', Mock())
    monkeypatch.setattr(record.scope_catalog, 'check', Mock())
    monkeypatch.setattr(record.scope_catalog, 'seal', Mock())
    monkeypatch.setattr(record.scope_snapshot, 'group', lambda state, name: state['native'])
    monkeypatch.setattr(record, 'check_packages', Mock())
    if drift:
        with pytest.raises(RuntimeError, match='drift'):
            record.record(tool)
        tool.save.assert_not_called()
    else:
        record.record(tool)
        saved = tool.save.call_args.args[0]
        assert saved['current'] == after
        assert saved['groups']['shared']['previous'] == 2
        assert data['current']['native'][record.ACCOUNT]['packages'] == record.OLD
