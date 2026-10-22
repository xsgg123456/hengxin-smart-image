"""Private, pinned owner binding; never mutate accounts or create login sessions."""
import copy
import hashlib
import json
import re
import stat
from uuid import UUID

KEY = 'OVERSEAS_SKILL_TOGGLE_OWNER_ID'
ENABLED = {'amazon-new-product-image-set', 'amazon-new-product-aplus'}


def read(work):
    path = work / 'skill-owner.env'
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode) and not path.is_symlink(), 'Owner binding must be a regular file'
    assert (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (0, 0, 0o600), 'Owner binding requires root:root 0600'
    raw = path.read_bytes()
    match = re.fullmatch(KEY.encode() + rb'=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:\r?\n)?', raw)
    assert match, 'Owner binding requires exactly one canonical UUID assignment'
    owner = match[1].decode()
    assert str(UUID(owner)) == owner and UUID(owner).int != 0, 'Invalid owner UUID'
    return {'owner': owner, 'sha256': hashlib.sha256(raw).hexdigest()}


def account(owner, u):
    # UUID is validated before interpolation; exact single role matches skills.manage policy.
    assert str(UUID(owner)) == owner
    query = ("SELECT count(*) FROM overseas_members m WHERE m.id='" + owner + "' AND m.status='active' "
             "AND (SELECT count(*) FROM overseas_member_roles r WHERE r.user_id=m.id)=1 "
             "AND EXISTS(SELECT 1 FROM overseas_member_roles r WHERE r.user_id=m.id AND r.role='super_admin')")
    assert u.sql(query) == '1', 'Owner must be an active overseas member with skills.manage'


def pinned(work, u):
    binding = read(work)
    assert binding == json.loads((work / 'skill-owner.private.json').read_text()), 'Owner binding changed since preparation'
    account(binding['owner'], u)
    return binding['owner']


def normalize(before, after):
    result = copy.deepcopy(after)
    env = result['services']['api'].get('environment', {})
    value = env.get(KEY)
    assert isinstance(value, str) and str(UUID(value)) == value and UUID(value).int, 'API owner binding missing or invalid'
    old = before['services']['api'].get('environment', {})
    if KEY in old:
        env[KEY] = old[KEY]
    else:
        env.pop(KEY)
    if not env and 'environment' not in before['services']['api']:
        result['services']['api'].pop('environment', None)
    return result


PROBE = '''
import json, os
from uuid import UUID
from sqlalchemy import select, text
import app.overseas.main
from app.core.config import get_settings
from app.db.session import session_factory
from app.overseas.auth.models import Member
from app.overseas.permissions import authorize_member
from app.overseas.management.skills import can_toggle, list_skills
owner = UUID(os.environ['OVERSEAS_SKILL_TOGGLE_OWNER_ID'])
assert get_settings().skill_toggle_owner_id == owner
with session_factory()() as session:
    session.execute(text('SET TRANSACTION READ ONLY'))
    members = session.scalars(select(Member)).all()
    actor = next(m for m in members if m.id == owner)
    assert actor.status == 'active'
    authorize_member(session, actor, 'skills.manage')
    assert [m.id for m in members if can_toggle(m)] == [owner]
    assert not can_toggle(None)
    result = list_skills(session, actor)
    assert result['canToggle']
    assert {i['name'] for i in result['items'] if i['enabled']} == {'amazon-new-product-image-set', 'amazon-new-product-aplus'}
    assert all(i['version'] == 1 for i in result['items'])
print(json.dumps({'ownerVerified': True, 'initialSkillsVerified': True, 'readOnly': True}))
'''


def installed(work, m, u):
    owner = pinned(work, u)
    entries = m.live(u.API)['Config']['Env']
    assert [v for v in entries if v.startswith(KEY + '=')] == [KEY + '=' + owner], 'Installed API owner drift'
    result = json.loads(m.run('docker', 'exec', u.API, 'python', '-c', PROBE, capture=True))
    assert result == {'ownerVerified': True, 'initialSkillsVerified': True, 'readOnly': True}
    m.private(work / 'SKILL_AVAILABILITY_VERIFIED.json', result)
