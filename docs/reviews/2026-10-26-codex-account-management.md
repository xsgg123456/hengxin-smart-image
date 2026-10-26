# Codex 账号管理独立审查

- 日期：2026-10-26；角色：code-reviewer；使用 `.agents/skills/code-review/SKILL.md`。
- 送审 candidateId：`17888a82cfc891b1c37f9b0575241c3bb084b1e4e6d63747166e3ae9ecefde7f`。
- **本轮结论：Stage 1 FAIL；Stage 2 未执行。不得据本报告登记两阶段 PASS。**
- 范围：`hengxin-smart-image/backend/app/account_management/` 全部八个模块、credential_broker 兼容扩展、config/main/overseas main；正式前端账号 API、页面/弹窗/hooks/style、国内 wrapper、路由及海外管理入口；新增四个后端测试、两个前端测试、海外路由基线测试；`scripts/release/account-*.py` 六个文件。已审独立 preview 作为设计参考；用户既存 AGENTS.md 修改不属于本轮功能审查。
- 下文 `backend/`、`frontend/` 均相对 `hengxin-smart-image/`；`scripts/` 相对仓库根。问题行号对应送审时版本。

## 快照变化

首次 `review-status` 的 currentId 与送审编号一致。审查中主 Agent 开始修改 manager.py 并增加身份漂移测试；结束前 currentId 为 `c4d820148ba5fd021b349ea048f0668cf39b96b7c19be57549fcafc2c9fefaff`，已不等于送审版本。主 Agent 告知身份问题已修、期限问题准备修；本报告不把该说明当作修订后通过结论。必须重新固定候选，重新从 Stage 1 复核，再执行 Stage 2。

## Stage 1 阻断与不匹配

### HIGH — 更换流程确认时没有重新核对原身份

- 合同：`docs/CODEX-ACCOUNT-MANAGEMENT-20261026.md:15`：“确认时核对版本和原身份，防止并发覆盖”；第8行要求不同账号明确确认更换。
- 位置：`backend/app/account_management/manager.py:151` 使用早先计算的 different 决定确认；第156行检查 revision；第157行仅 renew 检查当前身份。`store.py:70` 返回外部 canonical legacy 文件，文件变化不自动递增业务 revision。
- 复现：独立临时目录、假登录/假探测，不碰生产。legacy=A；以 replace 登录A，候选 verified 且 different=false；将 canonical 文件改为B，业务 revision 仍0；调用 activate(id, acknowledged=false)。结果成功切回A。换号确认被旧身份快照绕过。
- 原始输出：

```text
candidate_different= False
current_before_activate= concurrently-changed
activation_without_ack= ready current_after= original
```

- 修复标准：所有原本有配置的授权流程在启用前重新读取并比较当前身份与 pending.previous；无法读取或不同则409，要求重新读取/重新授权。补 renew、replace、原身份不可读回归，不能只测试不同邮箱。

### MEDIUM — 到期检测未终止，旧候选仍存在时允许第二个授权流程

- 合同：同文件第15行：“每业务一个待授权流程”“取消、超时、服务重启清理候选”。
- 位置：`manager.py:172` 的 cancelled 不包含 expiresAt；第203行把该回调传给检测；第125行只把 step 改为 expired；第83行看到 expired 直接清空 pending。`probe.py:30` 的模型进程另有120秒上限，因此在授权末段启动的检测可以继续越过授权期限。
- 复现：用阻塞探测函数保存传入的取消回调，在检测期间让 expiresAt 到期；poll 返回 expired，但该回调仍为 False；再次 start 成功，两个授权线程和两个候选目录同时存在。旧线程退出时 `manager.py:220` 的 self.pending is pending 不成立，也跳过旧流程结束审计。
- 原始输出：

```text
expired_step= expired
expired_probe_cancelled= False
live_authorization_threads= 2 temporary_candidates= 2
```

- 修复标准：期限进入实际取消条件；直到旧进程及候选目录清理完成才放行新流程；超时与主动取消审计准确。增加检测中到期、重新开始、取消后清理及重启残留回归。

### MEDIUM — 视觉证据与声称视口不一致，窄屏验收未证明

