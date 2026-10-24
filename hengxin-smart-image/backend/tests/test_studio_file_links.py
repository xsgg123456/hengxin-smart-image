"""External URLs remain browser links and never become server fetches."""
import pytest
from test_studio_formal_delivery import space, collect


@pytest.mark.parametrize('target', ['https://example.invalid/result.png',
    'http://127.0.0.1/private.zip', '//example.invalid/file.bin'])
def test_external_links_are_not_local_output_candidates_or_fetch_requests(space, target, monkeypatch):
    from app.overseas.studio import delivery
    def forbidden(*args, **kwargs):
        raise AssertionError('external reference must never read a file')
    monkeypatch.setattr(delivery, 'collect_reference', forbidden)
    assert collect(space, f'![图片]({target}) [下载]({target})') == ([], [])
