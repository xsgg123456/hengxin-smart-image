"""Read-only fleet discovery and narrowly scoped, non-forced image reclamation."""
import importlib.util
import json
from pathlib import Path
import subprocess

REPO = 'hengxin-smart-image-backend:'
PROJECT_LABEL = 'io.hengxin.project'
PROJECT = 'smart-image'
TOPOLOGY = {
    'domestic': ('hengxin-vps-staging', ('api', 'outbox', 'api-image-worker',
                                      'api-image-outbox', 'image-variants')),
    'overseas': ('hengxin-overseas', ('api',)),
    'identity': ('hengxin-identity', ('identity-api',)),
}


def run(*args, capture=False):
    result = subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    return result.stdout if capture else None


class Docker:
    def __init__(self, runner=run):
        self.run = runner

    def inspect(self, kind, refs):
        if not refs:
            return []
        return json.loads(self.run('docker', kind, 'inspect', *refs, capture=True))

    def containers(self):
        ids = self.run('docker', 'ps', '-aq', capture=True).split()
        return self.inspect('container', ids)

    def snapshot(self):
        containers = self.containers()
        result = {}
        for group, (project, services) in TOPOLOGY.items():
            result[group] = {}
            for service in services:
                matches = [c for c in containers
                           if c['Config'].get('Labels', {}).get('com.docker.compose.project') == project
                           and c['Config'].get('Labels', {}).get('com.docker.compose.service') == service
                           and c['State'].get('Running')]
                if len(matches) != 1:
                    raise RuntimeError('Missing or ambiguous running service: ' + group + '/' + service)
                container = matches[0]
                if container['State'].get('Health', {}).get('Status', 'healthy') != 'healthy':
                    raise RuntimeError('Unhealthy service: ' + group + '/' + service)
                result[group][service] = container['Image']
        return result

    def images(self):
        ids = self.run('docker', 'image', 'ls', '--filter', 'reference=' + REPO + '*',
                       '--no-trunc', '--quiet', capture=True).split()
        ids += self.run('docker', 'image', 'ls', '--all', '--filter',
                        'label=' + PROJECT_LABEL + '=' + PROJECT, '--filter', 'dangling=true',
                        '--no-trunc', '--quiet', capture=True).split()
        return self.inspect('image', sorted(set(ids)))

    def candidate(self, release):
        return next((i['Id'] for i in self.images() if REPO + release in (i.get('RepoTags') or [])), None)

    def resolve(self, ref):
        items = self.inspect('image', [ref])
        if len(items) != 1 or not any(t.startswith(REPO) for t in items[0].get('RepoTags') or []):
            raise RuntimeError('Previous image is not a project image')
        return items[0]['Id']

    def plan(self, data):
        live = self.snapshot()
        if set(data['groups']) != set(TOPOLOGY):
            raise RuntimeError('Initialize every group before cleanup')
        protected = {c['Image'] for c in self.containers()}
        history_ids = set()
        for group, history in data['groups'].items():
            if history['current'] != live[group] or not history['previous']:
                raise RuntimeError('Incomplete history or fleet drift: ' + group)
            protected.update(history['current'].values())
            protected.update(history['previous'].values())
            history_ids.update(history['current'].values())
            history_ids.update(history['previous'].values())
        existing = {item['Id'] for item in self.inspect('image', sorted(history_ids))}
        if existing != history_ids:
            raise RuntimeError('A retained current/previous image is missing')
        for release, pending in data['pending'].items():
            protected.add(pending.get('image'))
            protected.add(self.candidate(release))
            for values in pending.get('before', {}).values():
                protected.update(values.values())
        remove = []
        for item in self.images():
            tags = item.get('RepoTags') or []
            digests = item.get('RepoDigests') or []
            tagged = (tags and all(t.startswith(REPO) for t in tags)
                      and all(t.startswith(REPO[:-1] + '@') for t in digests))
            labels = (item.get('Config') or {}).get('Labels') or {}
            dangling = not tags and not digests and labels.get(PROJECT_LABEL) == PROJECT
            if item['Id'] not in protected and (tagged or dangling):
                remove.append({'id': item['Id'], 'tags': sorted(tags)})
        return {'remove': remove, 'protected': sorted(p for p in protected if p), 'live': live}

    def cleanup(self, data, store):
        plan = self.plan(data)
        store.report('cleanup-plan.json', plan)
        removed = []
        for item in plan['remove']:
            # Recompute references immediately before each mutation. Never force.
            current = self.plan(data)
            if item not in current['remove']:
                continue
            self.run('docker', 'image', 'rm', *(item['tags'] or [item['id']]))
            removed.append(item)
            store.report('cleanup-result.json', {'removed': removed})
        # Pending builds/preparations retain their caches as well as their images.
        if not data['pending']:
            spec = importlib.util.spec_from_file_location('release_build', Path(__file__).with_name('release-build.py'))
            builder = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(builder)
            builder.check(self.run)
            self.run('docker', 'buildx', 'prune', '--builder', builder.BUILDER,
                     '--max-used-space', '2gb', '--force')
        return removed
