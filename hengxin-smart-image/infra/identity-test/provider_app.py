"""Test-only ASGI entry. Never import from a deployed application."""
from app.identity import router
from app.modules.auth.dingtalk import DingTalkMember, DingTalkProviderError


def exchange(code, settings):
    if code not in {'both', 'domestic', 'overseas', 'neither'}:
        raise DingTalkProviderError('Unknown disposable test member')
    return DingTalkMember(code, '测试成员-' + code, 'test-union-' + code,
                         '测试部门', settings.dingtalk_corp_id)


router.dingtalk.exchange_container_code = exchange
router.dingtalk.exchange_auth_code = exchange
from app.identity.main import create_app  # noqa: E402

app = create_app()
