"""Publish agreed shapes without representing future business APIs as implemented."""
from typing import Annotated
from fastapi import APIRouter, File, Form, Query, UploadFile
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


@router.get('/auth/me', response_model=b.User)
def current_user():
    return pending()


@router.get('/workspace', response_model=b.Workspace)
def workspace():
    return pending()


@router.get('/templates', response_model=b.PageResult[b.Template])
def templates(query: Annotated[b.TemplateQuery, Query()]):
    return pending()


@router.get('/templates/{id}', response_model=b.Template)
def template(id: str):
    return pending()


@router.post('/templates', response_model=b.Template)
def create_template(body: b.TemplateInput):
    return pending()


@router.put('/templates/{id}', response_model=b.Template)
def update_template(id: str, body: b.TemplateInput):
    return pending()


@router.delete('/templates/{id}', status_code=204)
def delete_template(id: str):
    return pending()


@router.get('/skills', response_model=list[b.SkillVersion])
def skills(mode: b.Mode | None = None):
    return pending()


@router.post('/files', response_model=b.Picture)
def upload_file(file: Annotated[UploadFile, File()]):
    return pending()


@router.get('/tasks', response_model=b.TaskPage)
def tasks(query: Annotated[b.TaskQuery, Query()]):
    return pending()


@router.post('/tasks', response_model=b.Accepted, status_code=202)
def create_task(body: b.CreateTaskInput):
    return pending()


@router.get('/tasks/{id}', response_model=b.TaskDetailData)
def task(id: str):
    return pending()


@router.delete('/tasks/{id}', response_model=b.DeletionReceipt)
def delete_task(id: str):
    return pending()


@router.post('/tasks/{id}/rounds', response_model=b.Accepted, status_code=202)
def revise(id: str, body: b.RevisionInput):
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


@router.get('/management/skills', response_model=list[m.ManagedSkill])
def managed_skills():
    return pending()


@router.post('/management/skills', response_model=m.ManagedSkill)
def upload_skill(file: Annotated[UploadFile, File()], mode: Annotated[b.Mode, Form()],
                 version: Annotated[str, Form()]):
    return pending()


@router.post('/management/skills/{id}/install', response_model=m.ManagedSkill)
def install_skill(id: str):
    return pending()


@router.put('/management/skills/{id}/status', response_model=m.ManagedSkill)
def skill_status(id: str, body: m.SkillStatusInput):
    return pending()


@router.get('/management/settings', response_model=m.ManagedSettings)
def settings():
    return pending()


@router.put('/management/settings', response_model=m.ManagedSettings)
def update_settings(body: m.SettingsInput):
    return pending()
