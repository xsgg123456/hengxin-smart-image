# 多会话发布准备独立审查 · 2026-10-24

- candidateId：`9c15d3a3a59618fc5811f0d3281df00299754ade6404f061e4551b0d74ec5aa5`。
- 范围：本次正式多会话 backend/API/迁移/执行与清理，frontend/controller/页面及测试，0.2.50 打包与发布入口及继承执行链。用户预存 AGENTS.md 修改未改动；批准预览作为 UI 基准。未修改实现、未提交、未部署，未对生产做写测试。
- 依据：全文读取 `docs/STUDIO-SESSIONS-IMPLEMENTATION-20261024.md:1`，并核对 `Product-Spec.md:1334`、`Design-Brief.md:218`、`DEV-PLAN.md:1552` 与前次报告。
- **Stage 1：FAIL，MEDIUM 1 项；无新增 HIGH。Stage 2：未完成，不登记 PASS。** 前次旧 GET 清新草稿 HIGH 已关闭，但本轮发现稳定读取不能清除失效归档。以下质量观察不替代 Stage 2 完整通过。
- 起始与报告写入前 `review-status` 均返回同一 currentId；结论不覆盖此后修复。主 Agent 应修复后重新固定快照并复核，不得向 `.needs-review` 写 clean。

## MEDIUM S1-01：稳定刷新仍保留已经删除的归档，完成入口和引导失真

合同第 2 条要求“任务完成需所有会话均无在途且有有效归档”，第 7 条保留既有任务归档细节。`frontend/src/views/overseas/studio/studio-session-api.ts:13` 对同一 taskVersion 只接受非空 archiveId。即使没有任何在途写入、GET 明确返回 `archiveId:null`，`:27` 仍把旧缓存覆盖到返回值。

这是生产可达路径：`backend/app/overseas/archives/deletion.py:55` 接受归档删除但不增加 task.version；`backend/app/overseas/studio/queries.py:74` 对删除中的归档返回不可用，`:119` 返回 null。前端 `use-studio-sessions.ts:126`、`OverseasStudio.vue:13` 却继续开放“完成任务”和“查看本任务成品”，`:27` 的“暂无可用归档”提示也不会出现。手工刷新不能恢复。后端 `service.py:170` 仍拒绝完成，所以本项为 MEDIUM，不是越权或非法完成 HIGH。

独立使用真实 Vue controller、项目 fixture，通过 stdin 运行以下脚本（未写测试源码）：

```ts
import { fixture, flush } from './tests/studio-sessions-fixture.ts';
(async()=>{
  const f=fixture(),v=f.mount();await flush();const s=v.state;
  s.selected.value=['p'];await s.archive('SKU');await flush();
  console.log('BEFORE',JSON.stringify({archive:s.data.value?.archiveId,canComplete:s.canComplete.value}));
  const original=f.api.get;
  f.api.get=async(...args)=>({...await original(...args),archiveId:null});
  await s.refresh();await flush();
  console.log('AFTER_SERVER_ARCHIVE_NULL',JSON.stringify({archive:s.data.value?.archiveId,canComplete:s.canComplete.value}));
  v.close();
})();
```

原始输出：

```text
BEFORE {"archive":"archive","canComplete":true}
AFTER_SERVER_ARCHIVE_NULL {"archive":"archive","canComplete":true}
```

修复标准：稳定完整读取应接受同版本的 null；过时或并行 mutation 回执不能复活已失效归档。补真实 controller 回归，断言当前与已加载其他会话 archiveId 均清空、canComplete 为 false，同时仍允许之后重新归档。

## Stage 1 全合同核对

下表 B=`hengxin-smart-image/backend/`，F=`hengxin-smart-image/frontend/`。代码位置均相对上述根目录。

