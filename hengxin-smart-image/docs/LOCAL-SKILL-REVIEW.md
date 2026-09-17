# 本地 Skill 登记最终独立审查

审查日期：2026-09-17。candidateId：`6b62e18598cb6e4e2232254e9a908d929e07b17b476122e426910bf14c633674`。

**Stage 1：PASS。Stage 2：PASS。无 HIGH / MEDIUM 阻塞；1 项 LOW 测试一致性建议。** 初审 M1/M2/M3 已在本候选关闭。本报告不批准旧候选。

范围：相对 HEAD `d04fdd1f7db870c531d143c153a9ed6e4e13d015` 的全部未提交业务差异及新增未跟踪业务文件，涵盖 backend 的契约、配置、Skill 数据/迁移/登记/检查/执行/测试，frontend 的管理页面、API、类型、校验器、mock、测试，infra 配置和本轮文档。依据 Product-Spec.md:475–483、Design-Brief.md:23、DEV-PLAN.md:3–12。未重新验收此前已提交的全部历史产品功能。

已使用 code-review skill。开始及结束只读 review-status 返回的 currentId 均与上述 candidate 相同；审查期间未发现代码快照变化。报告 Markdown 不改变代码快照。由主 Agent 使用 review-approve 登记本候选两阶段 PASS；reviewer 未登记批准、未写 clean、未提交或部署。

以下路径以 `hengxin-smart-image/` 为基准；Spec、Brief、计划及 output 路径相对仓库根。

## Stage 1 · Spec Compliance

### 完整实现

