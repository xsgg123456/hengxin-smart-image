import logging

from app.modules.api_image_edits.celery_app import execute


def test_worker_boundary_never_logs_private_exception_or_replays(monkeypatch, caplog):
    calls = []
    monkeypatch.setattr('app.db.session.session_factory', lambda: object())
    monkeypatch.setattr('app.storage.minio_store.get_store', lambda: object())

    def failure(*args):
        calls.append(args)
        raise RuntimeError('SQL params: https://cdn3.dmiapi.com/image?token=private-image-token')

    monkeypatch.setattr('app.modules.api_image_edits.execution.execute_next', failure)
    with caplog.at_level(logging.ERROR):
        execute.run()
    assert len(calls) == 1
    assert 'API_IMAGE_EXECUTION_FAILED' in caplog.text
    assert 'private-image-token' not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
