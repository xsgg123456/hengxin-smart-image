import hashlib
import io
from pathlib import Path
import sys
import zipfile

import httpx
import pytest
from PIL import Image, UnidentifiedImageError

sys.path.insert(0, str(Path(__file__).parents[2] / 'infra'))
from phase11a_checks import image_evidence, Evidence


def test_download_proof_validates_image_and_zip_bytes(tmp_path):
    stream = io.BytesIO()
    Image.new('RGB', (17, 23), 'orange').save(stream, format='PNG')
    raw = stream.getvalue()
    with httpx.Client(base_url='http://isolated.test', transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=raw))) as client:
        result = image_evidence(client, [{'url': '/image', 'fileId': 'one'}], tmp_path, 'proof')
    assert result == [{'fileId': 'one', 'sha256': hashlib.sha256(raw).hexdigest(),
                       'size': [17, 23], 'format': 'PNG'}]
    with zipfile.ZipFile(tmp_path / 'proof.zip') as archive:
        assert archive.read('proof-1.png') == raw


def test_http_success_with_non_image_cannot_count_as_generation(tmp_path):
    with httpx.Client(base_url='http://isolated.test', transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=b'<html>error</html>'))) as client:
        with pytest.raises(UnidentifiedImageError):
            image_evidence(client, [{'url': '/image'}], tmp_path, 'invalid')
    assert not (tmp_path / 'invalid.zip').exists()


def test_acceptance_rejects_duplicate_or_unfinished_invocations():
    evidence = Evidence.__new__(Evidence)
    evidence.attempts = lambda _: [{'execution_count': 2, 'status': 'finished'}]
    with pytest.raises(RuntimeError, match='Duplicate'):
        evidence.round_evidence('task')
    evidence.attempts = lambda _: [{'execution_count': 1, 'status': 'running'}]
    with pytest.raises(RuntimeError, match='did not finish'):
        evidence.round_evidence('task')


def invocation(**changes):
    return dict({'id': 'attempt', 'round_id': 'round', 'execution_count': 1, 'status': 'finished',
                 'process_id': 999999999, 'process_start': 'birth', 'cli_version': '0.153.4'}, **changes)


def test_attempt_uniqueness_is_independent_of_job_execution_count():
    evidence = Evidence.__new__(Evidence)
    evidence.samples = []
    evidence.attempts = lambda _: [invocation(), invocation(id='second')]
    with pytest.raises(RuntimeError, match='Duplicate attempt'):
        evidence.round_evidence('task')


@pytest.mark.parametrize('missing', ['process_id', 'process_start', 'cli_version'])
def test_missing_execution_identity_cannot_pass(missing):
    evidence = Evidence.__new__(Evidence)
    evidence.samples = []
    evidence.attempts = lambda _: [invocation(**{missing: None})]
    with pytest.raises(RuntimeError, match='Missing CLI'):
        evidence.round_evidence('task')


def test_expected_rounds_must_match_exactly():
    evidence = Evidence.__new__(Evidence)
    evidence.samples = []
    evidence.attempts = lambda _: [invocation()]
    with pytest.raises(RuntimeError, match='Unexpected round'):
        evidence.round_evidence('task', ['round', 'missing-round'])
    assert len(evidence.round_evidence('task', ['round'])) == 1


@pytest.mark.parametrize('field', ['status', 'round_status', 'job_status'])
def test_timeout_receipt_cannot_hide_unfinished_business_state(field):
    from phase11a_faults import validate_stop
    row = {'status': 'finished', 'round_status': 'failed', 'job_status': 'failed'}
    row[field] = 'running'
    with pytest.raises(RuntimeError, match='terminal states'):
        validate_stop([row], {'reason': 'timeout', 'exit_code': -15, 'elapsed_seconds': 10}, 'timeout')


@pytest.mark.parametrize('elapsed', [0.2, 35])
def test_timeout_receipt_requires_expected_duration(elapsed):
    from phase11a_faults import validate_stop
    row = {'status': 'finished', 'round_status': 'failed', 'job_status': 'failed'}
    with pytest.raises(RuntimeError, match='tolerance'):
        validate_stop([row], {'reason': 'timeout', 'exit_code': -15, 'elapsed_seconds': elapsed}, 'timeout')


def test_correct_stop_receipts_pass():
    from phase11a_faults import validate_stop
    for reason, terminal, elapsed in [('timeout', 'failed', 10.189), ('cancelled', 'cancelled', .235)]:
        validate_stop([{'status': 'finished', 'round_status': terminal, 'job_status': terminal}],
                      {'reason': reason, 'exit_code': -15, 'elapsed_seconds': elapsed}, reason)
