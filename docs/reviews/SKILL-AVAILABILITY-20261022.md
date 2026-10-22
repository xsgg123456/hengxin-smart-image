# 海外 Skill 账号专属开关独立审查

- 日期：2026-10-22；审查者：独立 code-reviewer。
- candidateId：`a2fcd69bdff5dde51098f5d3b31294bb07a27668d15826309f3f94d44367eae5`。
- 结论：**Stage 1 PASS；Stage 2 PASS**。未发现本轮范围内 HIGH / MEDIUM 缺陷。
- 审查开始及报告前多次 `harness.py review-status` 均返回上述 currentId，未发生代码快照变化。审查者未修改产品代码、未提交、未登记批准、未写 `.needs-review`。
- 本报告仅审查本地实现；不表示生产环境已绑定账号、完成迁移或上线。

## 范围与基准

源文档：`Product-Spec.md:1286` 的六条增补、`Design-Brief.md:211`、`DEV-PLAN.md:1526`；实施证据 `docs/SKILL-AVAILABILITY-20261022.md`。

下文 `B/` 表示 `hengxin-smart-image/backend/`，`F/` 表示 `hengxin-smart-image/frontend/`，`I/` 表示 `hengxin-smart-image/infra/`。

短路径补充：`B/management/`、`B/studio/`、`B/execution/` 分别指 `B/app/overseas/management/`、`B/app/overseas/studio/`、`B/app/overseas/execution/`；`B/config.py`、`B/db.py` 指 `B/app/overseas/` 下对应文件；`F/admin/`、`F/studio/` 分别指 `F/src/views/overseas/admin/`、`F/src/views/overseas/studio/`。同一单元格或项目内省略目录的文件沿用此前同模块路径。

审查范围：B/app/overseas 的 config、db、management/{models,router,settings,skills}、studio/queries，迁移 0020、相关新增和适配测试；F/src/api/overseas/management、OverseasPortal、admin/{OverseasLiveSkills,OverseasSkillCatalog,OverseasLiveSettings}、studio/{use-studio,StudioSkillSelect,OverseasStudio,studio-composer-draft}及相关测试；I/.env.overseas.example、compose.overseas.yaml。以 review-status 相对上一批准快照的 43 个文件清单固定范围。

上一批准快照为 `9887aaaa1ac26ab00bc44c0fdd75f542cff7308cb05f63016c6167ab78aa7fff`，报告 `docs/reviews/STUDIO-DRAFT-MATERIALS-FINAL-20261022.md`。附件草稿、素材批量移除属于既有已审核变更，本轮检查 Skill 接线的兼容性，不将它们列为新增需求漂移。

## Stage 1：Spec Compliance — PASS

