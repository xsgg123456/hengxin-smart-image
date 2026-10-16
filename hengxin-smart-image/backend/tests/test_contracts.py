"""Shared API/identity contracts survive domestic legacy module retirement."""
import re
from pathlib import Path
import pytest
from pydantic import TypeAdapter, ValidationError
from app.contracts import business, management


def test_openapi_preserves_api_image_and_shared_management_routes():
    from app.main import app
    paths = app.openapi()['paths']
    root = '/api/v1/api-image-edits'
    required = {
        root + '/files': {'post'}, root + '/tasks': {'get', 'post'},
        root + '/tasks/{task_id}': {'get', 'delete'},
        root + '/tasks/{task_id}/items/{item_id}/revise': {'post'},
        root + '/tasks/{task_id}/items/{item_id}/restore': {'post'},
        root + '/tasks/{task_id}/items/{item_id}/conversation': {'get'},
        root + '/tasks/{task_id}/items/{item_id}/conversation/turns': {'post'},
        '/api/v1/management/users': {'get'},
        '/api/v1/management/settings': {'get', 'put'},
        '/api/v1/auth/dingtalk/config': {'get'},
    }
    for path, methods in required.items():
        assert methods <= paths[path].keys(), path
    retired = ('/api/v1/tasks', '/api/v1/templates', '/api/v1/archives',
               '/api/v1/files', '/api/v1/workspace', '/api/v1/management/skills',
               '/api/v1/management/monitor', '/api/v1/management/usage')
    assert not any(path == old or path.startswith(old + '/') for path in paths for old in retired)
    assert not any('501' in operation.get('responses', {})
                   for path in paths.values() for operation in path.values() if isinstance(operation, dict))


@pytest.mark.parametrize('query', [dict(page=0), dict(pageSize=0), dict(pageSize=101)])
def test_shared_pagination_rejects_out_of_bounds(query):
    with pytest.raises(ValidationError):
        business.PageQuery(**query)


def test_optional_and_nullable_are_distinct_and_preserved_in_nested_results():
    error = business.ApiErrorBody(code='FAILED', message='request failed')
    assert error.model_dump() == {'code': 'FAILED', 'message': 'request failed'}
    with pytest.raises(ValidationError):
        business.ApiErrorBody(code='FAILED', message='request failed', requestId=None)
    schema = business.ApiErrorBody.model_json_schema(mode='serialization')
    assert 'requestId' not in schema['required']
    assert schema['properties']['requestId']['type'] == 'string'
    assert 'default' not in schema['properties']['requestId']
    page = business.PageResult[business.ApiErrorBody](items=[error], page=1, pageSize=20, total=1)
    assert page.model_dump()['items'] == [error.model_dump()]
    user = business.User(id='1', name='pending', role=None, status='pending')
    assert user.model_dump()['role'] is None
    assert user.model_dump()['identitySessionId'] is None


def test_all_omittable_nonnullable_model_fields_reject_explicit_null():
    for module in [business, management]:
        for model in vars(module).values():
            if not isinstance(model, type) or not hasattr(model, 'model_fields'):
                continue
            for name, field in model.model_fields.items():
                if field.exclude_if is None:
                    continue
                with pytest.raises(ValidationError):
                    TypeAdapter(field.annotation).validate_python(None)
                schema = model.model_json_schema()['properties'][field.alias or name]
                assert 'null' not in str(schema), (model.__name__, name)


def test_top_level_fields_match_frontend_interfaces():
    types = Path(__file__).resolve().parents[2] / 'frontend/src/types'
    if not types.exists():
        types = Path('/contracts-types')
    assert types.exists(), 'Run with frontend type sources mounted at /contracts-types'
    for module, source, names in [
        (business, 'hengxin.ts', ['User', 'PageQuery', 'PageResult', 'ApiErrorBody']),
        (management, 'hengxin.ts', ['SystemConfig']),
        (management, 'management.ts', ['SettingsAudit', 'UserInput']),
    ]:
        text = (types / source).read_text(encoding='utf-8')
        for name in names:
            match = re.search(r'export interface ' + name + r'(?:<[^>]+>)?\s*\{', text)
            assert match, name
            start, depth = match.end(), 1
            end = start
            while depth:
                depth += (text[end] == '{') - (text[end] == '}')
                end += 1
            body = text[start:end - 1]
            while re.search(r'\{[^{}]*\}', body):
                body = re.sub(r'\{[^{}]*\}', '', body)
            fields = set(re.findall(r'(?:^|[;\n])\s*(\w+)\??\s*:', body))
            assert fields == set(getattr(module, name).model_fields), name
