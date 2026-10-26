# Codex 账号管理修订后独立两阶段审查

- 日期：2026-10-26；执行者：独立 code-reviewer；使用 `.agents/skills/code-review/SKILL.md`。
- 最终 candidateId：`221eb46d7566ebd1c405387eca031661c0a66f4039fd38ada295fab55975e339`。
- **Stage 1：PASS。Stage 2：PASS。结论仅批准上述源码快照，不代表生产发布已经完成。**
- 范围：backend/app/account_management 八模块；credential_broker 兼容扩展；config/main/overseas main；正式前端账号 API、AccountPage、AuthorizationDialog、hooks/style、国内 wrapper、双业务路由和海外 adapter；本轮新增后端/前端测试及海外路由测试；scripts/release/account-*.py（最终七个文件）。已批准 preview 作为视觉合同。用户预存 AGENTS.md 修改不属于本轮功能审查或提交范围。
- 路径约定：下文 `backend/`、`frontend/` 相对 `hengxin-smart-image/`；`scripts/`、`docs/` 相对仓库根。
- 输入原文：`docs/CODEX-ACCOUNT-MANAGEMENT-20261026.md:1` 全文、`Product-Spec.md:1351`、`Design-Brief.md:224`、`DEV-PLAN.md:1571`、`docs/HARNESS-REVIEW.md:1`。本轮没有重新审查整个历史产品功能。

## 快照与审查中变更

开始时独立 review-status 确认 `c4d820148ba5fd021b349ea048f0668cf39b96b7c19be57549fcafc2c9fefaff`。审查发现发布脚本 319 行和海外错误解析问题，主 Agent 分别修订后重新交接：

1. `3a2b5b92ece5daa2fa2d19112db22634c5ca795aa71e022708a00d7889890a74`：安装验收职责从 account-deploy.py 拆到 account-installed-tests.py。已完整读取新 helper、调用方及自动打包 glob；独立重跑发布测试。
2. 最终 `221eb46d7566ebd1c405387eca031661c0a66f4039fd38ada295fab55975e339`：仅账号 API 增加海外业务错误体适配，测试增加双业务真实 Response 回归。已重新读取实现和测试并独立运行 17 项前端专项、类型检查。

审查构建曾临时产生 frontend/dist-review-account，已核对绝对路径在仓库内后移动到忽略目录 output/account-management/reviewer-build；移动后独立 review-status 恢复当时的 3a2b5b 快照。构建产物不属于源码审查或提交。最终结论不沿用旧报告的 PASS；两次修订差异均在本轮复核。报告写入后再次独立 review-status 确认 currentId 仍为最终221eb46d快照。

## Stage 1：合同逐项对照

下表每项均实际读过对应实现；测试和渲染证据见后文。生产执行是下游发布步骤，单独列出，不冒充已完成。

