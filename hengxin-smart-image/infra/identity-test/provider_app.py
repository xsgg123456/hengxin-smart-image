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


@app.get('/api/identity/v1/test-login', include_in_schema=False)
def test_login(taskId: str = ''):
    """Browser-operated login for disposable harnesses; never in production app."""
    import json
    from uuid import UUID
    from fastapi.responses import HTMLResponse
    task = str(UUID(taskId)) if taskId else ''
    destination = '/?workspace=overseas#/overseas/tasks/' + task
    return HTMLResponse('''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>隔离测试设计师登录</title><body><h1>隔离测试设计师登录</h1>
<p>仅用于本地验收，以 p18-designer 登录；不调用真实钉钉。</p>
<button id="login">登录设计师并进入图片任务</button><p id="status"></p>
<script>
const status = document.getElementById('status');
async function post(url, body) {
  const response = await fetch(url, {method:'POST', credentials:'same-origin',
    headers:{'Content-Type':'application/json','X-HX-Request':'1'}, body:JSON.stringify(body)});
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}
document.getElementById('login').onclick = async () => {
  try {
    status.textContent = '正在登录…';
    await post('/api/identity/v1/dingtalk/container', {code:'p18-designer'});
    const result = await post('/api/identity/v1/tickets', {business:'overseas', purpose:'session'});
    await post('/api/overseas/v1/auth/identity/session', {ticket:result.ticket});
    location.href = DESTINATION;
  } catch (error) { status.textContent = String(error); }
};
</script></body></html>'''.replace('DESTINATION', json.dumps(destination)))
