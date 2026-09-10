"""Contract drift checks against the checked-in frontend declarations."""
import re
from pathlib import Path
import pytest
from pydantic import ValidationError

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.contracts import business, management
from app.contracts.router import router


def contract_app():
    app = FastAPI()
    app.include_router(router, prefix='/api/v1')
    return app


def test_business_contracts_are_explicitly_unimplemented():
    client = TestClient(contract_app())
    for path in ['/workspace', '/archives',
                 '/management/users', '/management/settings', '/management/monitor']:
        response = client.get('/api/v1' + path)
        assert response.status_code == 501
        assert response.json()['code'] == 'NOT_IMPLEMENTED'


def test_openapi_request_response_and_pagination():
    app = contract_app()
    from app.modules.tasks.router import router as tasks_router
    from app.modules.revisions.router import router as revisions_router
    app.include_router(tasks_router, prefix='/api/v1')
    app.include_router(revisions_router, prefix='/api/v1')
    schema = app.openapi()
    paths = schema['paths']
    assert len(paths) == 12
    accepted = paths['/api/v1/tasks']['post']['responses']['202']
    assert accepted['content']['application/json']['schema']['$ref'].endswith('/Accepted')
    assert schema['components']['schemas']['Accepted']['properties']['state']['const'] == '排队中'
    assert schema['components']['schemas']['Task']['properties']['progress']['anyOf'][1]['type'] == 'null'
    client = TestClient(contract_app())
    for query in ['page=0', 'pageSize=0', 'pageSize=101', 'mode=invalid']:
        assert client.get('/api/v1/archives?' + query).status_code == 422
    assert '/api/v1/tasks/{id}/rounds' in paths


def test_optional_and_nullable_are_distinct_and_preserved_in_nested_results():
    picture = business.Picture(name='x', url='/x')
    assert picture.model_dump() == {'name': 'x', 'url': '/x'}
    for field in ['fileId', 'version']:
        with pytest.raises(ValidationError):
            business.Picture(name='x', url='/x', **{field: None})
    schema = business.Picture.model_json_schema(mode='serialization')
    assert 'fileId' not in schema['required']
    assert schema['properties']['fileId']['type'] == 'string'
    assert 'default' not in schema['properties']['fileId']
    slot = business.ResultSlot(slot=0, versions=[], currentVersionId=None, error=None)
    assert slot.model_dump()['currentVersionId'] is None
    assert slot.model_dump()['error'] is None
    assert business.User(id='1', name='pending', role=None, status='pending').role is None
    required = management.DefaultSkillIds.model_json_schema()['required']
    assert set(required) == {'wallpaper', 'product', 'text'}
    for value in [{}, {'wallpaper': None}, {'wallpaper': None, 'product': None}]:
        with pytest.raises(ValidationError):
            management.DefaultSkillIds.model_validate(value)
    assert management.DefaultSkillIds(wallpaper=None, product=None, text=None).model_dump() == {
        'wallpaper': None, 'product': None, 'text': None}


def test_all_omittable_nonnullable_model_fields_reject_explicit_null():
    for module in [business, management]:
        for model in vars(module).values():
            if not isinstance(model, type) or not hasattr(model, 'model_fields'):
                continue
            for name, field in model.model_fields.items():
                if field.exclude_if is None:
                    continue
                from pydantic import TypeAdapter
                with pytest.raises(ValidationError):
                    TypeAdapter(field.annotation).validate_python(None)
                schema = model.model_json_schema()['properties'][field.alias or name]
                assert 'null' not in str(schema), (model.__name__, name)


def test_top_level_fields_match_frontend_interfaces():
    # Frontend sources are available locally; Docker copies this fixture directory
    # via the integration runner for the cross-language check.
    types = Path(__file__).resolve().parents[2] / 'frontend/src/types'
    if not types.exists():
        types = Path('/contracts-types')
    assert types.exists(), 'Run with frontend type sources mounted at /contracts-types'
    for module, source, names in [
        (business, 'hengxin.ts', ['User', 'Picture', 'Template', 'Task', 'Round', 'Archive',
          'Accepted', 'TemplateInput', 'CreateTaskInput', 'RevisionInput', 'DeletionReceipt']),
        (management, 'management.ts', ['UsageSummary', 'UsageAttempt', 'UsageReport',
          'UsageRow', 'MonitorReport', 'SettingsAudit', 'UserInput']),
    ]:
        text = (types / source).read_text(encoding='utf-8')
        for name in names:
            start = re.search(r'export interface ' + name + r'\s*\{', text).end()
            depth, end = 1, start
            while depth:
                depth += (text[end] == '{') - (text[end] == '}')
                end += 1
            body = text[start:end - 1]
            # Remove inline nested objects; only compare top-level field names.
            while re.search(r'\{[^{}]*\}', body):
                body = re.sub(r'\{[^{}]*\}', '', body)
            fields = set(re.findall(r'(?:^|[;\n])\s*(\w+)\??\s*:', body))
            assert fields == set(getattr(module, name).model_fields), name