| 需求 | 结论、代码位置与验证证据 |
|---|---|
| Spec:475 取消新 ZIP 上传 | 匹配。backend/app/modules/skills/router.py:37 返回 410；frontend/src/views/hengxin/admin/skills.vue:29、:35–41 只提供标识、类型、版本、说明。backend/tests/test_local_skills.py:29 实际 HTTP 验证 410。 |
| Spec:475 保留历史 ZIP 数据及执行 | 匹配。backend/migrations/versions/0012_local_skills.py:11 默认历史来源 zip，不改 checksum；backend/app/modules/skills/package_validator.py:83 仍计算原 ZIP 字节摘要；backend/app/execution/materials.py:77 保留读对象/解包分支，router.py:70 保留历史安装。独立复跑 test_skills.py 通过。 |
| Spec:477 固定根、标识/语义版本定位、禁止任意路径 | 匹配。backend/app/core/config.py:26、app/modules/skills/local_tree.py:35–46；app/contracts/management.py:158 与 app/core/semver.py:5–16；前端 utils/skill-version.ts:2–9 与页面:79。HTTP 拒绝路径和非法 SemVer，接受 build 元数据；文件树也使用同一后端输入校验。 |
| Spec:477 说明、可先登记、初始不可用 | 匹配。backend/app/modules/skills/local_service.py:20–38 不读取服务器文件，保存每版本 description，pending/空 hash/空对象地址；service.py:105 返回版本说明，历史 null 回退。test_local_skills.py:145、:158 验证三个版本各自说明及历史回退，:29 验证无对象和不可提前启用。 |
| Spec:478 发布树所有权与执行用户不可写 | 匹配。backend/app/modules/skills/local_tree.py:20–25 检查 owner 和实际写权限，:43–47 包含全部祖先，:60 检查每成员。backend/tests/test_local_skills_linux.py:46–49 真正降权 nobody，:92 覆盖可写与 Worker 所有文件；Linux 9 项的执行结果见交接验证记录。 |
| Spec:478 拒绝链接/越界/特殊/超限 | 匹配。local_tree.py:36 的安全标识和版本限制、:44–46 祖先检查、:58–69 类型/硬链接/大小限制、:71–79 O_NOFOLLOW/inode/变化检查。test_local_skill_tree.py:32 覆盖超限和元数据，test_local_skills_linux.py:92 覆盖链接、FIFO、权限。 |
| Spec:478 完整树独立 hash、不可变约定 | 匹配。local_tree.py:28–32 对排序路径与内容摘要计算树 hash，:62 包含空目录，:85 拒绝旧 hash 漂移。test_local_skill_tree.py:19 验证目录和脚本影响 hash。docs/LOCAL-SKILL-RELEASES.md:31 明确 root 管理员仍须遵守不可变发布约定。 |
| Spec:479 真实 Worker 异步检查 | 匹配。local_service.py:41–54 在事务内写 Job/Outbox；backend/app/worker/tasks.py:62 分发，skill_check.py:28–60 claim/heartbeat/租约与 current_job_id 围栏；worker/outbox.py:27–30 支持过期检查重投。test_local_skills.py:65 覆盖重复与失效 claim，test_local_skills_concurrency.py:18 的真 PG 并发测试验证只产生一个作业。 |
| Spec:479 元数据、读取、依赖与实际隔离访问 | 匹配。local_tree.py:87–89 校验元数据；backend/app/execution/local_skill_probe.py:17–38 在 sandbox 内核对完整文件树、可读性、可执行依赖和 Python 顶层模块。测试 test_local_skills_linux.py:59、:114 分别检查成功及依赖缺失。 |
| Spec:479 检查不执行 Skill 代码、不生图 | 匹配。local_skill_probe.py:51–57 复用执行挂载后将最终命令替换为固定 `/usr/bin/python3 -I -c PROBE`；PROBE 仅读取、which、顶层 find_spec，未执行声明程序。Linux fixture 的 poison.py 没有被执行，检查不调用 Codex 生图。 |
| Spec:479 已验证未启用、显式启用、重检撤下 | 匹配。skill_check.py:55 只产生 verified/invalid，router.py:75–87 显式启停，local_service.py:52 先转 checking；页面:74 的标签和:85–88 确认文案对应实际状态。test_local_skills.py:65 证实 verified 不进入可用列表且重检不会恢复 available。 |
| Spec:479 固定 hash 不被重检覆盖 | 匹配。skill_check.py:16–24 前后双校验、:53–58 拒绝替换既有 hash。test_local_skills.py:65 注入不同内容摘要，断言 invalid 且旧 hash 保留。 |
| Spec:480 分组版本、默认、审计、权限 | 匹配。skills.vue:5–28 沿用分组/展开/SkillDefaults；router.py:20 所有维护接口依赖 manage_system；local_service.py:14、:33、:53、:68 与 router.py:84 写审计。service.py:94–109 计算历史模板、任务和默认引用。test_local_skills.py:29 对三种非超管角色返回 403。 |
| Spec:480 有引用/检查在途不得移除、不删服务器目录 | 匹配。local_service.py:58–74 锁版本、检查状态/引用/默认/当前作业、处理 FK 竞态，仅删 DB 登记；skills.vue:16、:90–95 禁用并确认“不删除文件”。test_local_skill_execution.py:19、test_local_skills.py:136 与前端 local-skills.test.ts:45 验证引用保护。 |
| Spec:480 明确错误、加载、空态 | 匹配。skills.vue:4–5、:41、:80–95 提供加载/错误/空文案/请求防重；AdminPreview.vue:3 明确模拟。独立查看 duplicate、empty、available 截图，错误提示和危险操作可辨。 |
| Spec:481 每轮固定版本、只读挂载、不复制解包 | 匹配。materials.py:63–75 读取 task.skill_version_id、核对快照并返回 local_skill；workspace.py:84–85 仅 ro-bind 对应版本到 /work/skill。test_local_skill_execution.py:19 验证无本地复制、冻结 ID/hash；Linux test:66 实际写入失败 EROFS、相邻版本不可见。 |
| Spec:481 缺失/内容变更/依赖失败明确失败、不回退 | 匹配。skill_check.py:15–25 校验抛错；materials.py:69–73 转为 SkillDeploymentError；diagnostics.py:14 与 codex_runner.py:197 提供固定失败说明。实现没有切换版本分支。 |
| Spec:482 模板/任务冻结，默认切换不改历史 | 匹配。backend/app/modules/templates/service.py:118 固定 skill_version_id；tasks/service.py:50–52 固定 ID/version/hash，:81 后续轮次仍加载原 Task；tasks/snapshots.py:57 只允许 available 接收新任务。材料层不要求历史版本仍 available，test_local_skill_execution.py:27 明确测试 disabled 旧绑定仍送校验。 |
| Spec:482 原任务隔离保持 | 匹配。workspace.py:19–47 仍以 task/round 建独立 Home/work/control；:82–85 只添加当前版本只读挂载，不开放发布根或用户全局 Skill。Linux 挂载测试验证邻居隐藏。 |
| Spec:483 专项覆盖与效果验收边界 | 匹配。本轮新增树校验、真实 HTTP、迁移、并发、执行材料、Linux bwrap、前端契约及 SemVer 测试。docs/LOCAL-SKILL-VALIDATION.md:3、:21–23 明确本机/模拟/生产/生图边界；不把未运行的模型效果计入已验收。 |