| 需求条目 | 结论与代码证据 | 行为证据 |
|---|---|---|
| 管理目录保留全部安装项，展示状态及开关；工作台仅显示开启项 | 完整实现。B/app/overseas/management/skills.py:22 管理投影不丢关闭项，:29 单独过滤；B/app/overseas/studio/queries.py:104 接入过滤；F/src/views/overseas/admin/OverseasSkillCatalog.vue:11 状态/按钮。 | B/tests/test_overseas_skill_availability.py:135 用真实 HTTP 同时断言管理两项、工作台一项/空列表。独立重跑通过；实际浏览器管理页面显示两开一关。 |
| 初始仅开启两个指定名称；以后新安装默认关闭 | 完整实现。B/migrations/overseas/versions/0020_skill_availability.py:22 只插入两个指定名称；B/app/overseas/management/skills.py:24 无记录即关闭，:30 无记录不进入工作台。 | B/tests/test_overseas_skill_availability_migration.py:9 在真实 PostgreSQL 完整迁移后精确断言两行；B/tests/test_overseas_skill_availability.py:30 新安装条目关闭。审查者独立迁移测试 1 passed。 |
| 唯一成员 ID + 原 skills.manage 权限共同约束，不按姓名/超管身份推定；空绑定禁写 | 完整实现。B/app/overseas/config.py:28 UUID 配置/空字符串转 None；management/skills.py:12 精确比较 actor.id，:42 重新锁定成员并核验 skills.manage；management/router.py:37 使用原权限依赖及浏览器写保护。 | B/tests/test_overseas_skill_availability.py:64 覆盖未绑定、同名其他超管、本人无原权限；所有拒绝均无状态及审计写入。owner_configuration.py:7 覆盖海外变量、空值、国内同名变量不能回退和非法值。独立重跑通过。 |
| 其他管理员可查看但不能切换；通用设置不能改绑定 | 完整实现。management/skills.py:22 返回 canToggle；F/admin/OverseasSkillCatalog.vue:3、:11 只读说明及隐藏写按钮；B/management/schemas.py:69 白名单及 :37 extra=forbid。 | B/tests/test_overseas_skill_availability.py:120 拒绝两个拼法的 owner 字段且保持原值；F/tests/overseas-skill-availability.test.ts:36、:61 验证只读和权限变化。 |
| 状态按稳定名称持久化，刷新、重启、目录更新不重置 | 完整实现。B/management/models.py:19 独立持久表且名称为主键；skills.py:17 每次读数据库并 populate_existing；0020:24 冲突不覆盖。无进程内启用缓存/目录同步重置逻辑。 | B/tests/test_overseas_skill_availability.py:30 新请求/Session及包更新后开关与版本保持；migration.py:9 人工关闭后重复 upgrade 两次仍关闭。重启持久性依据数据库存储和独立新连接验证，未声称重启生产服务。 |
| 切换具备版本冲突、真实操作者审计、失败不假成功 | 完整实现。B/management/skills.py:46 execution gate 串行化，:51 版本不符 409，:59 写 actor/before/after，:64 事务提交；F/admin/OverseasLiveSkills.vue:25 请求锁，:31 使用服务端完整结果，:40 冲突/未知结果读回，读回失败禁写。 | HTTP 严格参数、CSRF、404、409、无副作用断言见 B/tests/test_overseas_skill_availability.py:94、:105；真实 PG 并发一成功一冲突见 postgres.py:21，审查者独立重跑通过；F/tests/overseas-skill-availability.test.ts:17、:45、:61、:77 覆盖重复点击、冲突、网络丢响应及卸载回包。 |
| 关闭项不能通过旧页面、旧草稿或直接 API 新提交 | 完整实现。B/management/settings.py:25 冻结安装包后核查 enabled，:69 冻结与切换共用 gate；studio/service.py:66 在入队前调用。F/studio/use-studio.ts:27 禁发失效选择，StudioSkillSelect.vue:2、:8 提示及显式清空。 | B/tests/test_overseas_skill_availability.py:135 关闭项首次及新幂等键均 422、数据库仅原作业；postgres.py:47 缓存开启状态等待 gate 后刷新并拒绝。F/tests/studio-draft-materials.test.ts:130、:146 覆盖整页恢复与同会话目录变化。 |
| 提示失效选择，保留其余草稿；已提交幂等、历史及冻结作业不受影响 | 完整实现。F/studio/studio-composer-draft.ts:44、:75 保留失效 skill ID 及草稿，use-studio.ts:135 retry 沿用冻结 Pending；B/studio/service.py:54 已提交请求先 replay，冻结校验仅用于新提交；B/management/installed_catalog.py:139 与 execution/materials.py:22 从冻结 release 读包，不读取开关。 | B/tests/test_overseas_skill_availability.py:135 验证 replay 同轮次、冻结字节不变、关闭后原排队任务仍可完成；F/tests/studio-draft-materials.test.ts:146、:164 验证附件文本保留、清空/重开可发、未知提交继续核实原 key。独立 25 项前端测试含原批量移除兼容通过。 |
| 仅开关，不删安装包、不改内容、不扩展品牌匹配 | 完整实现。skills.py:41 只写状态与 Audit；installed_catalog 未改动，安装树及品牌规则没有新增写入口。 | 包升级持久测试和 frozen_package 字节断言通过；git diff/快照范围未见包删除、品牌逻辑或其它产品功能。 |
| 账号配置部署接线与本地范围 | 完整实现。I/compose.overseas.yaml:14 注入 OVERSEAS_SKILL_TOGGLE_OWNER_ID，I/.env.overseas.example:39 空值示例；B/config.py:28 读取；B/db.py:10 迁移版本更新。 | 配置测试独立通过；本次没有生产访问/变更。真实账号绑定由主 Agent 核实并保存在忽略目录，本报告不公开或重新读取其标识。 |
| UI/引导与设计一致、请求状态可信 | 完整实现。F/admin/OverseasSkillCatalog.vue:2 沿用 ElCard/ArtTable，:26 完整换行，:30 状态按钮间隔 8px；LiveSkills.vue:15 刷新真实读取，:45 明确冲突读回；F/studio/OverseasStudio.vue:26 提示实际禁止发送的原因。 | 审查者实际打开正式组件+隔离 API 目录，并打开既有系统配置预览作邻居对比；详细数值见 Stage 2。未发现不存在功能的引导。 |

