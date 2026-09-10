"""Publish agreed shapes without representing future business APIs as implemented."""
from typing import Annotated
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from . import business as b
from . import management as m

router = APIRouter(tags=['planned-business-contracts'], responses={
    501: {'model': b.ApiErrorBody, 'description': '业务实现属于后续 Phase'},
    422: {'model': b.ApiErrorBody},
})


def pending():
    return JSONResponse(status_code=501, content={
        'code': 'NOT_IMPLEMENTED', 'message': '该业务接口将在后续开发阶段接入',
    })


@router.get('/workspace', response_model=b.Workspace)
def workspace():
    return pending()


@router.post('/tasks/{id}/archives', response_model=b.Archive)
def archive_task(id: str):
    return pending()


@router.get('/archives', response_model=b.PageResult[b.Archive])
def archives(query: Annotated[b.PageQuery, Query()]):
    return pending()


@router.get('/archives/{id}', response_model=b.Archive)
def archive(id: str):
    return pending()


@router.delete('/archives/{id}', status_code=204)
def delete_archive(id: str):
    return pending()


@router.get('/management/usage', response_model=m.UsageReport)
def usage(query: Annotated[m.UsageQuery, Query()]):
    return pending()


@router.get('/management/monitor', response_model=m.MonitorReport)
def monitor():
    return pending()


@router.get('/management/users', response_model=b.PageResult[m.ManagedUser])
def users(query: Annotated[m.UserQuery, Query()]):
    return pending()


@router.put('/management/users/{id}', response_model=m.ManagedUser)
def update_user(id: str, body: m.UserInput):
    return pending()


@router.get('/management/settings', response_model=m.ManagedSettings)
def settings():
    return pending()


@router.put('/management/settings', response_model=m.ManagedSettings)
def update_settings(body: m.SettingsInput):
    return pending()