| 合同条目 | 结论、代码证据与验证方式 |
| --- | --- |
| 管理中心追加账号页，其他布局不变（合同3、6行） | 完整实现。`frontend/src/router/modules/index.ts:20` 增加国内入口；`src/identity-main.ts:22` 增加海外路由；`src/views/overseas/OverseasPortal.vue:4`、8 只对账号分支适配外壳；国内 wrapper `src/views/hengxin/admin/codex-auth.vue:1`。已读 diff、打开正式组件和邻居页面实测。 |
| 真实状态、检测、授权、重试、启用、取消、移除、记录（6行） | 完整实现。`AccountPage.vue:3`、9、12、15、21、27；`AuthorizationDialog.vue:5`、16、20、24、30；两个 hook 调用真实 API；正式组件无模拟选择器。专项组件测试实际编译 Vue 模板并触发事件。 |
| 国内、海外各自配置（7行） | 完整实现。`service.py:123` 分别创建 store/manager/control socket；`service.py:85` 依据真实 worker UID 映射业务；`store.py:103` 只写当前 store。state 测试验证另一业务仍引用原 source。 |
| 迁移引用共享主凭据、不复制刷新令牌、不撤销（7、14行） | 完整实现。`store.py:48` 初始化 legacy 标记，`:70` 返回同一原文件；`service.py:93` 沿用 access_credentials；`managed_credentials.py:173` 使用现有刷新锁。`test_account_management_state.py:51` 证明无新 auth.json、副业务/原字节保留。 |
| 独立授权验证并确认后才切换（7行） | 完整实现。`manager.py:149` 限 verified、未过期；`:156` 复核候选身份和剩余寿命；`:159` 校验版本；`store.py:103` 写私有 grant 后原子发布 state。取消与失败不会到该发布路径。 |
| 失败、超时、取消不动当前配置（8行） | 完整实现。`manager.py:179` 临时目录；`:216` 只变 pending；`:227` 清理后结束审计。`test_account_management_state.py:122` 等失败矩阵以及到期/取消用例通过。 |
| 同账号同工作区续接，异账号明确确认（8、17行） | 完整实现。`manager.py:202` renew 异身份转 mismatch；`:154` different 必须 replace 且 acknowledged=true。`managed_credentials.py:66` 身份为 account/sub；`:208` 保留已有会话绑定。state 测试验证两个旧 home 的历史未改、不同身份旧会话被拒绝。 |
| 官方 CLI device-auth、独立 HOME、无密码/上传凭据（12行） | 完整实现。`device.py:17` 写独立 file-store config，`:20` 清洁环境，`:24` 官方 login --device-auth，`:28` 期限/输出上限，`:38` 停进程；`AuthorizationDialog.vue:45` 限官方链接。真实 CLI 获取/取消证据由主 Agent 提供，本 reviewer 没有完成真实账号登录。 |
| 主凭据留宿主，API只接管理 socket（13行） | 完整实现。`client.py:28` 服务端配置选 socket；`account-package.py:51` API只含client/router/schemas；`account-deploy.py:74` 只 mount 当前业务 runtime 子目录，未 mount private/auth。源码和发布覆盖 diff 验证。 |
| worker access-only 协议兼容（13行） | 完整实现。`credential_broker.py:30` 获取 peer UID，`:37` 虚方法派发；`:53` 旧 broker 默认行为保持；`service.py:88` 业务 source 查询；`managed_credentials.py:190` 清空 refresh_token。既有凭据/broker回归通过，Linux专属本机跳过如实标注。 |
| 移除仅清绑定、不logout/revoke、不删共享源（14行） | 完整实现。`store.py:117` 仅 generation=None、revision+1、审计；`AccountPage.vue:27` 二次确认。state测试实际验证原源和另一业务保留。 |
| 单候选、管理员所有权、配置版本（15行） | 完整实现。`manager.py:79`、`:83` 清理完成前拒绝第二流程；`:115` 所有者校验；`store.py:99` CAS；API不接受actor。到期阻塞探测用例验证第二次start被拒绝。 |
| 确认时复核原身份（15行） | 完整实现，旧HIGH已关闭。`manager.py:160` 对所有 configured intent重读；读取失败409，不等于previous亦409。renew、replace外部源漂移回归独立通过；不能再用旧different=false绕过。 |
| 取消、超时、重启清候选（15行） | 完整实现，旧MEDIUM已关闭。`manager.py:180` cancelled含expiresAt；`:84` 仅cleanupComplete才释放名额；`:238` 在TemporaryDirectory退出后标记完成；`:25` 重启清临时目录；`service.py:119` daemon独占锁。期限测试断言取消回调为真且清理前新start失败。 |
| 隔离最小真实请求、不读业务、不建任务、不续用户会话（16行） | 完整实现。`probe.py:20` 随机临时目录、`:24` 随机workspace ID、`:25` 禁Skill、`:27` read-only最小请求；`workspace.py:82` 等仅绑定临时home/work与固定运行库，不挂业务目录。新模块没有业务DB写入。 |
| 网络故障不误报失效，检测带时间（16、17行） | 完整实现。`probe.py:16` 刷新不确定性返回network，`:43` 完整成功事件+精确回应才ready，`:47` 明确认证拒绝才expired；`manager.py:68` 更新checked；`store.py:17`北京时间；初态unchecked。 |
| 真实身份与工作区，不按邮箱判定（17行） | 完整实现。`store.py:28` 使用真实account ID作工作区展示；`managed_credentials.py:66` 验证account/sub及access identity；前端不算different，直接使用服务端字段。相同邮箱/不同workspace测试证明门禁。 |
| 不改模型、Skill、任务、会话、成品，不自动重跑（18行） | 完整实现。本轮diff不改runner/model/业务数据逻辑；probe专用model仅用于临时检测；`AccountPage.vue:9`、25与`use-account.ts:31` 明确用户回任务手动重发。 |
| 国内manage_system、海外settings.manage（19行） | 完整实现。`router.py:14` 实际会话解析与权限检查；`frontend/src/api/overseas/management.ts:5`正确能力映射。API测试用真实会话/角色记录验证撤权、禁用用户和跨业务cookie拒绝。 |
| 所有修改都有browser_request（19行） | 完整实现。`router.py:39`定义WRITE，六个修改端点均引用；API参数化测试逐端点验证缺header/恶意Origin拒绝。 |
| 审计四字段、不含令牌与授权码（19行） | 完整实现。`store.py:94`固定字段，`manager.py:69`、110、231固定动作/结果，不记录CLI输出；响应schema白名单过滤。state/API测试对secret-refresh、code、token等作负断言。 |
| 前缀固定、客户端不传业务/路径（22行） | 完整实现。`main.py:55`、`overseas/main.py:47`固定路由；`router.py:28`拒绝query；`schemas.py:7` strict/forbid extra；`client.py:31`生成actor。注入字段测试被422拒绝。 |
| GET根Account（24行） | 完整实现。`router.py:42`；`store.py:77`；`schemas.py:35`。 |
| POST check + GET轮询（25行） | 完整实现。`router.py:47`；`manager.py:44`异步，`:67`防旧revision结果覆盖；`use-account.ts:7`按checking轮询。 |
| POST authorizations intent/revision（26行） | 完整实现。`router.py:52`；`schemas.py:11`；`manager.py:79`。 |
| GET本人流程（27行） | 完整实现。`router.py:57`；`manager.py:115`、125。异管理员403回归。 |
| POST retry（28行） | 完整实现。`router.py:62`；`manager.py:140`只允许有source且未到期failed；hook实接retry。 |
| POST activate acknowledged（29行） | 完整实现。`router.py:67`；`schemas.py:16`严格布尔；`manager.py:149`包含两种身份复核及CAS。 |
| DELETE流程取消（30行） | 完整实现。`router.py:72`；`manager.py:132`；`use-authorization.ts:72`成功才close，404按已清理处理。 |
| DELETE根revision移除（31行） | 完整实现。`router.py:77`；`store.py:117`；`AccountPage.vue:52`传当前revision。 |
| Account、Authorization结构/Unix秒/现有错误结构（33、35行） | 完整实现。`schemas.py:35`、46；`manager.py:75`公开字段白名单；`client.py:34`错误状态白名单；前端 `codex-auth.ts:21`、27校验。海外错误message适配位于`:34`，真实409→hook回归证明修复。 |
| 管理socket framing/上限/UID（37行） | 完整实现。`client.py:12`16KiB/128KiB、8秒预算；`service.py:60` SO_PEERCRED、`:62`5秒接收；`:25`精确action字段；每socket固有manager。client分片/超限/坏帧测试通过；Linux socket证据边界见后文。 |
| 构建发布保留旧版，排空再切换（9行） | 发布实现完整。`account-package.py:18`精确patch原API源码；`account-deploy.py:40`基线校验、`:65`保留旧镜像；`account-worker.py:54`停止领取后检查active/reserved/scheduled/DB，连续两次idle才stop；`account-deploy.py:187`两worker verified后才切API。尚未执行生产安装/排空/部署。 |

