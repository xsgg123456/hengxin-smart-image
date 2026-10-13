"""Test-only ASGI entry. Never import from a deployed application."""
from app.identity import router
from app.modules.auth.dingtalk import DingTalkMember, DingTalkProviderError


def exchange(code, settings):
    from phase18_fixtures import CODES
    from phase19_fixtures import CODES as TASK_CODES
    from membership_checks import CODES as MEMBER_CODES
    if code not in {'both', 'domestic', 'overseas', 'neither', *CODES, *TASK_CODES, *MEMBER_CODES}:
        raise DingTalkProviderError('Unknown disposable test member')
    display_code = 'mi-ui-applicant' if code == 'mi-ui-same-name' else code
    return DingTalkMember(code, '测试成员-' + display_code, 'test-union-' + code,
                         '测试部门', settings.dingtalk_corp_id)


router.dingtalk.exchange_container_code = exchange
router.dingtalk.exchange_auth_code = exchange
from app.identity.main import create_app  # noqa: E402

app = create_app()