| 条目 | 结论与证据 |
|---|---|
| 1. 10 上限、历史超限、命名、删除确认与名额释放 | 完整实现。B`app/overseas/studio/conversations.py:12` 在 task 行锁内计数；`:23` 校验归属/版本/幂等；B`schemas.py:67` 限制名称；F`OverseasStudio.vue:126` 确认范围。B`tests/test_studio_sessions.py:21` 验证历史 11 个保留，B`tests/test_overseas_studio_postgres.py:52` 四线程争第 10 个名额仅一次成功。 |
| 2. 同会话互斥、跨会话实际并行、目标停止、后台新结果 | 执行部分完整。B`service.py:36`/`:57` 按会话互斥，B`execution/claims.py:81` 目标会话检查及五槽约束。真实 PG 测试 `test_overseas_studio_postgres.py:74` 两个不同会话同时认领为 running；F`studio-session-state.ts:6` 未读标记。CUA 独立停止会话 2 后会话 1 仍排队，总数从 2 变 1。有效归档完成入口受 S1-01 影响。 |
| 3. CLI/sessionId、持久目录、消息/草稿/Skill/附件/图片隔离 | 完整实现。B`execution.py:22` 只载本会话上下文，`:44` 用 conversation.id 建工作目录且 copy_auth=False，`:61` 保留 workspace-write；B`queries.py:34`/`:50` 拒绝私有跨会话输入，B`files.py:72` 上传命名空间，B`material_list.py:10` 只列公共和本会话。独立运行 B`test_studio_sessions.py:39`/`:68` 及 `test_overseas_studio_conversations.py:16` 通过。 |
| 4. 身份/任务本地选择、草稿/滚动、迟到响应、不跨会话重放 | 完整实现，关闭前次 HIGH。F`studio-session-api.ts:29` 写开始/结束推进 epoch，`:42` 重读旧响应/迟到错误，mutation 仅更新目标行；F`use-studio.ts:46`/`:76` 赋值前归一，F`use-studio-sessions.ts:41` 同步共享状态。F`studio-session-order.test.ts:8` 冻结旧 snapshot 再新建，检查 localStorage 原文仍在；`:25` A 回执挂起时 B 确实已发送；`:58`/`:78`/`:91` 删除、解冻、404、microtask 交叉通过。F`studio-session-state.ts:34` key 含身份/任务，F`StudioTurns.vue:35` 按会话保存/恢复滚动。CUA 切换 A/B，B 草稿恢复、A 无该草稿。 |
| 5. 当前会话归档、任务/来源/SKU、删除后独立可查下载 | 核心归档与保留完整；稳定可用性刷新部分实现（S1-01）。B`service.py:120` 强制来源一致及 SKU，B`archives/snapshot.py:58` 独立归档并固化来源，B`archives/models.py:24` 来源无会话 FK。F`OverseasStudio.vue:43` 确认说明，F`OverseasArchiveDetail.vue:26` 来源展示。B`test_studio_sessions.py:83` 真删除会话后归档 GET/download 仍成功。 |
| 6. 全任务完成只读、切换查看、取消/确认解冻、历史保持、可再完成 | 完成/解冻状态机完整。B`service.py:159` 全任务在途/删除/有效归档门禁，`:177` 解冻仅状态与版本；F`use-studio-sessions.ts:66` 传播任务态；F`OverseasStudio.vue:15` 顶部提示和 `:45` 确认。controller 完成/解冻回归通过且无自动发送。当前有效归档前端门禁需 S1-01 修复。 |
| 7. 批准 UI、真实组件、原功能、收起/窄屏 | 完整接线。F`OverseasStudio.vue:21`/`:28`/`:42` 使用正式列表、附件、标注等组件；`:20` 重试提示有真实处理。CUA 打开正式 3032、批准预览 3031、邻居任务列表，白底卡片/蓝色 Element 操作/边框密度一致；1920 视口正式和预览会话列均 200px、Skill 均 265px。F`studio-sessions.css:10`/`:11` 窄屏浮层/堆叠。390 实测证据沿用验证文档，未冒称 reviewer 独立重测该视口。 |
| DTO、GET/transcript、Send、新建/PATCH/DELETE、upload、错误与兼容 | 完整接线。B`router.py:17`/`:32`/`:39`/`:44`/`:50`/`:56`/`:92`，F`api/overseas/studio.ts:65`；显式 conversationId、版本、幂等键与严格 DTO。B`queries.py:148` 404/410/删除门禁；未指定会话维持旧默认选择。 |
| 旧 pending 升级、原 body/key、来源不可证明时保留 | 完整实现。F`studio-pending.ts:18` 仅迁移可证明来源，冲突保留原槽；F`use-studio.ts:106`/`:117` 检查归属并原样重发，旧发送用 query hint。B`service.py:57` 保持哈希并核对回执来源。独立 12 个前端旧 pending 测试与 B`test_studio_sessions.py:209`/`:238`/`:259` 通过。 |
| 删除清理/失败可重试/占名额/保护共享材料和归档/不重调度 | 完整实现。B`conversation_cleanup.py:22` 验证退出和节点，`:34` 精确对象与目录边界，`:117` 先固化归档及 manifest 后擦除；B`execution/outbox.py:24` 维护接入，B`execution/claims.py:81` 删除后拒绝认领。B`test_studio_sessions.py:118`、`:155`、`:183` 覆盖失败重试、历史消费者引用及链接保护。Windows 链接用例跳过，Linux专项原始日志为 25 PASS、0 skip。 |
| 0020→0021 历史兼容、原字段/归档保留 | 完整实现。B`migrations/overseas/versions/0021_studio_sessions.py:17` 增量字段、按历史排序命名、精确来源回填；历史上传不猜归属。B`tests/test_studio_sessions_migration.py:13` 真实 PG 填充 12 会话、逐字段比较及重复 upgrade，已有用户重命名不回填覆盖。主 Agent Linux/PG 证据已读取，未在本 Windows 审查重新运行全 PG 集。 |
| 发布、权限/Skill/国内/broker 保留、排空备份恢复、实际安装包测试 | 发布实现完整，生产交付尚未执行。`scripts/release/overseas-studio-sessions-deploy.py:161` 固定生产基线，`:194` 保留完整 Compose 与成员绑定，`:207` 对实际 native 安装目录 network=none 测试，`:233` 迁移前验证备份及逐原字段指纹，`:257` 校验权限/argv。继承 `overseas-upload-deploy.py:183` 先关流、排空、备份、迁移、切换、验证再开流；`overseas-studio-ux-deploy.py:122` 实际隔离恢复并核对摘要后才写 COMPLETE。失败仅关流留证，不自动回灌旧生产库。29 项发布专项独立通过。 |