部分实现：无。未实现：无。Spec 漂移：无；新增持久表、开关 API、配置字段均对应已批准条目。系统设置默认项过滤是关闭项禁止新提交的必要兼容（F/admin/OverseasLiveSettings.vue:40；测试 :87），不是额外管理功能。

## Stage 2：Code Quality — PASS

### 结构、类型与安全

- 责任分离通过：持久状态、安装目录、冻结接纳分别保留在 B/management/skills.py:12、installed_catalog.py:119、settings.py:69；前端读写状态与展示分别在 LiveSkills.vue:14、SkillCatalog.vue:19。此次相关产品文件均小于 300 行，最长 use-studio.ts 233 行，Portal 149 行，新增状态模块 65 行。
- 类型/错误处理通过：F/src/api/overseas/management.ts:13、:21 校验布尔状态、正整数版本及 canToggle；B/management/schemas.py:58 使用 strict bool/int；LiveSkills.vue:35 401 清空目录，:37 403 降级只读，:41 不明结果读回失败禁止再写。测试覆盖可达 HTTP/SFC 路径，没有用测试专用产品分支替代校验。
- 安全扫描通过：对本轮产品源码运行 `rg` 检查 eval、dangerouslySetInnerHTML、innerHTML、VITE KEY/SECRET/TOKEN、sk-ant-/sk-proj-、/Users/ 及显式 any，无命中。新增查询使用 ORM 参数绑定（skills.py:35）；写入口保留 browser_request 和后端权限验证（router.py:37、skills.py:42）。新增配置不包含硬编码真实成员 ID、令牌或密码（config.py:28、I/.env.overseas.example:39）。
- 并发真实性通过：B/tests/test_overseas_skill_availability_postgres.py:21 用两个真实 Session/线程及 Barrier；:47 显式缓存旧对象、另一事务持有 gate 并提交关闭，验证后续 freeze 得到 422。这不是 SQLite 并发替身。独立重跑两项全部通过。
- 兼容性通过：F/tests/studio-draft-materials.test.ts:50、:146、:164、:178 实际执行 useStudio 草稿恢复、失效选择、未知提交及批量操作；管理测试编译真实 SFC。浏览器 fixture 只替换 API，正式 Vue 仍来自产品源文件，见 F/tests/skill-availability-preview.ts:1。

### 实际视觉对比

审查者使用 Chrome 实际打开 `http://127.0.0.1:3037/#/overseas/admin/skills`，以及现有 `overseas-preview.html#/overseas/management/settings` 邻居页面。两个页面均完整渲染后截图观察并读取 computed style：

| 项目 | 新目录 | 既有系统配置基准 | 结论 |
|---|---:|---:|---|
| 卡片圆角 | 16px | 16px | 匹配 |
| 卡片背景 | rgb(255,255,255) | 同值 | 匹配 |
| 卡片内部计算 padding | 23px（含边框后外观 24px） | 23px | 匹配 |
| 标准按钮高度/字号 | 32px / 14px | 32px / 14px | 匹配 |
| 标准按钮文字颜色 | rgb(93,135,255) | 同值 | 匹配 |
| 1920px 宽视口 | scrollWidth=1920，越界按钮=[] | 既有同套壳 | 无横向溢出 |

代码证据：F/admin/OverseasSkillCatalog.vue:2、:11、:26，现有邻居 F/admin/OverseasSettings.vue:2。状态采用原 ElTag，动作紧凑纵排，完整名称/描述与刷新搜索均可读。

