"""Restore a closed HTTP gate only for a fully verified, already live release."""
import catalog
import joint_studio_marker as marker
import joint_studio_paths as paths
import scopes
import snapshot


def restore(tool):
    # Caller holds the standard host release lock. This does not resume migration.
    data = tool.load()
    row = marker.read(tool.u, tool.store)
    if (data.get('version') != 2 or data.get('pending') or data.get('migration_pending')
            or not row or row['phase'] != 'complete'
            or not scopes.has_domestic_publisher(data['current'])):
        raise RuntimeError('Ingress restoration requires a completed, idle Studio release')
    if not paths.gate_state(tool.u, 'workers'):
        raise RuntimeError('Background gate is closed; use migration recovery')
    was_open = paths.gate_state(tool.u, 'ingress')
    snapshot.same(data['current'], tool.capture(data, runtime=True))
    catalog.before(tool.u, tool.store, data)
    if tool.load() != data or marker.read(tool.u, tool.store) != row:
        raise RuntimeError('Release state changed during ingress verification')
    if (not paths.gate_state(tool.u, 'workers')
            or paths.gate_state(tool.u, 'ingress') != was_open):
        raise RuntimeError('Release gates changed during verification')
    if not was_open:
        receipt = {'state_sha256': catalog.state_sha(data['current']), 'phase': 'verified'}
        tool.store.report('ingress-restore-last.json', receipt)
        paths.set_gate(tool.u, 'ingress', True)
        tool.store.report('ingress-restore-last.json', dict(receipt, phase='opened'))
    return data