没有“部分实现”或“未实现”的源码条目；生产安装测试和发布后健康/页面冒烟仍待主 Agent执行，属于合同第9行的后续验收，不能据本报告宣称整个交付完成。

## Stage 2：质量、安全、测试真实性与视觉

### 已发现并关闭的问题

- **MEDIUM，文件大小/职责**：原account-deploy.py共319行；最终拆出 `scripts/release/account-installed-tests.py:5` 安装验收职责，调用点 `account-deploy.py:116` 仍先state校验。最终297行/helper30行；`account-package.py:75` glob自动纳入新文件。独立release 5项再次通过。
- **MEDIUM，海外真实错误解析/测试盲区**：原 `codex-auth.ts:34` 直接复用identity helper，而 `backend/app/errors.py:16` 返回message、helper只读detail；清理409被覆盖成成员管理提示，`use-authorization.ts:49`无法触发短重试。原测试直接throw IdentityError掩盖解析层。最终 `codex-auth.ts:34` 仅本页适配实际业务错误message到detail；`tests/codex-auth.test.ts:106`国内/海外各用真实Response经过API再进hook，均重试到第3次start且错误清空。已独立复跑确认。

### 安全与结构结论

- 通过：新生产模块/组件/发布文件均不超过300行；manager243、service143、store124，UI职责分为API/schema/hooks/page/dialog。前端新增生产代码无any；Python grep命中any为内建量词函数。依据上述文件及独立行数检查。
- 通过：限定扫描未发现硬编码API密钥、eval、innerHTML、dangerouslySetInnerHTML、前端VITE秘密变量。设备登录与发布命令均使用argv，无shell=True；主凭据路径为宿主运行配置，不下发HTTP。`device.py:24`、`service.py:98`、`account-runtime.py:28`。
- 通过：凭据文件复用no-follow目录访问、单链接/普通文件验证、0600写入、原子replace+fsync；`managed_credentials_files.py:12`、21、52、82。新状态和grant使用同一访问层，`store.py:61`、108。
- 通过：API仅允许10001，worker按1001/999映射；访问令牌返回前清refresh；每业务mount独立。`service.py:60`、85、126；`account-deploy.py:74`。未发现跨业务客户端可控路由或文件路径入口。
- 通过：发布不写任务数据库、不恢复token。回退worker前要求两API已回旧版、两业务revision为0，并在排空后再次检查；`account-deploy.py:224`、237。静态发布先备份、拒绝hash资源碰撞，回退保留两代资源；`account-frontend.py:24`、70。发布5项包含拒绝已换账号的旧broker回退且断言不启动排空。
- 测试真实性通过：状态测试将两个旧会话home实际sync到新grant，再核验history原样、refresh为空；到期测试用真实线程事件阻塞verify并断言取消回调、第二流程拒绝；API测试使用实际会话和权限记录，只有宿主exchange隔离。前端测试真实编译模板，Element Plus通过stub测交互，视觉另有真实浏览器补足。对应 `test_account_management_state.py:64`、180、`test_account_management_api.py:76`、94、180、`codex-auth-component.test.ts:28`、85。
- 无Spec漂移：没有新增业务表、任务操作、模型设置或额外产品页面。私有grant、管理daemon和发布工具直接服务合同；保留旧grant用于恢复符合“不撤销原授权”。`store.py:114`、`account-package.py:63`。

