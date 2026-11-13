"""Cleanup after verified success; all categories use the same two deployments."""
import time

import artifact_gc
import catalog
import cleanup
import image_gc
import snapshot


def execute(u, store, data, apply=False):
    import joint_studio_marker
    joint_studio_marker.guard(u, store)
    if data.get('pending'):
        raise RuntimeError('Pending release blocks cleanup')
    if data.get('migration_pending'):
        raise RuntimeError('Unverified migration blocks cleanup')
    snapshot.same(data['current'], snapshot.capture_for(u, data, runtime=True))
    # Include the ledger/receipts, transactions, sources and LAN publication files
    # exactly once. Docker reports deduplicated layers separately.
    roots = [snapshot.RELEASES, u.ROOT, store.root]
    before = artifact_gc.allocated(roots) + image_gc.layer_bytes(u)
    data = catalog.before(u, store, data)
    value = catalog.check(data)
    sources, paths = catalog.protected(data)
    if data.get('version') == 2:
        from scope_catalog import image_references
        from scopes import has_domestic_publisher
        fleet, current, previous = image_gc.scoped(u, has_domestic_publisher(data['current'])), data['current']['images'], None
        extra = {'extra_retained': image_references(data)}
    else:
        fleet, current = u, value['current']['images']
        previous, extra = value['previous']['images'] if value['previous'] else None, {}
    report = dict(status='preview', time_ns=time.time_ns(), before_bytes=before,
                  bytes_scope='release-sources+lan-root+ledger+docker-LayersSize',
                  unowned=value['unowned'], results={})
    if apply:
        # Ownership must survive deletion of the original transaction evidence.
        store.report('intranet.json', data)
    tasks = {
        'sources': lambda: cleanup.execute(u, store, data, apply=apply),
        'images': lambda: image_gc.execute(fleet, store, current, previous,
            set(value['known_images']), apply=apply, **extra),
        'artifacts': lambda: artifact_gc.execute(u, store, value['artifacts'], sources, paths, apply=apply),
    }
    for name, task in tasks.items():
        try:
            report['results'][name] = task()
        except Exception as exc:
            report['results'][name] = dict(status='warning', error=type(exc).__name__, deleted=[])
    report['status'] = ('warning' if any(r['status'] == 'warning' for r in report['results'].values())
                        else 'complete' if apply else 'preview')
    if apply:
        # Keep only compact no-reuse tombstones once large manifests are no
        # longer needed for partial-deletion recovery.
        for path in report['results']['artifacts'].get('deleted', []):
            item = value['artifacts'][path]
            item['proof'] = {k: item['proof'][k] for k in ('path', 'kind')}
            item['proof']['deleted'] = True
            item['owners'] = []
        store.report('intranet.json', data)
        report.update(after_bytes=0, net_released_bytes=0)
        for _ in range(3):
            store.report('intranet-complete-cleanup.json', report)
            report['after_bytes'] = artifact_gc.allocated(roots) + image_gc.layer_bytes(u)
            report['net_released_bytes'] = before - report['after_bytes']
        store.report('intranet-complete-cleanup.json', report)
    return report