- 合同第9行要求交互验证；Design-Brief.md 本轮末条要求窄屏内部滚动可达。
- 实际查看 `output/account-management/dialog-390.png`：图片是桌面布局整体缩成390宽、高约185的画面，不能证明390×844响应式布局。实际查看 account-desktop.png：仍是折叠侧栏版本，卡片起点约93，与主 Agent 声称的展开菜单卡片x259不是同一截图。
- `frontend/src/views/codex-auth/style.css:8` 有内部滚动上限，第14行有响应式声明，但声明不能替代渲染验收。主 Agent 已确认截图取到了旧画面，需重拍并保存视口与元素边界原始数据。

## Stage 1 完整条目矩阵

下表“代码匹配”表示本轮已实际读取对应实现；不等同全流程生产验收。上面的问题优先于任何局部匹配。

| 合同条目 | 结果和证据 |
| --- | --- |
| 管理中心追加页面，其他布局不变（第3、6行） | 代码匹配。国内 wrapper `frontend/src/views/hengxin/admin/codex-auth.vue:1`；国内入口 `router/modules/index.ts:20`；海外页面分支 `views/overseas/OverseasPortal.vue:8`、权限映射 `api/overseas/management.ts:5`。修改现有布局仅在 codex-auth 分支，正式 AccountPage 无演示控件。视觉验收仍受上面的截图问题阻断。 |
| 状态、加载、错误、检测（第6、33行） | 代码匹配。`AccountPage.vue:3`、4–15；`use-account.ts:7`、12、19；`store.py:77`。首次 legacy 状态 unchecked，不把文件存在当 ready；失败显示 network，checked 保留北京时间。 |
| 官方设备授权（第12行） | 代码匹配。`device.py:17` 私有 CODEX_HOME；第24行仅启动 login --device-auth；第28行期限和日志大小限制；第38行结束进程。前端 `AuthorizationDialog.vue:45`、46 只打开受限制官方链接与复制授权码，没有密码或上传凭据入口。真实设备码获取/取消证据为主 Agent 的 QA.md 声明，本 reviewer 未操作真实账号。 |
| 主凭据只在宿主、API只连接自己控制socket（第13行） | 代码匹配。`service.py:123` 为两个业务分别构造控制socket；`scripts/release/account-deploy.py:74` 挂载当前业务 runtime 子目录；API只包含 client/router/schemas（account-package.py:54）；client.py:28 仅用服务端配置路径。 |
| worker access-only及UID业务映射（第13、37行） | 代码匹配。`service.py:82`、85 使用1001/999不同映射；第88行按可信 peer UID取source；`credential_broker.py:30`、37 传真实UID；`managed_credentials.py:193` 清除refresh_token，既有同步身份校验仍存在。Linux socket 测试代码 `test_account_management_linux.py:65`、79；本Windows独立测试相应跳过，未声称实测Linux UID。 |
| 初始共享canonical、锁刷新、不复制legacy（第7、14行） | 代码匹配。`store.py:48` 初始化legacy标记，第70行直接返回同一文件；`service.py:93` 走既有 access_credentials；`managed_credentials.py:185` 在文件锁内读/刷新。`test_account_management_state.py:51` 检查无复制且移除不删源。 |
| 新授权经探测、确认才原子切换当前业务（第7行） | 局部匹配。`manager.py:149` 要求verified；`store.py:103` 新generation及原子state保存。确认原身份有HIGH缺陷，不能判完整通过。 |
| 失败/取消/网络异常不替换当前配置（第8行） | 代码匹配常规分支。`manager.py:181`、203–208 只变pending；`store.py:103` 为唯一授权发布路径；state测试第111行覆盖login失败、network、expired。期限清理缺陷另列。 |
| 原账号续接、不同账号确认、旧会话身份保留（第8、17、18行） | 局部匹配。`manager.py:193` renew不一致进入mismatch；`credential_identity.py:24`、`managed_credentials.py:239` 保留原身份约束；state测试第64、98行覆盖原history保留和换号旧会话拒绝。replace确认时身份漂移未保护，见HIGH。 |
| 单候选、管理员所有权、revision CAS（第15行） | 局部匹配。`manager.py:112` 检查所有者；`store.py:99`、manager.py:156检查revision；不同管理员403测试 `test_account_management_state.py:137`。到期后仍能出现双候选，见MEDIUM。 |
| 取消、到期、重启清理（第15行） | 局部匹配。`manager.py:25`、30 清理重启临时目录；`service.py:119` 进程独占锁；manager.py:174 TemporaryDirectory及close关闭。到期探测未停止、旧pending过早丢弃不匹配。 |
| 隔离最小真实模型检测、不读业务、不创建任务（第16行） | 代码匹配。`probe.py:20` 临时目录与随机工作区，第25行不用Skill，第27行read-only最小请求；`workspace.py:82` 仅绑定临时home/work及固定runtime，不挂业务/主凭据/控制socket；probe无DB或任务服务导入。真实调用为主 Agent 提供证据，不把假verify测试当真实模型成功。 |
| 网络与明确认证拒绝分开（第16行） | 代码匹配。`probe.py:16` 刷新不确定性返回network；第43行仅完整成功事件+确切回答返回ready；第47行仅明确401/token_expired/invalid_grant判expired。 |
| 账号ID+subject、真实工作区、带检测时间（第17行） | 代码匹配。`managed_credentials.py:70`–88返回account/sub并核验access一致；`store.py:28` 展示真实account_id；`store.py:17` 北京时间；manager.py:68更新checked。不会用邮箱判断same identity。 |
| 不改模型/Skill/任务/成品/历史，不自动重放（第18行） | 代码匹配。新模块无业务任务写入；`AccountPage.vue:9`、25 和 `AuthorizationDialog.vue:28` 引导手动回任务发送；broker兼容修改没有改变runner、会话binding或生产模型配置。probe专用模型只用于检测。 |
| 国内/海外权限、全部写请求CSRF（第19行） | 代码匹配。`router.py:14` 使用实际会话及manage_system/settings.manage，第39行browser_request，六个修改端点均有WRITE。`test_account_management_api.py:76`、94、180覆盖权限撤销、跨业务cookie、全部写CSRF、海外权限。独立运行通过。 |
| 审计时间/操作者/动作/结果，不含token/code（第19行） | 常规记录匹配。`store.py:94`固定四字段；manager.py:69、107、223写固定结果，无原始异常/CLI输出。expired旧pending被丢弃时结束审计可缺失，见MEDIUM。 |
| 业务/actor/路径不由客户端控制（第22、37行） | 代码匹配。`router.py:28`拒绝query，`schemas.py:7` strict+extra forbid，`client.py:31`由actor对象构造操作者，`service.py:25`精确字段校验，`service.py:60` SO_PEERCRED白名单。 |
| GET Account（第24行） | 匹配。`router.py:42`、client.py:43响应模型过滤；schema.py:35账号字段齐全。 |
| POST check，GET轮询checking（第25行） | 匹配。`router.py:47`、manager.py:44 异步启动，use-account.ts:7 1.5秒轮询；旧revision的探测结果不覆盖新配置（manager.py:67）。 |
| POST authorizations（第26行） | 匹配常规启动。`router.py:52`、schemas.py:11校验intent/revision；manager.py:79。 |
| GET本人authorizations/{id}（第27行） | 匹配。`router.py:57`、manager.py:112与122。 |
| POST retry（第28行） | 匹配。`router.py:62`、manager.py:137 只允许有候选且未过期的failed状态；use-authorization.ts:55接真实接口。 |
| POST activate（第29行） | 接口匹配，但身份复核不完整。`router.py:67`、schemas.py:16；manager.py:146。 |
| DELETE authorization（第30行） | 接口匹配。`router.py:72`、manager.py:129；use-authorization.ts:72 取消成功才关闭，404作为已清理。 |
| DELETE根移除（第31行） | 匹配。`router.py:77`、store.py:117仅清绑定加revision；AccountPage.vue:27二次确认和第52行发送版本。 |
| Account/Authorization字段、Unix秒、错误结构（第33、35行） | 匹配。`schemas.py:35`、46；manager.py:75只公开白名单，expiresAt来自time.time；client.py:34保留允许HTTP状态，异常为固定503；前端 `api/codex-auth.ts:21`、27校验契约。 |
| socket长度/时限/固定业务（第37行） | 匹配。`client.py:12`、19请求16KiB/响应128KiB及8秒总预算；`service.py:62`、69匹配framing；每socket固有manager。测试client第63行覆盖碎片响应与共同预算，第80行覆盖坏帧。 |
| 生产基线精确增量与旧版本保留（第9行及派发范围） | 代码匹配。`account-package.py:18`只对采集源码追加路由/字段；第54行仅加入API薄层；`account-deploy.py:40`、56检查镜像/文件基线，第65行保留旧镜像；`account-frontend.py:32`备份入口，第81行回退保留hash资源。安装/生产执行尚未完成。 |
| RuntimeDirectoryPreserve、双worker验证后才暴露API | 代码匹配。`account-runtime.py:152`明确Preserve=yes；`account-deploy.py:209`同时验证两worker verified PID及environ新socket，第222行才切API。 |
| 排空后切换、不强停在途任务（第9行） | 代码匹配。`account-worker.py:58`取消接纳，第62行检查队列、active/reserved/scheduled和DB，第67行连续两次idle才systemctl stop；失败且未尝试停服时恢复接纳（第77行）。`account-deploy.py:257`要求stopped证据后才写override。未执行生产排空。 |
| 回退不恢复旧token、不撤销独立绑定、不强停任务 | 代码匹配。`account-deploy.py:245`要求两API先回旧版，第249与260行两次要求业务revision=0，回退仍走drain-stop；无恢复凭据或DB路径。release-tests第76行验证已换账号时拒绝回退且不触发排空。 |
| 全测试、构建、生产就绪/正式页面冒烟（第9行） | **未验收完整。** 局部独立结果如下；全后端仍有失败待主 Agent定位；官方真实登录完成/启用未由本reviewer测试；实际安装、正式页面及生产健康待部署。QA.md明确尚未完成，不得拿局部绿灯宣称全量通过。 |