### 实际视觉对比

独立浏览器打开3035隔离API下的正式AccountPage/AuthorizationDialog及线上既有海外系统配置页面（只读，没有保存配置）。新页面、邻居均实际查看截图；DOM测量结果：

```text
新账号页: {bg:'rgb(255, 255, 255)',buttonHeight:32,cardX:259,font:'14px',padding:'23px',radius:'16px'}
既有系统配置: {bg:'rgb(255, 255, 255)',buttonHeight:32,cardX:259,font:'14px',padding:'23px',radius:'16px'}
```

卡片、按钮、侧栏、字体与邻居一致。正式style相对批准preview仅移除演示控件样式、补长文本换行，原24×36间距、8px授权码区域圆角、760px断点保持；`style.css:2`、11、14。preview顶部演示栏属于验收外壳，正式 `AccountPage.vue:1` 不含该栏。已实点重新授权和取消，弹窗关闭后fixture原账号保持，未把fixture流程冒充官方授权成功。

独立查看新的 `output/account-management/dialog-390.png` 为真实390×844画面；配套bounds原始数据：dialog x12、width366、top112.359、bottom731.641，footer bottom715.641，无横向溢出；取消和正文在屏内。`style.css:8` 内部高度上限和overflow:auto保证溢出可滚动。旧窄屏截图问题关闭。

