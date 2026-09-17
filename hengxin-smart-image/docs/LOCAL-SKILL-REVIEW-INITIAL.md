# 本地 Skill 登记独立审查 · 第一轮

审查日期：2026-09-17。原候选 `b840c020fe4867e74c1670d5060b57a147f3b158ccf25268c338f46564cda8e0`。

范围：本轮所有未提交业务代码与新增文件，包括 backend 的登记/检查/执行/契约/迁移/测试、frontend 的管理页面/API/类型/mock/测试、infra 配置；依据 Product-Spec.md:475–483、Design-Brief.md:23、DEV-PLAN.md:3–11、LOCAL-SKILL-RELEASES.md。不审定历史全项目验收，不部署 VPS，不调用模型。

**Stage 1：FAIL。Stage 2：尚不能批准；附质量预检查记录。禁止为原候选登记两阶段 PASS。** 未发现 HIGH；存在以下 MEDIUM。审查中主 Agent 已安排修复说明字段，并实际观察到 contracts/management.py、models.py、local_service.py、service.py、0012 迁移等发生改变。该修复必须随新 candidate 完整复核，本报告不能覆盖新快照。开发服务器还重写了生成声明 components.d.ts，主 Agent 已说明将恢复 HEAD；它不是本轮功能范围。

## 问题

### M1：版本说明在真实后端丢失（原候选 MEDIUM，修复已写入、待新候选复核）

- Spec:477 明确登记字段包含说明，前端 skills.vue:39 接收说明、:44 版本记录显示说明。
- 原候选 local_service.py:25 只在新 Skill 创建时将说明写入 SkillRecord；第二版本输入被丢弃。原候选 contracts/management.py:143 的 ManagedSkill 无 description，service.py:103–107 的 DTO 也不输出；真实页面连首次说明也无法显示。
- mock-management-skills.ts:36 却按版本返回 description，导致 mock 浏览器验证掩盖真实差异。
- 修复要求：按版本持久化并返回说明，历史 ZIP 有明确回退；HTTP 两版本不同说明、空说明、历史数据和迁移均应覆盖。审查中已看到实现修复，不能据此批准旧 candidate。

### M2：语义版本校验不符合约定（MEDIUM，待修）

- Spec:477 指定语义版本。contracts/management.py:160、skills.vue:79、mock-management-skills.ts:34 使用宽松且不完整的版本正则。
- 实际运行 SkillRegisterInput 的输出：

```text
01.0.0 ACCEPT
1.0.0-alpha..1 ACCEPT
1.0.0-01 ACCEPT
1.0.0+build.1 REJECT
```

