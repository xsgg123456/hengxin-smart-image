# 海外会话热修复最终独立审查

- candidateId：`b3cddd7cba1ae500a7cf89b7eb76c8670bc8973a15f6893377db737084d4588b`
- 结论：**Stage 1 PASS；Stage 2 PASS**。未发现本次范围内阻断问题。
- 范围：`Product-Spec.md:965` 开始的三段修订（去部门、窗口恢复重验、张帅全部权限）；IdentityPortal、revalidate、OverseasMembers、management-adapter、两份新增测试、前端版本和两份静态发布脚本。不是全项目历史需求重新验收，不代表生产前端已经发布。
- 方法：独立新实例读取 code-review skill、源需求、代码及首轮报告；独立执行 10 项重验/组件测试与 4 项发布测试；读取完整构建/全量测试结果；打开本地正式构建的成员列表、编辑弹窗及相邻海外首页实际观察。未修改产品代码、执行生产写操作或登记批准。
- 审查开始及结束 `review-status.currentId` 均等于上述 candidateId，未发现审查期间代码快照变化。由主 Agent 对该编号执行 review-approve；未写 `.needs-review`。

以下 `src/`、`tests/` 路径相对 `hengxin-smart-image/frontend/`。

## Stage 1：Spec Compliance

| Spec 项目 | 结论和证据 |
| --- | --- |
| 成员列表不展示部门 | 完整实现。`src/views/overseas/admin/OverseasMembers.vue:97` 列定义只有姓名、角色、状态、操作；实际浏览器列表同样四列。 |
| 编辑弹窗无部门输入或必填校验 | 完整实现。`OverseasMembers.vue:24` 表单只有姓名、海外角色、账号启用；`management-adapter.ts:40` 已删除部门非空限制，兼容属性仍可为空。真实弹窗与 `output/session-hotfix-members-dialog.jpg` 一致。 |
| 搜索提示仅姓名，兼容协议保留，无破坏性迁移 | 完整实现。`OverseasMembers.vue:9,47`、`src/api/overseas/members.ts:7,20` 保留兼容数据；本候选无后端/数据库修改；浏览器搜索框提示“搜索姓名”。 |
| focus / visibility 恢复重新检查并合并 | 完整实现。`src/views/auth/IdentityPortal.vue:119` 的 resume 与 `:124` 事件注册；`src/api/identity/revalidate.ts:21` 复用运行中 Promise。真实 SFC 测试 `tests/identity-portal-lifecycle.test.ts:56` 连续发两事件、断言初始加载加一次检查共 2 次身份请求。 |
| 同一有效身份保留页面、筛选/草稿，不跳业务入口 | 完整实现。`IdentityPortal.vue:2,54` 更新 member 但不触发 busy/清空成员；key 使用成员 ID；`src/views/overseas/OverseasPortal.vue:43,50` 监听能力值而非对象身份。同身份测试 `identity-portal-lifecycle.test.ts:55,59,63` 断言没有卸载、hash 保持。 |
| 核验期间阻止操作，包括 teleport | 完整实现。`IdentityPortal.vue:56` 设置 `document.body.inert`，不再只锁根容器；`revalidate.ts:24,35` 管理起止。实际依赖 `node_modules/element-plus/es/components/message-box/src/messageBox.mjs:9` 挂 body，dialog-content2.mjs:40 使用普通 div，不是 showModal 顶层原生 dialog，因此在 body 的 inert 范围内。SFC 测试 `:58,62,66` 核验锁定、完成/卸载释放。 |
| 失效、撤权、服务错误拒绝旧身份 | 完整实现。`revalidate.ts:32` 转入 reject，`IdentityPortal.vue:45` 清 member 和状态；`src/api/identity/auth.ts:12,29` 仍要求 active/有效角色，未放宽鉴权。真实 SFC 的 401/403/503 用例均断言子树卸载、解除锁定。 |
| 换号销毁旧页面，退出/切换后晚返回不恢复旧身份 | 完整实现。`IdentityPortal.vue:2` 的 ID key 更换触发旧树销毁；`:107,109,125` 切换、退出、卸载均 invalidate；`revalidate.ts:15,28,30,33,35` 以代次保护成功、错误和 finally。`tests/identity-revalidate.test.ts:33,41` 分别覆盖晚返回与新身份/新能力。 |
| 张帅五角色、八能力；其他超级管理员默认矩阵不变 | 完整实现。读取生产只读核验产物 `output/overseas-grant-verified.json:1`：张帅 active，五角色与八能力齐全，审计 update、2026-10-13 03:01:39.387856+00:00、auditRolesMatch=true。`output/overseas-grant-verify.py:12` 核对精确账号、角色集合及其审计；授权脚本 `output/overseas-grant-all.py:16` 只对指定成员调用正式 patch_member，本候选无全局角色矩阵修改。生产核验由主 Agent 执行，本 reviewer 独立读取并核对产物及脚本，没有重复写授权。 |

部分实现：无。未实现：无。Spec 漂移：无新增业务页面、API、数据库表或扩大其他账号默认权限；发布版本变更对应本次热修复。

### 首轮 HIGH 的复核

首轮只锁业务根节点，body 浮层仍可操作的问题由 `IdentityPortal.vue:59` 的 body.inert 修复。[MDN inert 语义](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/inert)确认普通后代不能接收点击/焦点；上述本地依赖源码证明本项目浮层属于该范围。