另独立查看已有 `output/skill-availability/readonly-mobile.png`（390×844）与 `stale-draft-desktop.png`：窄屏完整换行、只读无开关、工作台失效选择/保留草稿/禁用发送均可见。主 Agent 的初始两开状态以 `initial-two-enabled.png` 为准，其余截图为交互中间状态。审查者尝试 Chrome viewport override 后 DOM 仍报告 1920，故不把这次尝试计为独立窄屏测量；窄屏证据来自已查看截图和主 Agent 的真实组件验收记录，临时 override 已恢复。

### 验证原始输出

审查者独立执行（均退出 0）：

```text
.venv/Scripts/python.exe -m pytest tests/test_overseas_skill_availability.py tests/test_overseas_skill_owner_configuration.py -q
19 passed, 2 warnings in 11.07s

TEST_OVERSEAS_MEMBERS_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:55439/hx_skill_availability_test
.venv/Scripts/python.exe -m pytest tests/test_overseas_skill_availability_postgres.py -q
2 passed, 2 warnings in 2.35s

TEST_OVERSEAS_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:55439/hx_skill_availability_test
.venv/Scripts/python.exe -m pytest tests/test_overseas_skill_availability_migration.py -q
1 passed in 3.00s

node --import tsx --test tests/overseas-skill-availability.test.ts tests/studio-draft-materials.test.ts tests/overseas-management-api.test.ts
ℹ tests 25
ℹ suites 0
ℹ pass 25
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1181.2961
```

独立读取主 Agent 保存的全量前端/构建及 Linux 相关测试原始日志：

```text
# output/skill-availability/frontend-tests.log
ℹ tests 351
ℹ suites 0
ℹ pass 351
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8894.2977

# output/skill-availability/frontend-build.log
> hengxin-smart-image-frontend@0.2.46 build:overseas D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build --config vite.overseas.config.ts --mode demo
vite v7.1.7 building for demo...
transforming...
✓ 4683 modules transformed.
rendering chunks...
computing gzip size...
✓ built in 36.75s

# output/skill-availability/linux-focused.log
63 passed, 1 warning in 21.29s

# output/skill-availability/postgres.log
18 passed, 2 warnings in 25.79s
```

警告为现有 httpx/Starlette 弃用提示；构建日志另提示 pnpm 不再读取 package.json 中两个 pnpm 设置字段，未阻断类型检查与构建。本轮未修改依赖或锁文件，不以该提示声称升级/依赖审计通过。

全后端日志 `output/skill-availability/linux-full.log` 已读取，不能称全绿：

```text
FAILED tests/test_api_retry_gate_pg.py::test_oversized_retry_after_survives_postgres_json_and_admin_resume
E   sqlalchemy.exc.DataError: (psycopg.DataError) timestamp too large (after year 10K): '10000-01-01 07:59:59.999999+08'
1 failed, 2347 passed, 24 skipped, 9 warnings in 392.11s (0:06:32)
```

失败位于未改动的国内重试用例 `B/tests/test_api_retry_gate_pg.py:235`：数据库时区将 UTC 年 9999 上界转换到 +08 后超出 Python datetime 范围。主 Agent 从 `git archive HEAD` 提取 backend 到独立 `/tmp/hx-skill-availability-baseline`，原提交同条用例出现完全相同错误；审查者已独立读取 `head-timezone-baseline.log` 的原始异常及结果。仅将本次隔离测试数据库时区改为 UTC 后，当前代码完整 `test_api_retry_gate_pg.py` 六项通过，审查者已读取 `retry-gate-utc.log`：

```text
# HEAD，Asia/Shanghai，head-timezone-baseline.log
E   psycopg.DataError: timestamp too large (after year 10K): '10000-01-01 07:59:59.999999+08'
1 failed, 1 warning in 1.29s

# 当前候选，隔离测试数据库 UTC，retry-gate-utc.log
6 passed, 1 warning in 5.63s
```

因此该失败有基线复现，属于既有国内日期极值/环境时区边界，没有本轮 Skill 回归证据。没有为此改动产品源码、测试或生产数据库；不将原全量运行改写成全绿。本报告 PASS 针对上述 Skill 范围和明确已通过的验证，不覆盖该既有国内边界及生产时区承诺。24 项条件跳过也不记为通过。

## 交接

两阶段 PASS 只适用于本报告 candidateId。主 Agent 可按 `docs/HARNESS-REVIEW.md` 登记同一快照；若内容变化必须重新固定并复核。生产部署另行执行，不能据本报告宣称线上已生效。
