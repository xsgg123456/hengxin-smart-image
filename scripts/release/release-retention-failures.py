"""Retire superseded pre-deployment failures using verified per-business epochs."""
from copy import deepcopy

GROUPS = ('domestic', 'overseas', 'identity')


def scope(release, pending):
    group = next((g for g in GROUPS if release.startswith(g + '-') and len(release) > len(g) + 1), None)
    if pending.get('phase') == 'failed' and 'before' not in pending and group in GROUPS:
        return group
    return None


def record(data, release):
    """A retry failure must start a fresh baseline, never reuse an old epoch."""
    pending = data['pending'][release]
    pending.pop('failedAtSuccess', None)
    group = scope(release, pending)
    if group:
        pending['failedAtSuccess'] = {group: data.get('successCounters', {}).get(group, 0)}


def seed_legacy(data):
    changed = False
    for release, pending in data['pending'].items():
        if scope(release, pending) and 'failedAtSuccess' not in pending:
            record(data, release)
            changed = True
    return changed


def referenced(data, docker, excluding):
    protected = {c['Image'] for c in docker.containers()}
    for history in data['groups'].values():
        for images in history.values():
            protected.update(images.values())
    for release, pending in data['pending'].items():
        if release == excluding:
            continue
        protected.update((pending.get('image'), docker.candidate(release)))
        for images in pending.get('before', {}).values():
            protected.update(images.values())
    protected.discard(None)
    return protected


def preview(data, store, docker):
    eligible = []
    for release, pending in data['pending'].items():
        group = scope(release, pending)
        baseline = pending.get('failedAtSuccess', {})
        if not group or set(baseline) != {group}:
            continue
        if data.get('successCounters', {}).get(group, 0) <= baseline[group]:
            continue
        # Even a failed bookkeeping step can have a valid success receipt.
        if (store.root / ('verified-' + release + '.json')).exists():
            continue
        ids = {pending.get('image'), docker.candidate(release)} - {None}
        if ids & referenced(data, docker, release):
            continue
        eligible.append(release)
    if eligible:
        docker.plan(data)  # All groups healthy, history complete and live state unchanged.
    return sorted(eligible)


def retire(data, store, docker):
    """Caller holds the shared release lock; preview never mutates the ledger."""
    if seed_legacy(data):
        store.write(data)
    for release in preview(data, store, docker):
        # Re-read references before each state mutation, just like image removal.
        if release not in preview(data, store, docker):
            continue
        updated = deepcopy(data)
        pending = updated['pending'].pop(release)
        group = scope(release, pending)
        updated.setdefault('retiredFailures', {})[release] = {
            'pending': pending, 'reason': 'superseded-by-verified-release',
            'successCounters': {group: data['successCounters'][group]},
        }
        store.write(updated)  # Audit and unpin are one atomic durable write.
        data.clear()
        data.update(updated)
