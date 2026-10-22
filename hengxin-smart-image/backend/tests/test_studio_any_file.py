"""Arbitrary originals round-trip through the real API and execution workspace."""
from hashlib import sha256
from io import BytesIO
from uuid import UUID
from zipfile import ZipFile

import pytest
from PIL import Image
from app.overseas.execution.models import Job
from app.overseas.studio import files, context_workspace
from test_overseas_studio import studio, send
from test_overseas_tasks import overseas, ROOT, HEADERS
from test_overseas_materials import materials
from test_studio_context_assets import workspace, original_path


@pytest.mark.parametrize('name', [
    '字体包.ZIP', 'archive.rar', 'archive.7z', 'archive.tar.gz', '品牌.ttf', '品牌.otf',
    'source.psd', 'source.ai', 'video.mp4', 'audio.mp3', 'old.doc', 'old.ppt',
    'file.custom', '无后缀文件', 'page.html', 'drawing.svg', 'script.js', 'program.exe',
    'utf16.txt', 'data.csv', 'opaque.docx', 'bad.png',
])
def test_original_upload_download_refresh_send_and_workspace(studio, tmp_path, name):
    client, factory, _, task, _, store = studio
    content = b'\xff\xfe\x00\x80\r\n<svg onload="alert(1)"></svg>'
    if name.endswith('ZIP'):
        buffer = BytesIO()
        with ZipFile(buffer, 'w') as archive:
            archive.writestr('fonts/sample.ttf', content)
        content = buffer.getvalue()
    base = ROOT + '/tasks/' + task['id'] + '/studio'
    response = client.post(base + '/files', files={'file': (name, content, 'text/html')}, headers=HEADERS)
    assert response.status_code == 200, response.text
    asset = response.json()
    assert asset['name'].casefold() == name.casefold()
    assert not asset['contentType'].startswith('image/')
    download = client.get(asset['url'])
    assert download.content == content
    assert download.headers['content-disposition'].startswith('attachment;')
    assert download.headers['x-content-type-options'] == 'nosniff'
    assert client.get(asset['url'] + '?preview=true').status_code == 422
    assert any(a['id'] == asset['id'] for a in client.get(base).json()['materials'])
    result = send(client, task, attachmentIds=[asset['id']])
    assert result.status_code == 200, result.text
    turn = result.json()['turns'][-1]
    with factory() as session:
        inputs = session.get(Job, UUID(turn['jobId'])).payload['inputs']
    assert inputs[0]['checksum'] == sha256(content).hexdigest()
    ws = workspace(tmp_path)
    paths = context_workspace.prepare(ws, [], inputs, lambda data: content)
    assert original_path(ws, paths[0]).read_bytes() == content
    assert turn['attachments'][0]['id'] == asset['id']


def test_preview_validation_does_not_reject_original_and_names_stay_safe():
    data = BytesIO()
    Image.new('RGB', (2, 2), 'red').save(data, format='PNG')
    assert files.validate(data.getvalue(), 'image.PNG')[1] == 'image/png'
    assert files.validate(b'<script>alert(1)</script>', 'fake.png')[1] == 'application/octet-stream'
    name, kind = files.validate(b'original', '../font.bad\r\nX-Evil:1')
    assert '\r' not in name and '\n' not in name and '/' not in name and ':' not in name
    assert kind == 'application/octet-stream'


def test_unknown_file_nonempty_and_size_limits(monkeypatch):
    monkeypatch.setattr(files, 'MAX_BYTES', 8)
    assert files.validate(b'12345678', 'file.unknown')[1] == 'application/octet-stream'
    for data, status in [(b'', 422), (b'123456789', 413)]:
        with pytest.raises(files.HTTPException) as caught:
            files.validate(data, 'file.unknown')
        assert caught.value.status_code == status