### 初审问题关闭

- M1 关闭：models.py:29、local_service.py:29、service.py:106、迁移 0012:16–17 和 HTTP test_local_skills.py:145–166 共同证明版本说明持久化、空串保持、历史 ZIP 回退。独立后端复跑已包含这些用例。
- M2 关闭：core/semver.py:5–16、contracts/management.py:165、local_tree.py:36 统一后端规则；前端 utils/skill-version.ts:2–9 由页面与 mock 共用。test_local_skill_tree.py:45–69 还验证 build 路径、manifest 匹配和旧 ZIP 校验兼容。独立前后端测试覆盖原四个错误边界。
- M3 关闭：frontend/src/api/hengxin/mock-management-skills.ts:40 判重包含 name/mode/version，与 backend/app/modules/skills/models.py:13、:22 的唯一键一致；frontend/tests/skill-version.test.ts:27 实测跨类型可登记、同类型冲突。

部分实现：无。未实现：无（限本轮需求范围）。Spec 漂移：未发现新增无对应需求的页面、API、表或组件；新增登记/检查/移除、字段、迁移和配置均对应 Spec:475–483。未新增后台终端或依赖安装功能。

## Stage 2 · Code Quality

- 结构与类型：变更及新增 Python/TS/Vue 文件扫描未超过 300 行；新增业务代码未引入 TypeScript any。local_service.py:20、local_tree.py:35、skill_check.py:28、local_skill_probe.py:43 分别负责状态、文件树、租约作业、隔离探针。DTO 与 API 契约已贯通；前端类型检查 exit 0。
- 错误处理：local_service.py:35、:72 转换唯一键/FK 冲突为 409；skill_check.py:42–45 将预期错误与未预料错误分别处理；probe.py:58–64 限制超时和错误输出。路径读取不会静默回退到其它版本。
- 安全扫描：差异新增行及新增业务文件扫描 eval、innerHTML、dangerouslySetInnerHTML、shell=True、sk-ant/sk-proj、VITE 密钥变量，无命中。查询采用 SQLAlchemy 参数比较（local_service.py:22、skill_check.py:47）；探针 subprocess 使用 argv、close_fds 与 30 秒超时（local_skill_probe.py:55–57）。新增绝对路径仅为部署配置与隔离挂载路径，未发现硬编码凭证。
- 信任边界：local_tree.py:20–25 防 Worker 写入/改权限，:71–79 抵御打开时文件替换，skill_check.py:24 检查探测期间漂移；不能阻止 root 最后一次校验后修改发布树。docs/LOCAL-SKILL-RELEASES.md:31 已明确管理员不可变发布责任，未宣称只读挂载等于宿主不可变快照。
- 测试真实性：test_local_skill_tree.py:12 mock 权限，仅证明 hash/元数据；权限与挂载依据 test_local_skills_linux.py:46–49 真降权和真实 bwrap。test_local_skill_execution.py:28 mock validate_local，因此只证明材料层冻结版本传递，不是完整真实 CLI 返工。真 PG 并发/迁移测试的前提、随机隔离 schema 和断言已阅读；本 reviewer 未再次执行这些外部专项，执行结果来自交接记录。
- 视觉实际对比：使用 view_image 打开 `output/playwright/local-skills-initial.png` 与 `local-skills-neighbor-settings.png`，两页 1280×720，内容左缘约 x=259、卡片顶边约 y=369，标题、白卡圆角、蓝按钮、浅灰背景、提示条及导航层级一致；对应 skills.vue:3–28 与 settings.vue:1 起。另查看 duplicate/available/empty 的真实渲染截图，登记表单沿用 520px ElDialog（skills.vue:29）、ElForm 与 ElAlert，移除红色动作与检查蓝色动作分离。截图包含页面滚动位置，只作为桌面渲染证据，不宣称所有长页面内容同时在一个视口中。
- 截图版本边界：initial 截图提示条仍为旧“安装”措辞，其余较晚截图与当前 AdminPreview.vue:3 已为“部署检查”；当前语义已从源码复核。说明/SemVer/mock 修复不改布局。本 reviewer 未重启 Vite 或宣称重新跑过浏览器完整流程；交接中的交互已由主 Agent 执行。

