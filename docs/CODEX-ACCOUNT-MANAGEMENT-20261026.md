# 国内与海外 Codex 账号管理

用户于 2026-10-26 批准 preview-codex-auth 交互，授权正式实现、测试、中文 Git 提交与生产发布。只增加管理中心账号页，其他布局不变。

## 实施顺序与完成标准
1. 接入现有管理权限、页面和官方 CLI 设备码登录。验收：真实状态、检测、授权、重试、确认启用、取消、移除、操作记录可用，无模拟控件。
2. 服务端独立业务配置。验收：国内和海外各自更新；启动迁移引用现有共享主凭据，不复制刷新令牌、不撤销原授权。新授权验证成功并确认后才切换当前业务。
3. 故障与隔离验证。验收：失败/超时/取消不改变当前配置；原账号和工作区重新授权可继续原会话；不同账号明确确认更换，旧会话保留身份校验、不自动重跑；不修改现有任务数据。
4. 独立审查、构建、部署。验收：服务端测试、前端类型检查/构建、交互和权限测试通过；发布保留旧版本，执行器排空后切换，现有任务不被强制中断；生产就绪和页面冒烟通过。

## 安全与兼容边界
- 官方 `codex login --device-auth` 在独立临时 CODEX_HOME 运行；不用 app-server 登录接口，不接收账号密码或浏览器上传凭据。
- 主凭据和刷新令牌只留在宿主机授权服务私有目录；业务 API 仅连接自己的管理 socket，不接触凭据；执行器仍通过原 access-only broker 协议领取访问凭据。
- 两个业务初始引用同一现有主凭据文件，继续使用既有文件锁刷新。完成独立设备授权的业务才指向自己的新主凭据；移除仅清除当前业务绑定，不调用 logout/revoke、不删除共享源。
- 每业务一个待授权流程，绑定管理员与配置版本；取消、超时、服务重启清理候选，不动已启用配置。确认时核对版本和原身份，防止并发覆盖。
- 检测使用隔离临时工作区，做最小真实模型请求，不读业务文件、不新建业务任务、不续接用户会话。检测不到上游结果时显示连接异常，不把网络故障误报为授权失效。
- 身份以账号 ID 和 subject 为准，不以邮箱判断；工作区展示真实标识，不虚构名称。检测状态有时间，不把仅存在文件当作已验证可用。
- 不改模型、Skill、会话历史、任务状态、成品或原有身份校验；失败操作由用户手动重新发送。
- 国内使用 manage_system 权限；海外沿用 settings.manage。所有修改请求有 browser_request 校验。操作记录包含时间/操作者/动作/结果，不含令牌和授权码。

## 前后端接口合同
国内前缀 `/api/v1/management/codex-auth`，海外 `/api/overseas/v1/management/codex-auth`。业务取自部署和路由，禁止客户端传业务/文件路径。

- GET 根：Account。
- POST `/check`：启动异步连接检测，返回 Account；轮询 GET 至 checking=false。
- POST `/authorizations`：`{intent: connect|renew|replace, revision: number}`，返回 Authorization。
- GET `/authorizations/{id}`：当前管理员自己的流程。
- POST `/authorizations/{id}/retry`：重试候选检测。
- POST `/authorizations/{id}/activate`：`{acknowledged: boolean}`，确认启用，返回 Account。
- DELETE `/authorizations/{id}`：取消，返回 `{ok:true}`。
- DELETE 根：`{revision:number}`，移除当前业务绑定，返回 Account。

Account: `{status: empty|unchecked|ready|expired|network, email, workspace, checked, updated, audit:[{time,operator,action,result}], revision:number, checking:boolean}`。时间字符串由服务端输出北京时间。unchecked 表示尚未进行真实连接检测。

Authorization: `{id, step: starting|waiting|checking|expired|failed|mismatch|verified, userCode, verificationUrl, expiresAt:number, candidateEmail, candidateWorkspace, different:boolean, message}`；expiresAt 为 Unix 秒。different 由服务端比对完整身份。失败响应使用现有 HTTP 错误结构。

管理 socket 协议：使用现有 length-prefixed JSON framing，上限 16KiB 请求/128KiB响应；请求 `{action, actor:{id,name}, ...}`，action=status/check/start/poll/retry/activate/cancel/remove；start 附 intent/revision，poll/retry/activate/cancel 附 id，activate 附 acknowledged，remove 附 revision。响应 `{data: ...}` 或 `{error:{status:400|403|404|409|503,message}}`。每 socket 固定一个业务，SO_PEERCRED 限制 API UID。API 不接受客户端传 actor。