- 前三项是非法 SemVer，最后一项合法。[SemVer 2.0.0 第 2、9、10 条](https://semver.org/)明确要求数字无前导零、预发布标识非空，允许构建元数据。
- 修复要求：后端、页面和 mock 一致校验严格 SemVer，保留路径安全及长度限制；补上述边界测试。问题不构成路径穿越。

### M3：mock 与真实接口的重复登记规则不一致（MEDIUM，待修）

- models.py:13 的 Skill 唯一键为 `(name, mode)`，:22 的版本唯一键为 `(skill_id, version)`；local_service.py:22–23 按 name、mode 查找 Skill。
- mock-management-skills.ts:35 仅按 name、version 判重，忽略 mode。同标识、同版本分别登记 text 与 wallpaper，真实接口可登记，mock 会 409；分组页面本身沿用名称与处理类型分组。
- 修复要求：mock 判重补处理类型并覆盖跨类型用例，或者先明确变更真实唯一性约束。不要以不一致的 mock 用例证明真实登记行为。

## Stage 1 逐项核对

以下代码位置以原候选读取时为准，说明修复可能使后续行号偏移。

| Spec 条目 | 结论与证据 |
|---|---|
| :475 停止新 ZIP 上传，保留历史来源/执行 | 实现。router.py:37–39 返回 410；models.py:28 来源默认 zip；materials.py:67–78 分离本地与原对象读取/ZIP 校验，旧包哈希未改。历史安装后端 router.py:70 保留。v0.25 替代历史新增/安装网页流程，删除旧 ZIP 安装按钮不独立判为缺陷。 |
| :477 固定发布根目录，标识/版本定位 | 部分实现。config.py:26 指定根；local_tree.py:36–42 校验输入并组合目录；任意路径拒绝。语义版本存在 M2。 |
| :477 登记可先于部署，初始不可用 | 实现。local_service.py:20–36 只登记数据，状态 pending、空 checksum、无对象；router.py:79–82 禁止未验证启用；test_local_skills.py:29 断言 pending、无对象及 409。说明存在 M1。 |
| :478 管理员拥有、执行用户不可写 | 实现。local_tree.py:20–25 拒绝 Worker 所有或可写对象；:44–48 检查全部祖先；:59 校验每个成员。test_local_skills_linux.py:91 覆盖 Worker 所有与可写成员，执行降权为 nobody。 |
| :478 拒绝链接、越界、特殊与大小超限 | 实现。local_tree.py:46、:57–68 校验目录、符号/硬链接、普通文件与目录、数量、大小；:71 O_NOFOLLOW，:74 校验 inode/device，:78 检查大小和时间变化。test_local_skill_tree.py:37、test_local_skills_linux.py:91 提供对应断言。 |
| :478 完整文件树独立哈希 | 实现。local_tree.py:28–32 对排序后的路径和内容摘要散列，:62 包含空目录；:85 固定期望 checksum；package_validator.py:83 保留旧 ZIP 原始字节哈希。test_local_skill_tree.py:20 验证空目录、脚本与漂移。 |
| :479 真 Worker 异步检查 | 实现。local_service.py:47–55 原子 Job/Outbox；worker/tasks.py:62–64 路由；skill_check.py:31 claim、:35 heartbeat、:52–54 token/status/租约检查；outbox.py:27–30 支持过期非生成作业重新投递。 |
| :479 不执行 Skill 脚本/不调用 AI，实际隔离依赖检查 | 实现。local_skill_probe.py:12–40 固定探针仅遍历/读取、which、顶层 find_spec；:53–56 用实际 sandbox_command 替换最终命令为可信 /usr/bin/python3 -I 探针；不执行声明可执行文件，也不导入 Skill 内模块。test_local_skills_linux.py:59、:110 验证有毒脚本不执行及真实依赖缺失。 |
| :479 校验通过未启用、重检撤下、哈希不可覆盖 | 实现。local_service.py:53 设置 checking；skill_check.py:58–64 抑制哈希覆盖、只转 verified/invalid；router.py:76–87 独立显式启停；test_local_skills.py:65 覆盖重检、目录漂移、旧 hash 保留与重复作业。 |
| :480 分组、默认绑定、权限、审计 | 实现（mock 重复规则见 M3）。skills.vue:5–28 沿用分组、展开、默认组件；router.py:20 的 Admin 依赖保护全部管理变更；local_service.py:14–17、:34、:54、:70 写审计，router.py:84 写状态审计。test_local_skills.py:29 覆盖三个非超管角色 403。 |
| :480 无引用/无在途才移除且不删目录 | 实现。local_service.py:57–76 锁版本、检查 DTO 引用/默认/检查状态/当前 Job，FK 竞态返回 409；仅 session.delete。service.py:94–103 同时检查模板历史版本、任务和默认。test_local_skill_execution.py:49、test_local_skills.py:132 覆盖引用保护。 |
| :480 错误、加载、空态 | 实现。skills.vue:4–5、:41、:80–95 展示错误、加载、空文本及取消/操作防重；AdminPreview.vue:3 明确 mock。浏览器实际查看桌面列表和登记表单，截图见下。主 Agent 另提供错误/空态截图，未把它们算作真实 API 联调。 |
| :481 每轮固定版本、只读挂载、不解包、不暴露根 | 实现。materials.py:64–74 用 task.skill_version_id 和快照 checksum 调 validate_local 后直接设置 local_skill；workspace.py:84–85 仅 ro-bind 对应版本到 /work/skill。test_local_skill_execution.py:20 断言无 work/skill 副本与原绑定；test_local_skills_linux.py:66 验证写入 EROFS、邻居路径不可见。 |
| :481 缺失/变化/依赖失败不回退 | 实现。skill_check.py:15–25 在 probe 前后校验固定树；materials.py:70–72 包装部署失败；diagnostics.py:14 提供用户错误及不自动切换提示。无其他版本回退分支。 |
| :482 固定模板/任务、停用新任务、历史返工 | 实现。templates/service.py:115–119 保存固定版本；tasks/service.py:50–52 保存版本与 hash，:80 后续轮次重用 task；tasks/snapshots.py:54–58 锁版本并只接收 available；materials.py 不要求旧任务绑定仍 available。新版本启用/默认切换不修改旧任务。 |
| :482 Home/会话/素材/结果/控制隔离保持 | 实现。workspace.py:19–47 仍按 task/round 创建 Home/work/control，:82 只绑定任务 Home/work；local_skill 是新增单独只读挂载，未扩展全局 Skill 或认证目录。 |
| :483 验收覆盖与生产边界 | 部分证据自跑，其他为交接证据。下列测试原始输出与 LOCAL-SKILL-VALIDATION.md 区分记录；没有执行 VPS 部署或真实模型生图。 |

## Stage 2 质量预检查（不构成批准）

Stage 1 的 MEDIUM 尚未关闭且候选已变化；以下为主 Agent 要求的继续检查记录，正式两阶段 PASS 留给新快照复核。

- 文件结构：新增 local_service.py、local_tree.py、skill_check.py、local_skill_probe.py 各自分担 HTTP 状态、文件树、作业租约、隔离探测；扫描本轮变更 Python/TS/Vue 文件未超过 300 行。未引入新 `any`。异常分层位置为 materials.py:70–72 与 skill_check.py:44–48。
- 测试真实性：test_local_skill_tree.py:13 明确 mock 权限，仅验证元数据/哈希；test_local_skills_linux.py:46–49 真正降权，后者才支持权限与 bwrap 结论。test_local_skill_execution.py:20 是材料层测试，mock validate_local，不等于真实生图/CLI 返工验收。PG 并发/迁移证据来自主 Agent 指定的隔离库运行，未由本 reviewer 重跑。M1/M3 说明 mock 与真实契约仍存在测试盲区。
- 安全预检查：本轮新 Skill/执行代码、管理页面搜索 eval、innerHTML、dangerouslySetInnerHTML、暴露的 VITE KEY/SECRET/TOKEN、sk-ant/sk-proj、shell=True，无命中；SQL 走 SQLAlchemy 参数查询。local_skill_probe.py:57 subprocess 采用 argv、close_fds 与超时。未发现新增密钥或注入点。
- 文件树竞态边界：local_tree.py:44–78 检查 Worker 不可写祖先与成员，并保护打开文件竞态；skill_check.py:24 再次检查 probe 期间漂移。不能抵御 root 在最终检查后原地修改，LOCAL-SKILL-RELEASES.md:31 已明确管理员不可变发布约定；这是保留信任边界，不宣称绝对不可变快照。
- 视觉实际对比：独立浏览器 session 打开 Skill 管理与邻居系统配置，1280×720 截图 `output/playwright/local-review-skills.png`、`local-review-register.png`、`local-review-settings.png`。两页左边界 259px、卡片顶边约 369px，沿用相同白卡圆角、蓝按钮、标题、提示条及侧栏；表单沿用 ElDialog/ElForm，未新增终端/任意路径/ZIP 文件框。代码为 skills.vue:3–44 与 settings.vue:1 起。没有宣称移动端通过。
- Scope：登记/检查/移除 API、状态、迁移、配置与部署文档均能对应 v0.25；未发现额外页面、后台终端或依赖安装入口。旧 ZIP 安装兼容只保留后端接口，符合本轮替代网页安装方向，不列 scope creep。

## 自行执行的测试/编译原始结果

Windows，CODEX_VERSION=0.153.4；命令 `uv run pytest tests/test_local_skills.py tests/test_local_skill_tree.py tests/test_local_skill_execution.py tests/test_skills.py -q`：

```text
.......................                                                  [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
.venv\Lib\site-packages\starlette\testclient.py:53
  DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
23 passed, 2 warnings in 3.55s
```

`uv run python -m compileall -q app` 原始 stdout 为空，进程 exit 0。

`npm run typecheck`：

```text
npm warn Unknown project config "package-manager-strict-version". This will stop working in the next major version of npm. See `npm help npmrc` for supported config options.
npm warn Unknown project config "manage-package-manager-versions". This will stop working in the next major version of npm. See `npm help npmrc` for supported config options.

> hengxin-smart-image-frontend@0.0.0 typecheck
> vue-tsc --noEmit
```

最终 exit 0，无额外输出。上述测试运行与后续修复存在时间先后，不作为修复后的整体验收。

主 Agent 交接的 658 passed/104 skipped、Linux 9 passed、前端108 passed/构建成功，以及说明修复后30 passed，记录在 LOCAL-SKILL-VALIDATION.md:9–16；本 reviewer 未取得其完整构建原始日志，不能把这些转述当成独立重跑结果。一次临时 HTTP 复现脚本因未加载测试环境而在 Settings 初始化退出，没有产生功能结论。

修复全部差异并恢复生成声明后重新 `review-prepare`，以新 candidate 完成两阶段复核。当前报告不允许 review-approve 原快照。