## 质量、安全与范围观察（Stage 2 未形成 PASS）

1. 前次 305 行问题已关闭：B`tests/test_studio_sessions.py:19` 引入原样拆出的 `tests/studio_sessions_helpers.py:1`；主文件 280 行。发布包及安装 REQUIRED 已包含 helper，见 `scripts/release/package-studio-sessions.py:17`、`overseas-studio-sessions-deploy.py:40`。独立后端测试没有导入/收集失败。
2. 本轮读取 review-status 的 54 个受控变更文件，逐文件统计均不超过 300 行；扫描 eval、危险 HTML 渲染、显式 any、密钥前缀和 VITE 密钥变量均无命中。B`router.py:15` 保持 browser_request，权限/归属检查见 B`queries.py:19` 和 `service.py:20`；未发现本次新增明确安全问题。SQL 动态标识符由 `overseas-studio-sessions-data.py:16` 正则白名单约束。
3. 新增冻结 snapshot 测试比旧测试真实：snapshot 在故障等待前取得；B 并行发送发生在 A resolve 前，不是仅测试按钮启用。仍漏测“相同 taskVersion 下非空 archiveId 变 null”，实际全前端 383 PASS 不能掩盖 S1-01。
4. 未发现业务范围漂移：会话删除表、归档来源、旧请求 query hint 与发布验证均有合同依据。正式 `OverseasStudio.vue:1` 未接入模拟状态；`package-studio-sessions.py:27` 禁止 preview HTML 进入生产包。
5. 依赖风险不作零漏洞声明：`docs/STUDIO-SESSIONS-VALIDATION-20261024.md:28` 记录既有 critical=0/high=37/moderate=37/low=3，本次无依赖版本变更。未在本次审核中把这些既有告警归为新漏洞。

## 原始验证输出

reviewer 独立运行：

```text
pnpm exec tsx --test tests/studio-session-order.test.ts tests/studio-legacy-pending.test.ts tests/studio-sessions.test.ts
ℹ tests 28
ℹ suites 0
ℹ pass 28
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 646.3017
```

```text
pnpm test
> hengxin-smart-image-frontend@0.2.50 test D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> tsx --test tests/*.test.ts
ℹ tests 383
ℹ suites 0
ℹ pass 383
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8749.4654
```

```text
pnpm typecheck
> hengxin-smart-image-frontend@0.2.50 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

退出码 0，无类型错误。pnpm 的原有 package.json 配置位置警告仍在，未因该警告判失败。

```text
.venv/Scripts/python.exe -m pytest -q tests/test_studio_sessions.py tests/test_overseas_studio_conversations.py tests/test_studio_material_list.py
25 passed, 1 skipped, 2 warnings in 9.98s

hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest -q scripts/release/test_studio_sessions_release.py
.............................                                            [100%]
29 passed in 1.09s
```

Windows 跳过为创建 symlink 权限；警告为既有 Starlette/httpx、AnyIO 弃用。

已直接读取主 Agent 正式构建原始日志 `output/studio-sessions-release/frontend-build-production.log`，没有重复生成构建产物：

```text
dist/assets/index-C17gb_ma.js                                                             426.31 kB │ gzip: 140.95 kB
dist/assets/index-B-dflYw7.js                                                             562.49 kB │ gzip: 191.32 kB
dist/assets/prototype-DB3-X4kN.js                                                         662.37 kB │ gzip: 226.30 kB
dist/assets/echarts-OiDiNeVO.js                                                           756.30 kB │ gzip: 244.76 kB
dist/assets/index.vue_vue_type_style_index_0_lang-BUTevX3V.js                             814.14 kB │ gzip: 275.63 kB
dist/assets/index-CF8c24np.js                                                             963.71 kB │ gzip: 307.80 kB
✓ built in 32.58s
```

直接读取的 Linux 证据（主 Agent 执行，不冒称 reviewer 重跑）：

```text
# output/studio-sessions-release/linux-full-final.log
2485 passed, 121 skipped, 6 warnings in 738.65s (0:12:18)
# output/studio-sessions-release/linux-sessions-final.log
25 passed, 2 warnings in 24.14s
```

Linux 全量发生于 HTTP helper 原样抽取之前；后端生产逻辑未变，拆分后的 Windows 专项已独立复验。121 个条件跳过不能表述为相应能力通过。浏览器使用独立回环测试 API，没有模型/生产数据连接；此次实际操作仅切换、测试草稿和停止测试会话 2，未发起模型生成。
