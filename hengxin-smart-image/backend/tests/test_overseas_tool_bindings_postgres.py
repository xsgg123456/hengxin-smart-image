from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi import HTTPException
from sqlalchemy import select

from app.overseas.auth.models import Member
from app.overseas.execution.models import ExecutionGate
from app.overseas.management.models import Audit, ToolSkillBinding
from app.overseas.management.schemas import ToolBindingsPatch
from app.overseas.management.tool_bindings import replace
from overseas_installed_helpers import install_sample
from test_overseas_management_postgres import configured
from test_overseas_members_postgres import pg_factory, member


def test_two_admins_editing_empty_tool_cannot_overwrite_each_other(pg_factory):
    admins = [member(pg_factory), member(pg_factory)]
    skills = [install_sample('first'), install_sample('second')]
    with pg_factory.begin() as session:
        session.add(ExecutionGate(id=1))
    sync = Barrier(2)

    def edit(i):
        with pg_factory() as session:
            admin = session.get(Member, admins[i])
            sync.wait(timeout=8)
            try:
                replace(session, admin, 'outon', ToolBindingsPatch(expectedSkillIds=[], skillIds=[skills[i]['id']]))
                return 200
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(edit, range(2)))
    assert sorted(responses) == [200, 409]
    winner = responses.index(200)
    with pg_factory() as session:
        assert session.scalars(select(ToolSkillBinding.skill_name)).all() == [skills[winner]['name']]
        assert session.scalars(select(Audit.actor_id)).all() == [admins[winner]]