## 独立验证原始输出

后端六文件（账号API/client/state/Linux + 既有managed_credentials/broker）：

```text
.venv/Scripts/python.exe -m pytest -q tests/test_account_management_api.py tests/test_account_management_client.py tests/test_account_management_state.py tests/test_account_management_linux.py tests/test_managed_credentials.py tests/test_credential_broker.py
............................................................ssss........ [ 50%]
..................sss...s......s......sssssssssssssssssss.......s....s   [100%]
112 passed, 30 skipped, 2 warnings in 8.75s
```

exit_code=0。两个warnings为Starlette/httpx及anyio别名弃用。30个跳过为平台相关，不能称Windows验证了Linux SO_PEERCRED/no-follow。

最终前端专项原始摘要：

```text
node node_modules/tsx/dist/cli.mjs --test tests/codex-auth.test.ts tests/codex-auth-component.test.ts
✔ domestic: 真实业务409错误体驱动清理后的自动重试 (807.9121ms)
✔ overseas: 真实业务409错误体驱动清理后的自动重试 (815.9682ms)
ℹ tests 17
ℹ suites 0
ℹ pass 17
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 2901.5
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit
```

组合命令exit_code=0，typecheck stdout/stderr为空。

独立生产模式构建在海外错误适配前执行；最终适配后类型检查和17项测试已重新通过。构建原始输出节选（省略资源清单）：

```text
node node_modules/vite/bin/vite.js build --outDir dist-review-account
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 4695 modules transformed.
rendering chunks...
computing gzip size...
✓ built in 35.22s
```

exit_code=0。这是源码编译验证，不是正式版本化发布包；产物已移动到output/account-management/reviewer-build。

主Agent在最终修订后重新执行全前端测试与生产构建，reviewer实际读取原始日志 `output/account-management/frontend-final-tests.log`、`output/account-management-frontend-build.log`，没有冒称这些命令由reviewer执行：

```text
ℹ tests 413
ℹ suites 0
ℹ pass 413
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9205.4902
dist/assets/index-vDEdcYZV.js                                                             963.71 kB │ gzip: 307.80 kB
✓ built in 36.13s
```

正式版本化打包与安装仍由主Agent负责。

最终发布脚本独立测试：

```text
python scripts/release/account-tests.py
.....
----------------------------------------------------------------------
Ran 5 tests in 0.090s

OK
```

## 环境和发布验收边界

主 Agent 提供的跨平台证据：Windows大套件2462通过/405跳过/8失败，8个来自未修改的POSIX安全打开路径；Linux独立venv运行对应三个业务文件及账号API/client/state/Linux共82通过，2warnings、15.03s。但该Linux拷贝为身份/到期修复前state12版，因此它只支持平台归因，不能替代最终源码安装测试。较早Linux四凭据文件94通过也不是最终快照。最终发布的account-installed-tests.py:13要求实际安装源码的Linux专项无failed且无skipped，失败则不得进入start；该门禁后续必须实际通过。

官方CLI真实设备码获取→取消清理、access-only最小模型探测通过属于主Agent提交的实机证据（output/account-management/QA.md:6），reviewer未完成账号登录、启用或修改生产绑定。上线后的真实权限入口、就绪检查、两个worker socket、正式页面冒烟由主 Agent执行并单独记录。不得把本报告的代码两阶段PASS扩张为这些生产步骤已验收。

没有未关闭的HIGH/MEDIUM审查发现。由主Agent用最终candidate、本文路径和两阶段PASS执行review-approve；本报告不写clean、不执行提交或生产变更。