成员禁用确认在 `OverseasMembers.vue:79` 标记正在确认，`:83` 等待后先检查 active，`:99` 卸载时关闭 MessageBox。失败/换号卸载后不会继续 save。相邻执行确认已有 `src/views/overseas/OverseasExecution.vue:27,57,75` 的关闭和 alive/epoch 防护。普通 Vue teleport 随所属子树卸载。未发现本次引入的确认浮层残留或晚返回重新挂回旧身份路径。

## Stage 2：Code Quality

- **结构与类型 PASS**：`revalidate.ts:3,12` 依赖接口明确、单一职责，39 行；IdentityPortal 133 行、OverseasMembers 100 行、management-adapter 142 行，未超过 300 行。新增业务代码未发现 any。异常与超时仍通过 `src/api/identity/request.ts:5,13,15` 统一封装。
- **竞态处理 PASS**：`revalidate.ts:15` invalidate 先推进代次并清运行句柄；旧请求成功、失败、finally 均检查 epoch，不会清掉新检查的 pending，也不会覆写新账号。业务失败 `IdentityPortal.vue:46` 同步 invalidate，随后清旧子树；退出/切换同样失效化。
- **安全扫描 PASS**：对本次业务文件检查硬编码密钥、危险执行、HTML 注入与前端秘密变量，未发现新增命中。`tests/identity-portal-lifecycle.test.ts:51` 的 new Function 仅执行本仓库 SFC 编译结果用于测试，输入来自 `:20` 固定源码文件，不接收远端或用户脚本，不进入产品构建。
- **测试真实性 PASS，有明确覆盖边界**：`identity-portal-lifecycle.test.ts:20,51,54` 编译并挂载实际 IdentityPortal，使用 Vue 真 renderer，能证明事件绑定、挂载/卸载和失败路径，不是只测纯函数。子页面与 DOM host 被替代，所以 `:58` 证明 body.inert 属性设置，不证明浏览器真实键鼠行为；草稿 ref 在测试外部，`:65` 的值断言单独不足以证明内部表单保持，主要证据是 `:59` 的不卸载断言加真实代码 key/响应式链。换号 remount、真实 MessageBox 关闭尚无专门集成用例，是非阻断的测试增强项，不能把本报告说成完成了这些浏览器故障注入测试。
- **视觉对比 PASS**：独立打开 `http://127.0.0.1:3016/?workspace=identity#/overseas/admin/users`，查看列表、编辑弹窗，再点击海外业务首页。1280×720 视口下共享侧栏宽约 230px、内容起点 x≈259、卡片 y≈226、标题/按钮/浅色背景一致；与 `output/css-hotfix-production-members.jpg` 历史正式页面对照，同一布局中仅去掉部门列及提示。新弹窗截图 `output/session-hotfix-members-dialog.jpg` 1280×900，姓名/角色/开关/底部按钮完整。对应 `OverseasMembers.vue:2,9,24` 与 `OverseasPortal.vue:2,4,10`。本次没有新的设计稿，不自行要求重新设计。
- **发布差异 PASS**：`scripts/release/frontend-static.py:23,39,71,73` 版本和前置版本切换为 0.2.23→0.2.24；`scripts/release/test_frontend_static.py:19` 对应更新，独立 4 项测试通过。未执行发布。

## 原始验证输出

独立执行 `pnpm exec tsx --test tests/identity-portal-lifecycle.test.ts tests/identity-revalidate.test.ts`，exit code 0：

```text
✔ 真实IdentityPortal组件重验：同身份保留草稿，含挂body弹层锁定 (9.9595ms)
✔ 真实IdentityPortal组件重验：401，含挂body弹层锁定 (3.2839ms)
✔ 真实IdentityPortal组件重验：403，含挂body弹层锁定 (2.0683ms)
✔ 真实IdentityPortal组件重验：503，含挂body弹层锁定 (1.519ms)
✔ focus和visible并发只核验一次；核验前不替换成员及页面状态 (0.9296ms)
✔ 重验401拒绝旧身份且解除等待 (0.2732ms)
✔ 重验403拒绝旧身份且解除等待 (0.122ms)
✔ 重验503拒绝旧身份且解除等待 (0.0871ms)
✔ 退出或切换后晚返回的重验不得恢复旧账号 (0.2344ms)
✔ 真实换号和撤权返回服务端新身份，不复用旧权限 (0.7435ms)
ℹ tests 10
ℹ suites 0
ℹ pass 10
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1422.6417
```

独立执行 `python -m unittest scripts/release/test_frontend_static.py`，exit code 0：

```text
....
----------------------------------------------------------------------
Ran 4 tests in 0.115s

OK
```

编译证据为读取主 Agent 本候选日志 `output/overseas-session-hotfix-build.log`，未重复执行构建。原始摘录：

```text
> hengxin-smart-image-frontend@0.2.24 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ built in 31.42s
```

全量测试证据读取 `output/overseas-session-hotfix-tests.log`：

```text
ℹ tests 292
ℹ suites 0
ℹ pass 292
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 7667.4826
```

工具同时输出既有 pnpm 配置告警：`The "pnpm" field in package.json is no longer read by pnpm.`，涉及 `pnpm.overrides` 与 `pnpm.onlyBuiltDependencies`；本次未新增/修改依赖配置，不将该告警描述为编译失败。

## 验收边界

本报告批准上述代码候选的两阶段审查。真实浏览器只验证本地构建布局；焦点去重/同身份保持/失败销毁来自独立真实 SFC 测试与代码证据。未完成真实浏览器悬挂请求下的鼠标和键盘拦截测试，也未替代主 Agent 发布后生产冒烟检查。生产权限核验来自已保存的只读结果和审计，不包含凭据。
