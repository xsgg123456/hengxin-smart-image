"""Executed only inside the disposable *_test database container environment."""
import hashlib
import json
import os
import sys
from io import BytesIO
from uuid import uuid4

from PIL import Image
from sqlalchemy import text

import app.main  # register all existing models
from app.core.config import get_settings
from app.db.session import get_engine, session_factory
from app.models import Base
from app.modules.auth.sessions import issue_session
from app.modules.api_image_edits.models import ApiFile, ApiTask, ApiItem
from app.resource_models import FileRecord, UserRecord
from app.storage.minio_store import get_store


settings = get_settings()
assert settings.app_env == 'test' and get_engine().url.database.endswith('_test')
assert settings.minio_bucket.startswith('media-test-')

if len(sys.argv) > 1:
    # Commands contain only generated UUIDs; credentials never enter output.
    with session_factory().begin() as session:
        if sys.argv[1] == 'disable':
            user = session.get(UserRecord, sys.argv[2]); user.status = sys.argv[3]
        elif sys.argv[1] == 'idle':
            print(session.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND state='idle in transaction'")))
        elif sys.argv[1] == 'remove':
            model = FileRecord if sys.argv[2] == 'originals' else ApiFile
            get_store().remove(session.get(model, sys.argv[3]))
        elif sys.argv[1] == 'policy':
            client = get_store().client
            if sys.argv[2] == 'public':
                policy = {'Version': '2012-10-17', 'Statement': [{'Effect': 'Allow', 'Principal': {'AWS': ['*']},
                          'Action': ['s3:GetObject'], 'Resource': [f'arn:aws:s3:::{settings.minio_bucket}/*']}]}
                client.set_bucket_policy(settings.minio_bucket, json.dumps(policy))
            else:
                client.delete_bucket_policy(settings.minio_bucket)
        else:
            raise ValueError('unknown fixture action')
    sys.exit(0)

Base.metadata.create_all(get_engine())
store = get_store()
user_id = uuid4()
manifest = {'uid': str(user_id), 'images': []}
with session_factory().begin() as session:
    session.add(UserRecord(id=user_id, name='媒体隔离测试', role='operator', status='active', identity_source='development'))
    session.flush()
    manifest['token'] = issue_session(session, user_id)
    for domain, model in [('originals', FileRecord), ('api-image-edits', ApiFile)]:
        for large in (False, True):
            size = (1536, 1536) if large else (8, 6)
            image = Image.frombytes('RGB', size, os.urandom(size[0] * size[1] * 3)) if large else Image.new('RGB', size, '#012345')
            buffer = BytesIO(); image.save(buffer, format='PNG'); data = buffer.getvalue()
            identifier = uuid4()
            record = model(id=identifier, owner_id=user_id, name='原件测试.png', bucket=settings.minio_bucket,
                           object_key=f'{domain}/{identifier}', content_type='image/png', size_bytes=len(data),
                           checksum=hashlib.sha256(data).hexdigest(), width=size[0], height=size[1], status='ready')
            session.add(record); store.put(record, data)
            prefix = '/api/v1/' + ('api-image-edits/' if domain != 'originals' else '')
            manifest['images'].append({'id': str(identifier), 'path': prefix + f'files/{identifier}/content',
                                       'domain': domain, 'large': large, 'size': len(data), 'sha256': record.checksum})
            if domain == 'api-image-edits':
                task = ApiTask(id=uuid4(), owner_id=user_id, operator_id=user_id, name='整套测试', prompt='fixture',
                               material_id=identifier, parameters={}, state='succeeded')
                session.add(task); session.flush()
                for position in range(1, 21 if large else 2):
                    session.add(ApiItem(task_id=task.id, source_id=identifier, result_id=identifier, position=position, state='succeeded'))
                manifest['large_zip' if large else 'zip'] = f'/api/v1/api-image-edits/tasks/{task.id}/zip'
print(json.dumps(manifest))
