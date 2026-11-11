"""Explicit isolated Docker GC validation; never starts a test container."""
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import tarfile
import tempfile
import uuid

import engine
import image_gc
from release import retention_store


def run():
    if socket.gethostname() != 'hengxin-ai-245' or os.geteuid() != 0:
        raise RuntimeError('Only root on hengxin-ai-245 is supported')
    u = engine.u
    marker = uuid.uuid4().hex
    label = 'hengxin.retention-smoke=' + marker
    created, container = [], None
    initial_images = image_gc.images(u)
    initial_containers = {c['Id']: c['Image'] for c in image_gc.containers(u)}
    current = image_gc.capture(u)
    try:
        for name in ('old', 'previous', 'stopped', 'unknown'):
            raw = (marker + name).encode()
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode='w') as tar:
                item = tarfile.TarInfo('retention-smoke-marker')
                item.size = len(raw)
                tar.addfile(item, io.BytesIO(raw))
            p = subprocess.run(['docker', 'import', '--change', 'LABEL ' + label, '-'],
                               input=stream.getvalue(), capture_output=True, timeout=60, check=True)
            identity = image_gc.image_id(p.stdout.decode().strip())
            if identity in initial_images:
                raise RuntimeError('Test image collided with existing image')
            created.append(identity)
        old, previous, stopped, unknown = created
        container = u.run(['docker', 'create', '--label', label, '--name',
                           'retention-smoke-' + marker, stopped, '/never-executed']).strip()
        prior = dict(current, **{'domestic-web': previous})
        with tempfile.TemporaryDirectory(prefix='hengxin-image-smoke-', dir='/var/tmp') as folder:
            store = retention_store(Path(folder))
            with store.locked():
                result = image_gc.execute(u, store, current, prior,
                                          {old, previous, stopped}, apply=True)
            assert result['status'] == 'complete' and result['deleted'] == [old]
            assert {previous, stopped, unknown} <= image_gc.images(u)
            assert initial_images <= image_gc.images(u)
            summary = dict(status='PASS', old_deleted=True, previous_kept=True,
                           stopped_container_kept=True, unknown_kept=True,
                           released_layer_bytes=result['released_bytes'])
    finally:
        if container:
            row = json.loads(u.run(['docker', 'inspect', container]))[0]
            assert row['Config']['Labels']['hengxin.retention-smoke'] == marker
            assert not row['State']['Running']
            u.run(['docker', 'rm', container])
        for identity in created:
            if identity not in image_gc.images(u):
                continue
            row = json.loads(u.run(['docker', 'image', 'inspect', identity]))[0]
            assert row['Config']['Labels']['hengxin.retention-smoke'] == marker
            u.run(['docker', 'image', 'rm', '--no-prune', identity])
        assert image_gc.images(u) == initial_images
        assert {c['Id']: c['Image'] for c in image_gc.containers(u)} == initial_containers
    summary.update(test_objects_remaining=0, production_images=len(initial_images),
                   production_containers=len(initial_containers))
    print(json.dumps(summary))


if __name__ == '__main__':
    run()