## Spec 漂移

未发现额外业务页面、数据库表或任务操作。新runtime、状态文件和发布工具服务于合同；`store.py:114`保留旧私有grant不会撤销授权，移除没有删除共享源。独立preview的演示控件不在正式src页面中。这里只评价本轮新增功能，未重审整套既有产品Spec。

## 独立验证原始输出与限制

独立执行后端六个文件：

```text
.venv/Scripts/python.exe -m pytest -q tests/test_account_management_api.py tests/test_account_management_client.py tests/test_account_management_state.py tests/test_account_management_linux.py tests/test_managed_credentials.py tests/test_credential_broker.py
...........................................................ssss......... [ 51%]
.................sss...s......s......sssssssssssssssssss.......s....s    [100%]
111 passed, 30 skipped, 2 warnings in 8.88s
```

exit_code=0；两个warnings为Starlette测试客户端弃用提示。**此测试在主Agent已添加两项身份漂移修复测试后运行，因此111不属于原送审快照（原声明109）；它不能替代对新快照的完整审查。** Linux专属socket/文件安全相关跳过不能算Windows验证通过。主Agent声称旧快照Linux隔离94项通过，需在修复新快照上复跑。

独立前端类型检查：

```text
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit
```

stdout/stderr为空，exit_code=0。此次未独立执行生产build；主Agent QA.md记录0.2.54 build通过，但本轮未取得该build完整原始输出，因此不据此写“reviewer编译验证通过”。

独立发布测试原始输出，exit_code=0：

```text
python scripts/release/account-tests.py
.....
----------------------------------------------------------------------
Ran 5 tests in 0.102s

OK
```

## Stage 2

**未执行。** Stage 1 存在HIGH，按code-review skill停止在Stage 1。未给出Stage 2代码质量、安全扫描、测试真实性和邻居页面实际视觉对比PASS。修复、证据补全、重新固定candidate后，由主Agent重新派发审查；review-approve必须指向最终同一快照。
