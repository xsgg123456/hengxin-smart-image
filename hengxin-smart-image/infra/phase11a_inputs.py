"""Read-only export of explicitly selected development inputs for an isolated test."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from uuid import UUID

import httpx
from minio import Minio
from sqlalchemy import create_engine, text

from local_codex_worker import configuration


def export(task_id, output):
    task_id = str(UUID(task_id))
    infra = Path(__file__).resolve().parent
    config = configuration(infra / '.env', infra / '.env.local-codex')
    assert config['APP_ENV'] in ('test', 'development')
    output.mkdir(parents=True, exist_ok=False)
    os.chmod(output, 0o700)
    with httpx.Client(base_url='http://127.0.0.1:8008', trust_env=False, timeout=30) as client:
        response = client.get('/api/v1/tasks/' + task_id)
        response.raise_for_status()
        detail = response.json()
        task = detail['task']
        assert task['executionSource'] == 'cli' and task['mode'] == 'wallpaper'
        pictures = [('target-1', task['templateSnapshot']['images'][0]),
                    ('target-2', task['templateSnapshot']['images'][1]), ('source', task['sources'][0])]
        evidence = {'sourceTask': task_id, 'skillVersionId': task['skillVersionId'], 'files': []}
        for name, picture in pictures:
            file_id = str(UUID(picture['fileId']))
            data = client.get('/api/v1/files/' + file_id + '/content')
            data.raise_for_status()
            assert 0 < len(data.content) <= 10 * 1024 * 1024
            mime = data.headers['content-type'].split(';')[0]
            extension = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}[mime]
            filename = name + extension
            (output / filename).write_bytes(data.content)
            evidence['files'].append({'name': filename, 'mime': mime, 'fileId': file_id,
                                      'sha256': hashlib.sha256(data.content).hexdigest()})
    engine = create_engine(config['DATABASE_URL'])
    try:
        with engine.begin() as connection:
            connection.execute(text('SET TRANSACTION READ ONLY'))
            row = connection.execute(text('SELECT bucket, object_key, checksum, version, status '
                'FROM skill_versions WHERE id = :id'), {'id': UUID(task['skillVersionId'])}).mappings().one()
            assert row['status'] == 'available'
        store = Minio(config['MINIO_ENDPOINT'], access_key=config['MINIO_ACCESS_KEY'],
                      secret_key=config['MINIO_SECRET_KEY'], secure=False)
        response = store.get_object(row['bucket'], row['object_key'])
        try:
            package = response.read(64 * 1024 * 1024 + 1)
        finally:
            response.close()
            response.release_conn()
        assert len(package) <= 64 * 1024 * 1024
        assert hashlib.sha256(package).hexdigest() == row['checksum']
        (output / 'skill.zip').write_bytes(package)
        evidence.update(skillVersion=row['version'], skillChecksum=row['checksum'])
    finally:
        engine.dispose()
    (output / 'inputs.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'exportedFiles': len(pictures), 'skillVersion': evidence['skillVersion'],
                      'sourceReadOnly': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        export(args.task_id, args.output)
    except Exception as error:
        print('Input export failed: ' + type(error).__name__, file=sys.stderr)
        sys.exit(1)
