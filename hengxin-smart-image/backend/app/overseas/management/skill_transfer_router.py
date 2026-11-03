"""Management folder API. The application never writes the installed volume."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.core.browser_auth import browser_request
from app.overseas.permissions import require_permission
from . import skill_downloads, skill_transfer_client as publisher
from .skill_transfer_schema import SkillDelete, TransferCreate, TransferInstall
from .skills import can_toggle

router = APIRouter()
admin = require_permission('skills.manage')


def manager(actor=Depends(admin)):
    if not can_toggle(actor):
        raise HTTPException(403, '仅指定账号可上传、更新或删除 Skill')
    return actor


@router.post('/skill-transfers', dependencies=[Depends(browser_request)])
async def create_transfer(request: Request, actor=Depends(manager)):
    body = await publisher.parse_body(request, TransferCreate)
    return await publisher.request('POST', '/transfers', actor, body=body.model_dump(),
                                   key=request.headers.get('Idempotency-Key'))


@router.get('/skill-transfers')
async def list_transfers(actor=Depends(manager)):
    return await publisher.request('GET', '/transfers', actor)


@router.get('/skill-transfers/{transfer_id}')
async def get_transfer(transfer_id: UUID, actor=Depends(manager)):
    return await publisher.request('GET', f'/transfers/{transfer_id}', actor)


@router.put('/skill-transfers/{transfer_id}/files', dependencies=[Depends(browser_request)])
async def upload_file(transfer_id: UUID, request: Request, path: str = Query(max_length=500),
                      actor=Depends(manager)):
    return await publisher.request('PUT', f'/transfers/{transfer_id}/files', actor,
                                   content=publisher.bounded_stream(request), params={'path': path})


@router.post('/skill-transfers/{transfer_id}/validate', dependencies=[Depends(browser_request)])
async def validate_transfer(transfer_id: UUID, actor=Depends(manager)):
    return await publisher.request('POST', f'/transfers/{transfer_id}/validate', actor)


@router.post('/skill-transfers/{transfer_id}/install', dependencies=[Depends(browser_request)])
async def install_transfer(transfer_id: UUID, request: Request, actor=Depends(manager)):
    body = await publisher.parse_body(request, TransferInstall)
    return await publisher.request('POST', f'/transfers/{transfer_id}/install', actor, body=body.model_dump())


@router.delete('/skill-transfers/{transfer_id}', dependencies=[Depends(browser_request)])
async def cancel_transfer(transfer_id: UUID, actor=Depends(manager)):
    return await publisher.request('DELETE', f'/transfers/{transfer_id}', actor)


@router.get('/skills/{skill_id}/package')
def get_package(skill_id: UUID, actor=Depends(admin)):
    return skill_downloads.package(skill_id)


@router.get('/skills/{skill_id}/files')
def download_file(skill_id: UUID, release: str = Query(pattern=r'^[a-f0-9]{64}$'),
                  path: str = Query(max_length=500), actor=Depends(admin)):
    return skill_downloads.file(skill_id, release, path)


@router.delete('/skills/{skill_id}', dependencies=[Depends(browser_request)])
async def delete_skill(skill_id: UUID, request: Request, actor=Depends(manager)):
    body = await publisher.parse_body(request, SkillDelete)
    return await publisher.request('DELETE', f'/skills/{skill_id}', actor, body=body.model_dump())