### LOW 建议（不阻塞）

L1：前端 mock 对“检查中再次检查”返回 409（frontend/src/api/hengxin/mock-management-skills.ts:47），真实后端幂等返回原记录（backend/app/modules/skills/local_service.py:45–46）。frontend/tests/local-skills.test.ts:54 当前断言 mock 409，不能用它证明后端重复请求语义。页面 skills.vue:15 已禁用在途按钮，真实 API 的并发/幂等保护有后端测试，不影响本轮用户流程；后续建议统一 mock 为幂等行为并改断言。

## 独立验证原始输出

后端，工作目录 `hengxin-smart-image/backend`，`CODEX_VERSION=0.153.4`：

命令：`uv run pytest tests/test_local_skills.py tests/test_local_skill_tree.py tests/test_local_skill_execution.py tests/test_skills.py -q`

```text
.......................................                                  [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
39 passed, 2 warnings in 3.55s
```

后端编译命令：`uv run python -m compileall -q app migrations tests`。正确 backend 工作目录的原始 stdout/stderr 为空，exit 0。首次误在仓库根运行只输出 `Can't list 'app'`、`Can't list 'migrations'`、`Can't list 'tests'`，该次不计为编译证据；已纠正目录并重跑。

前端，工作目录 `hengxin-smart-image/frontend`，命令：`node node_modules/tsx/dist/cli.mjs --test tests/local-skills.test.ts tests/skill-version.test.ts tests/management.test.ts`。原始汇总：

```text
ℹ tests 14
ℹ suites 0
ℹ pass 14
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 370.635
```

前端编译类型命令：`node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`。原始 stdout/stderr 为空，进程 exit 0。

交接验证证据（并非本 reviewer 重跑）：docs/LOCAL-SKILL-VALIDATION.md:9–17 记录后端全量 658 passed / 104 条件 skipped、说明修复 30 passed、SemVer 修复 56 passed、Linux 真实 bwrap/nobody 9 passed、前端修复后 110 passed、类型 exit 0、Vite 构建成功。未将 skipped 当作通过；全量结果与局部后续修复回归按时间分别记录。

## 交付边界

本报告只批准本轮本机代码与所述验证范围。未部署 VPS，未验证 VPS 账户/内核/依赖，未调用付费生图，也不把材料层测试当作真实模型返工效果验收。移动端现有侧栏遮挡按 DEV-PLAN.md:12 明确不在本轮桌面管理页验收范围。生产升级和真实效果验收仍须按 docs/LOCAL-SKILL-RELEASES.md:21–39 执行。
