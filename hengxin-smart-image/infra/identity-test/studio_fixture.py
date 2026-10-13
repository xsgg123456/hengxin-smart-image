"""Populate clearly labelled offline studio images in the disposable harness only."""
import json
import os
import sys
from hashlib import sha256
from io import BytesIO
from uuid import UUID, uuid4
from PIL import Image, ImageDraw
from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, '/workspace/backend')
import checks as h
from studio_checks import check_queued_studio


def run():
    # This module uses only checks.py's hardcoded disposable database and service endpoints.
    with h.ENGINES['overseas'].connect() as connection:
        rows = connection.execute(text("SELECT id,material_ids,name FROM overseas_tasks "
            "WHERE status='studio' ORDER BY created_at")).all()
    assert len(rows) >= 2
    base = h.BUSINESS['overseas'][0] + '/api/overseas/v1'
    with h.login('p18-designer') as designer, h.login('p19-designer2') as stranger:
        h.exchange(designer, 'overseas')
        h.exchange(stranger, 'overseas')
        test = rows[1]
        check_queued_studio(h, designer, stranger, base, {'id': str(test.id)},
                           {'id': test.material_ids[0]})
        task = rows[0]
        task_id = str(task.id)
        path = base + '/tasks/' + task_id + '/studio'
        result = h.expect(designer.post(path + '/turns', json={
            'text': '离线UI验收：这三张测试图片由本地PIL生成，未调用AI。'},
            headers={'Idempotency-Key': 'offline-ui-fixture'}), 200).json()
        turn = result['turns'][-1]
    sys.argv.append('--phase20')
    os.environ.update(h.environment('overseas'))
    from app.core.config import get_settings
    get_settings.cache_clear()
    from app.overseas.execution.models import Job
    from app.overseas.execution import claims
    from app.overseas.studio.execution import HANDLER
    from app.storage.minio_store import get_store
    from types import SimpleNamespace
    store = get_store()
    pictures = []
    for i, color in enumerate(('#2364aa', '#21897e', '#d97035'), 1):
        image = Image.new('RGB', (790, 790), color)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((240, 90, 550, 660), radius=30, fill='#e9ecef', outline='white', width=8)
        draw.rounded_rectangle((260, 115, 530, 615), radius=15, fill=color)
        draw.text((300, 280), f'TEST IMAGE {i}', fill='white')
        draw.text((225, 700), 'OFFLINE UI FIXTURE - NO AI CALL', fill='white')
        output = BytesIO()
        image.save(output, format='PNG')
        data = output.getvalue()
        identity = uuid4()
        row = dict(id=str(identity), name=f'offline-test-{i}.png', bucket=get_settings().minio_bucket,
            object_key=f'studio/fixtures/{identity}', content_type='image/png', size_bytes=len(data),
            checksum=sha256(data).hexdigest(), width=790, height=790)
        store.put(SimpleNamespace(**row), data)
        pictures.append(row)
    factory = sessionmaker(h.ENGINES['overseas'], expire_on_commit=False)
    with factory.begin() as session:
        job = claims.locked_job(session, UUID(turn['jobId']))
        assert job.status == 'queued' and job.execution_count == 0
        result = dict(sessionId='offline-ui-fixture', reply='离线界面验收：三张测试图片，未调用AI。', pictures=pictures)
        HANDLER.publish(session, job, result)
        job.process_exited = True
        claims.end(session, job, 'succeeded', result=result)
    print('STUDIO_FIXTURE ' + json.dumps(dict(taskId=task_id, turnId=turn['id'],
        pictureIds=[p['id'] for p in pictures], modelCalls=0)), flush=True)


if __name__ == '__main__':
    run()
