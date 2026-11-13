"""Administrator-only domestic Skill status and workspace bindings."""
import os
from pathlib import Path, PurePosixPath
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy.orm import Session

from app.core.browser_auth import browser_request
from app.core.config import get_settings
from app.db.session import get_session
from app.modules.auth.permissions import require_permission
from app.overseas.management import skill_downloads
from app.overseas.management import skill_transfer_client as publisher
from app.overseas.management.skill_transfer_schema import SkillDelete, TransferCreate, TransferInstall
from .bindings import read_bindings, save_bindings
from .installed_skills import DomesticInstalledSkills
from .skill_state import freeze_enabled, listing, set_availability
from .skill_publication import authorize as authorize_write
from . import protected as protection


router = APIRouter(prefix='/management/domestic-studio', tags=['domestic-studio-management'])
Admin = Annotated[object, Depends(require_permission('manage_system'))]
Database = Annotated[Session, Depends(get_session)]
WRITE = [Depends(browser_request)]
SkillId = Annotated[str, Field(min_length=1, max_length=100)]
PUBLISH_SOCKET = '/run/hengxin-domestic-skill-publisher/publisher.sock'


class WorkspaceBindings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    camera: SkillId | None
    case: SkillId | None
    product: SkillId | None
    scene: SkillId | None
    phone: SkillId | None


class BindingInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    bindings: WorkspaceBindings
    expected: WorkspaceBindings


class AvailabilityInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: StrictBool
    version: int = Field(ge=1, strict=True)


def get_catalog():
    value = os.environ.get('DOMESTIC_SKILL_ROOT', '').strip()
    if not value:
        raise HTTPException(503, '国内 Skill 存储尚未配置，请联系管理员')
    try:
        return DomesticInstalledSkills(Path(value), protected=protection.enabled(get_settings()))
    except (OSError, ValueError):
        raise HTTPException(503, '国内 Skill 存储配置无效，请联系管理员') from None


Catalog = Annotated[DomesticInstalledSkills, Depends(get_catalog)]


def publisher_socket():
    value = os.environ.get('DOMESTIC_SKILL_PUBLISH_SOCKET', PUBLISH_SOCKET)
    try:
        protected = protection.enabled(get_settings())
    except ValueError:
        raise HTTPException(503, '国内 Skill 发布服务配置无效，请联系管理员') from None
    if not PurePosixPath(value).is_absolute() or (protected and value != PUBLISH_SOCKET):
        raise HTTPException(503, '国内 Skill 发布服务配置无效，请联系管理员')
    return value


async def publish_request(method, path, actor, **kwargs):
    return await publisher.request(method, path, actor, socket_path=publisher_socket(), **kwargs)


@router.post('/skill-transfers', dependencies=WRITE)
async def create_transfer(request: Request, admin: Admin):
    body = await publisher.parse_body(request, TransferCreate)
    return await publish_request('POST', '/transfers', admin, body=body.model_dump(),
                                 key=request.headers.get('Idempotency-Key'))


@router.get('/skill-transfers')
async def list_transfers(admin: Admin):
    return await publish_request('GET', '/transfers', admin)


@router.get('/skill-transfers/{transfer_id}')
async def get_transfer(transfer_id: UUID, admin: Admin):
    return await publish_request('GET', f'/transfers/{transfer_id}', admin)


@router.put('/skill-transfers/{transfer_id}/files', dependencies=WRITE)
async def upload_file(transfer_id: UUID, request: Request, admin: Admin, path: str = Query(max_length=500)):
    return await publish_request('PUT', f'/transfers/{transfer_id}/files', admin,
                                 content=publisher.bounded_stream(request), params={'path': path})


@router.post('/skill-transfers/{transfer_id}/validate', dependencies=WRITE)
async def validate_transfer(transfer_id: UUID, admin: Admin):
    return await publish_request('POST', f'/transfers/{transfer_id}/validate', admin)


@router.post('/skill-transfers/{transfer_id}/install', dependencies=WRITE)
async def install_transfer(transfer_id: UUID, request: Request, admin: Admin):
    body = await publisher.parse_body(request, TransferInstall)
    return await publish_request('POST', f'/transfers/{transfer_id}/install', admin, body=body.model_dump())


@router.delete('/skill-transfers/{transfer_id}', dependencies=WRITE)
async def cancel_transfer(transfer_id: UUID, admin: Admin):
    return await publish_request('DELETE', f'/transfers/{transfer_id}', admin)


@router.delete('/skills/{skill_id}', dependencies=WRITE)
async def delete_skill(skill_id: UUID, request: Request, admin: Admin):
    body = await publisher.parse_body(request, SkillDelete)
    return await publish_request('DELETE', f'/skills/{skill_id}', admin, body=body.model_dump())


@router.get('/skills')
def list_skills(_admin: Admin, session: Database, catalog: Catalog):
    return {'items': listing(session, catalog)}


@router.get('/skills/{skill_id}/package')
def skill_package(skill_id: UUID, _admin: Admin, catalog: Catalog):
    return skill_downloads.package(skill_id, catalog_provider=catalog)


@router.get('/skills/{skill_id}/files')
def skill_file(skill_id: UUID, _admin: Admin, catalog: Catalog,
               release: str = Query(pattern=r'^[a-f0-9]{64}$'), path: str = Query(max_length=500)):
    return skill_downloads.file(skill_id, release, path, catalog_provider=catalog)


@router.patch('/skills/{skill_id}/availability', dependencies=WRITE)
def change_availability(skill_id: UUID, body: AvailabilityInput, _admin: Admin,
                        session: Database, catalog: Catalog):
    authorize_write(session, _admin.id)
    items = set_availability(session, catalog, str(skill_id), body.enabled, body.version)
    session.commit()
    return {'items': items}


@router.get('/bindings')
def get_bindings(_admin: Admin, session: Database):
    return {'bindings': read_bindings(session)}


@router.put('/bindings', dependencies=WRITE)
def update_bindings(body: BindingInput, _admin: Admin, session: Database, catalog: Catalog):
    authorize_write(session, _admin.id)
    saved = save_bindings(session, body.bindings.model_dump(), lambda identity: freeze_enabled(session, catalog, identity),
                          expected=body.expected.model_dump())
    session.commit()
    return {'bindings': saved}
