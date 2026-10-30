"""Thumbnail resource and failure tests require no database or external services."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
from threading import Event
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from PIL import Image
from app.overseas import thumbnails, image_delivery
from test_overseas_materials import MemoryStore


@pytest.fixture(autouse=True)
def empty_cache(monkeypatch):
    monkeypatch.setattr(thumbnails, '_cache', OrderedDict())
    monkeypatch.setattr(thumbnails, '_cache_bytes', 0)


def source(size=(800, 400), mode='RGB', color='red', format='PNG', **options):
    buffer = BytesIO()
    with Image.new(mode, size, color) as image:
        image.save(buffer, format=format, **options)
    data = buffer.getvalue()
    row = SimpleNamespace(id=uuid4(), bucket='test', object_key=uuid4().hex, name='source.png',
        content_type={'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}[format],
        size_bytes=len(data), checksum=sha256(data).hexdigest())
    store = MemoryStore()
    store.put(row, data)
    return store, row, data


@pytest.mark.parametrize('format', ['PNG', 'JPEG', 'WEBP'])
def test_original_format_bytes_kept_and_thumbnail_dimensions(format):
    store, row, data = source(format=format)
    response = image_delivery.deliver(store, row, thumbnail=True)
    with Image.open(BytesIO(response.body)) as image:
        assert image.size == (384, 192) and image.format == 'WEBP'
    assert image_delivery.deliver(store, row).body == data
    assert store.data[row.object_key] == data


def test_transparency_and_exif_orientation():
    store, row, _ = source(mode='RGBA', color=(255, 0, 0, 0))
    with Image.open(BytesIO(thumbnails.render(store, row))) as image:
        assert image.getpixel((0, 0))[3] == 0
    exif = Image.Exif()
    exif[274] = 6
    store, row, _ = source(format='JPEG', exif=exif)
    with Image.open(BytesIO(thumbnails.render(store, row))) as image:
        assert image.size == (192, 384)


@pytest.mark.parametrize('limit,status', [('bytes', 413), ('pixels', 413), ('result', 413)])
def test_input_and_result_limits_release_capacity_and_preserve_original(monkeypatch, limit, status):
    store, row, data = source(size=(4, 4))
    setting = {'bytes': 'MAX_SOURCE_BYTES', 'pixels': 'MAX_PIXELS', 'result': 'MAX_RESULT_BYTES'}[limit]
    monkeypatch.setattr(thumbnails, setting, 1)
    with pytest.raises(HTTPException) as caught:
        thumbnails.render(store, row)
    assert caught.value.status_code == status
    assert not thumbnails._cache and store.data[row.object_key] == data
    assert thumbnails._workers.acquire(blocking=False)
    thumbnails._workers.release()


def test_invalid_and_animated_images_fail_without_changing_source():
    store, row, _ = source()
    store.data[row.object_key] = b'not image'
    row.size_bytes, row.checksum = len(b'not image'), sha256(b'not image').hexdigest()
    with pytest.raises(HTTPException) as caught:
        thumbnails.render(store, row)
    assert caught.value.status_code == 422 and not thumbnails._cache
    buffer = BytesIO()
    first, second = Image.new('RGB', (8, 8), 'red'), Image.new('RGB', (8, 8), 'blue')
    first.save(buffer, format='PNG', save_all=True, append_images=[second])
    data = buffer.getvalue()
    store.put(row, data)
    row.size_bytes, row.checksum = len(data), sha256(data).hexdigest()
    with pytest.raises(HTTPException) as caught:
        thumbnails.render(store, row)
    assert caught.value.status_code == 422
    assert image_delivery.deliver(store, row).body == data


def test_two_running_conversions_reject_third_and_release_slots(monkeypatch):
    monkeypatch.setattr(thumbnails, 'WORKER_WAIT_SECONDS', 0.02)
    sources = [source() for _ in range(3)]
    entered = [Event(), Event()]
    release = Event()
    original = thumbnails.original_bytes
    def delayed(store, row, limit):
        index = next(i for i, item in enumerate(sources) if item[1] is row)
        entered[index].set()
        assert release.wait(5)
        return original(store, row, limit)
    monkeypatch.setattr(thumbnails, 'original_bytes', delayed)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(thumbnails.render, store, row) for store, row, _ in sources[:2]]
        try:
            assert all(event.wait(5) for event in entered)
            with pytest.raises(HTTPException) as caught:
                thumbnails.render(*sources[2][:2])
            assert caught.value.status_code == 429 and caught.value.headers['Retry-After'] == '1'
        finally:
            release.set()
        assert all(future.result(timeout=5) for future in futures)
    monkeypatch.setattr(thumbnails, 'original_bytes', original)
    assert thumbnails.render(*sources[2][:2])


def test_waiting_conversion_starts_after_capacity_is_released(monkeypatch):
    store, row, _ = source()
    waiting = Event()
    original_acquire = thumbnails._workers.acquire
    class ObservedSlots:
        def acquire(self, **kwargs):
            waiting.set()
            return original_acquire(**kwargs)
        def release(self):
            slots.release()
    slots = thumbnails._workers
    assert original_acquire(blocking=False) and original_acquire(blocking=False)
    monkeypatch.setattr(thumbnails, '_workers', ObservedSlots())
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(thumbnails.render, store, row)
        try:
            assert waiting.wait(1)
            assert not future.done()
        finally:
            slots.release()
            slots.release()
        assert future.result(timeout=3)


@pytest.mark.parametrize('bound', ['items', 'bytes'])
def test_lru_is_bounded_and_evicted_entries_can_regenerate(monkeypatch, bound):
    sources = [source(color=color) for color in ('red', 'green', 'blue')]
    sizes = [len(thumbnails.render(store, row)) for store, row, _ in sources]
    thumbnails._cache.clear()
    thumbnails._cache_bytes = 0
    if bound == 'items':
        monkeypatch.setattr(thumbnails, 'CACHE_ITEMS', 2)
    else:
        monkeypatch.setattr(thumbnails, 'CACHE_BYTES', max(sizes) * 2)
    for store, row, _ in sources:
        thumbnails.render(store, row)
    assert len(thumbnails._cache) == 2
    assert thumbnails._cache_bytes == sum(len(value) for value in thumbnails._cache.values())
    assert not any(key[1] == sources[0][1].object_key for key in thumbnails._cache)
    assert thumbnails.render(*sources[0][:2])
    assert len(thumbnails._cache) == 2
