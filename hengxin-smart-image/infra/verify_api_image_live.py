"""Two-image, paid upstream smoke test through a dedicated local platform instance.

Requires its own disposable DB/store and API_IMAGE_API_KEY on the worker, not here.
Never run against the production host. Prints only task IDs, counts and safe states.
"""
import argparse
import io
import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from PIL import Image, ImageDraw


def request(base, path, method='GET', body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    req = Request(base + path, data=data, method=method,
                  headers={'Content-Type': 'application/json', **(headers or {})})
    with urlopen(req, timeout=15) as response:
        return json.load(response)


def upload(base, name, data):
    boundary = 'api-image-smoke-' + uuid4().hex
    payload = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
               'Content-Type: image/png\r\n\r\n').encode() + data + f'\r\n--{boundary}--\r\n'.encode()
    req = Request(base + '/files', data=payload,
                  headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    with urlopen(req, timeout=20) as response:
        return json.load(response)


def sample(index):
    image = Image.new('RGB', (512, 512), 'white')
    draw = ImageDraw.Draw(image)
    if index == 2:
        draw.rectangle((0, 0, 512, 512), fill='#446cbd')
        draw.ellipse((145, 145, 367, 367), fill='#ffd858')
    else:
        draw.rounded_rectangle((140 + index * 10, 60, 372 - index * 10, 452), radius=20,
                               fill='#aaaaaa', outline='#333333', width=8)
    data = io.BytesIO(); image.save(data, 'PNG')
    return data.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--api-url', default='http://127.0.0.1:8009')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    target = urlsplit(args.api_url)
    if target.hostname not in ('127.0.0.1', 'localhost') or target.port != 8009:
        raise SystemExit('This paid smoke test only accepts the dedicated localhost:8009 instance')
    origin = args.api_url.rstrip('/')
    base = origin + '/api/v1/api-image-edits'
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    status = request(base, '/status')
    assert status['enabled'] and not status['paused'], status
    pictures = [upload(base, f'smoke-{index}.png', sample(index)) for index in range(3)]
    body = {'name': 'API独立通道真实双图验收', 'prompt':
            'Replace only the gray rectangle interior in the first image with the blue and gold '
            'pattern from the second image. Preserve the outline and white background. Return one image.',
            'originalFileIds': [picture['fileId'] for picture in pictures[:2]],
            'materialFileId': pictures[2]['fileId']}
    headers = {'Idempotency-Key': 'live-' + uuid4().hex}
    task_id = request(base, '/tasks', 'POST', body, headers)['taskId']
    assert request(base, '/tasks', 'POST', body, headers)['taskId'] == task_id
    print(json.dumps({'taskId': task_id, 'submitted': 2, 'duplicateSubmitSameTask': True}), flush=True)
    deadline, previous = time.monotonic() + 600, None
    while time.monotonic() < deadline:
        task = request(base, '/tasks/' + task_id)
        states = [item['state'] for item in task['items']]
        current = (task['status'], states)
        if current != previous:
            print(json.dumps({'status': current[0], 'items': states}), flush=True)
            previous = current
        if task['status'] in ('succeeded', 'partial_failed', 'failed', 'uncertain'):
            break
        time.sleep(2)
    assert task['status'] == 'succeeded', {'taskId': task_id, 'status': task['status'], 'error': task.get('error')}
    assert [item['position'] for item in task['items']] == [1, 2]
    results = []
    for item in task['items']:
        path = item['result']['url']
        assert path.startswith('/api/v1/api-image-edits/files/')
        with urlopen(origin + path, timeout=20) as response:
            image_bytes = response.read(30 * 1024 * 1024 + 1)
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.load()
            results.append({'position': item['position'], 'width': image.width, 'height': image.height})
        (output / f'result-{item["position"]}.png').write_bytes(image_bytes)
    assert request(base, '/tasks', 'POST', body, headers)['taskId'] == task_id
    assert request(base, '/tasks/' + task_id)['metrics']['requestCount'] == task['metrics']['requestCount']
    evidence = {'taskId': task_id, 'status': task['status'], 'metrics': task['metrics'],
                'results': results, 'idempotentSubmit': True}
    (output / 'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(evidence, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
