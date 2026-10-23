# 多会话正式实现独立复审 · 2026-10-24

- candidateId：`b918fa4c483b1c963f58cf05eab59768d90c9aba30f98d7d19175669c9222f16`。
- 范围：正式 backend 会话模型/API/执行隔离/删除/归档/0021 迁移，frontend API/controller/正式页面和测试，0.2.50 打包与发布脚本及其继承执行链。用户已有 AGENTS.md 修改不属于功能提交。未改实现、未提交、未部署。
- 依据：`Product-Spec.md:1334`、`Design-Brief.md:218`、`DEV-PLAN.md:1552`、`docs/STUDIO-SESSIONS-IMPLEMENTATION-20261024.md:5`，以及批准的 `frontend/preview-studio-sessions`。
- **Stage 1：FAIL，HIGH 1 项。Stage 2：未完成；发现 HIGH 后停止，已有质量观察不构成 Stage 2 PASS。不得登记 review-approve。**
- 开始及最终复现后的 review-status 均返回上述 currentId；本报告结论不覆盖随后修复的快照。主 Agent 已收到阻断复现。

## HIGH S1-01：旧会话读取响应把新会话当成删除，销毁新草稿并抢走选择

合同第 4 条要求：“后台请求迟到不能改写新会话、误清草稿或误投发送”。当前实现不满足。

`hengxin-smart-image/frontend/src/views/overseas/studio/use-studio-sessions.ts:36` 的 `accept` 只用 taskVersion 排除旧响应。`:41` 用返回列表替换 summaries；`:48` 将列表缺失的其他 engine 当成已删除，`:53` 停止并移除 engine，`:54` 物理删除对应 localStorage 草稿；`:75` 自动选择列表首项。

然而 `hengxin-smart-image/backend/app/overseas/studio/service.py:44` 的 finish 只更新 task.updated_at，`:101` 新建会话不增加 task.version；`conversations.py:50` 的重命名及 `:59` 删除同样不增加任务版本。因此新建前的 A GET 和新建后的结果可以拥有相同 taskVersion。每 engine 自己的 operation/AbortController 不能阻止另一个 engine 的旧结果覆盖全局会话列表。

独立复现使用真实 Vue controller 和现有项目 fixture，没有改生产代码、没有调用模型。明确在服务端请求完成时截取旧 snapshot，然后延迟网络回包：

```text
BEFORE {"id":"n2","text":"新会话必须保留的草稿","sessions":["a","b","n2"],"saved":"{\"version\":1,\"text\":\"新会话必须保留的草稿\",\"skill\":\"\",\"attachments\":[],\"references\":[],\"revisions\":[]}"}
AFTER {"id":"a","text":"","sessions":["a","b"]}
```

AFTER 的 saved 字段缺失是 `local.get(key)` 已返回 undefined，草稿已被删除；不是仅 UI 暂时显示错误。

复现命令：frontend 目录通过 `pnpm exec tsx` stdin 运行以下内容。

```ts
import { fixture, flush, deferred, local } from './tests/studio-sessions-fixture.ts';
import type { Studio } from './src/api/overseas/studio.ts';
import { composerDraftKey } from './src/views/overseas/studio/studio-composer-draft.ts';
(async () => {
  const f = fixture(), v = f.mount(); await flush(); const s = v.state;
  const old = f.snapshot('a'), late = deferred<Studio>(), original = f.api.get;
  let delay = true;
  f.api.get = async (...args) => {
    if (args[2] === 'a' && delay) { delay = false; return late.promise; }
    return original(...args);
  };
  const oldRead = s.refresh(); await flush();
  await s.newConversation(); s.text.value = '新会话必须保留的草稿'; await flush();
  const id = s.activeId.value, key = composerDraftKey('designer', 't', id);
  console.log('BEFORE', JSON.stringify({id, text:s.text.value, sessions:s.sessions.value.map(x=>x.id), saved:local.get(key)}));
  late.resolve(old); await oldRead; await flush();
  console.log('AFTER', JSON.stringify({id:s.activeId.value, text:s.text.value, sessions:s.sessions.value.map(x=>x.id), saved:local.get(key)}));
  v.close();
})();
```

测试盲区：`frontend/tests/studio-sessions.test.ts:91` 的迟到读取测试在 resolve 时才调用 `f.snapshot('a')`，返回的是最新会话列表，没有覆盖“服务端已读取旧快照、网络迟到”的生产可达路径。应补充创建、删除、并行发送状态及已写草稿的旧快照回包测试。修复应使跨 engine 汇总具有明确时序/单调版本依据，不能仅凭一次可能陈旧的列表缺失就销毁用户草稿；只加现有 per-engine operation 不够。

## Stage 1 全合同逐项核对

下表 B 为 `hengxin-smart-image/backend/`，F 为 `hengxin-smart-image/frontend/`。通过项限定为本次代码和所列验证，不等于生产发布已完成。

| 合同项目 | 结论与证据 |
|---|---|
| 1. 每任务 10 会话、历史超限保留、命名/删除确认、清理后释放名额 | 完整实现。B`app/overseas/studio/conversations.py:12` 在任务锁内计数，`:23` 版本/归属/幂等校验；B`studio/schemas.py:67` 名称限制；F`OverseasStudio.vue:126` 删除确认。B`tests/test_studio_sessions.py:45` 及真实 PG `test_overseas_studio_postgres.py:52` 证明历史不删、并发仅一项抢到第 10 名额。 |
| 2. 同会话互斥、跨会话真实并行、准确排队、停止目标、后台新结果 | 后端完整实现：B`studio/service.py:36`/`:57` 目标会话互斥，B`execution/claims.py:81` 认领校验会话及五槽；`:110` cancel 定位 turn.job_id。PG `tests/test_overseas_studio_postgres.py:74` 同会话两次发送仅一次成功、跨会话两 job 同时 running。F`studio-session-state.ts:6` 未读状态；但全局迟到汇总存在 S1-01，不能把前端状态稳定性判完全通过。 |
| 3. 独立 CLI/sessionId、工作目录/输入输出/消息、私有附件/图片、显式公共素材 | 完整实现。B`studio/execution.py:22` 只取原会话历史，`:44` conversation.id workspace 且 copy_auth=False；B`queries.py:34`/`:50` 拒绝跨会话附件/图片，精确保留旧消费者历史引用；B`files.py:72` 上传绑定会话命名空间，B`material_list.py:10` 仅公共与本会话。B`tests/test_overseas_studio_conversations.py:16` 真实持久 home 隔离；B`test_studio_sessions.py:64`/`:93` 私有输入/引用拒绝通过。既有凭据代理与 sandbox 参数未放宽。 |
| 4. 身份/任务本地选择、草稿/滚动、迟到请求与旧 pending | **部分实现，S1-01 HIGH。** F`studio-session-state.ts:34` key 含身份/任务；F`studio-composer-draft.ts:14` 按会话保存，`StudioTurns.vue:35` 恢复滚动。旧 global pending 缺陷已修：F`studio-pending.ts:18` 仅按可证明原归属迁移，`use-studio.ts:106`/`:117` 保持原 body/key、query hint；B`service.py:57` 保持哈希并校验回执归属。独立新增旧 pending 12 项全部通过，原 HIGH 关闭；新 HIGH 是另一条跨 engine GET 路径。 |
| 5. 仅当前会话归档、任务/会话/SKU 说明、删除后独立归档可读/下载 | 完整实现。B`service.py:120` 强制图片同来源/任务 SKU，B`archives/snapshot.py:58` 固化来源并独立存储；B`archives/models.py:24` 来源没有会话外键依赖。F`OverseasStudio.vue:43` 确认说明，F`OverseasArchiveDetail.vue:26` 来源筛选/展示。B`test_studio_sessions.py:107` 删除原会话后原归档下载仍 200。 |
| 6. 全任务只读、查看切换、确认/取消解冻、保留上下文和归档、无自动执行 | 完整实现。B`service.py:159` 检查全任务在途/删除/有效归档，`:177` 解冻仅任务状态及版本；F`use-studio-sessions.ts:57` 传播只读状态，F`OverseasStudio.vue:15`/`:45` 完成条及确认弹窗。F`studio-sessions.test.ts:66` 两会话草稿保持、零自动 send 独立通过；主 Agent 真实组件完成/取消/确认截图另见验证文档。 |
| 7. 批准 UI、原材料/标注/交付/Skill/权限/重试保留、收起与窄屏 | 已核实。F`OverseasStudio.vue:21`/`:28`/`:42` 复用真实组件，`StudioSessionList.vue:1` 列表和收起；`studio-sessions.css:8` Skill 包装层 265px。审查者独立打开正式 3032、批准预览 3031 与邻居工作流任务列表：1920 视口下两页 Skill 均 265×32、会话列均 200px，关闭前次 MEDIUM。窄屏 CSS `:10`/`:11` 浮层和堆叠；已查看主 Agent 的真实 mobile.png，无横向裁切。审查工具本次 viewport.set 未实际改变 1920，故不冒称独立复测 390；390/scrollWidth382/Skill207.1875 来自主 Agent 实测。 |
| DTO/GET/Transcript/Send/new/PATCH/DELETE/upload、错误、选择兼容 | 完整接线。B`studio/router.py:19`/`:32`/`:45`/`:51`/`:57`/`:81`，F`api/overseas/studio.ts:65` 显式 conversationId，版本/幂等键，严格 DTO；B`queries.py:148` 410/404/409 与归属。旧客户端缺字段保持默认，旧未确认发送用 query hint 且不改 body hash。 |
| 异步清理、失败占名额、可重试、路径保护、不重调度已删会话 | 完整实现。B`conversation_cleanup.py:22` 进程退出/节点检查，`:34` 精确对象所有权，`:117` 先提交独立归档/manifest 再擦除；B`tasks/cleanup_files.py:88` 根目录/链接/硬链接限制；`execution/outbox.py:24` 调度维护，`claims.py:81` 删除状态拒绝认领。独立 Windows 故障/重试/历史消费者用例通过；Linux 专项 25/25 包含 Windows 跳过的链接检查。 |
| 0020→0021、旧字段/历史/文件/归档来源保持 | 完整实现。B`migrations/overseas/versions/0021_studio_sessions.py:17` 增量字段、稳定历史命名、仅精确来源回填、共享旧上传保持 NULL；`:68` 禁 downgrade。B`tests/test_studio_sessions_migration.py:13` 实际 12 会话填充 PG、逐原字段比较和重复 upgrade；主 Agent PG 迁移证据已记录，不以 SQLite 代替。 |
| 发布基线、权限/Skill/国内/代理/五槽保持、备份隔离恢复、实际安装包测试 | 代码已核查，运行交付尚待执行。`scripts/release/package-studio-sessions.py:10` 固定版本/迁移并复用干净受审包门禁；`overseas-studio-sessions-deploy.py:159` preflight、`:208` 实际安装目录网络隔离测试、`:235` migrate、`:260` 安装验证、`:269` 测试回执；继承 `overseas-upload-deploy.py:183` 的关闭接纳→排空→隔离恢复备份→迁移→切换→校验→开放，异常不恢复旧库。29 个发布专项独立通过。生产只读 preflight 是主 Agent 的证据，本 reviewer 未对生产执行任何发布。 |

## Stage 2 已观察项（未形成完整 PASS）

1. **MEDIUM S2-01**：B`tests/test_studio_sessions.py:301` 至末尾使文件共 305 行，超过 `.agents/skills/code-review/SKILL.md` 的 300 行标准。应合理拆分测试/公共夹具；拆分后检查实际安装测试仍收集旧 pending 兼容用例。已提前告知主 Agent。
2. 测试真实性盲区见 S1-01。现有 22 项 controller 回归通过并不能证明“旧服务端快照迟到”安全。
3. 已扫描本次 49 个非预览代码文件：危险渲染/eval、密钥前缀、显式 any、字面密码各 0 命中；发布 SQL 动态表名使用 `overseas-studio-sessions-data.py:16` 严格标识符，业务变更用 SQLAlchemy。固定 /opt 路径是部署基线，非用户输入拼接。未发现本次引入的明确注入/凭据泄露，但不作全仓库无漏洞声明。
4. 本次没有新增业务 scope creep：来源筛选、会话删除表、query 兼容提示及发布验证均有合同依据。正式页面没有模拟生成按钮接入，打包入口排除 preview HTML。
5. 独立打开并视觉比较正式工作台、批准预览、邻居工作流任务列表；Art Shell、白色卡片、蓝色 Element 主操作、边框及紧凑密度一致。桌面数值见上表。
6. 依赖审计仍有既有 high=37/moderate=37/low=3，critical=0，引用 `docs/STUDIO-SESSIONS-VALIDATION-20261024.md:28` 及原始 npm-audit.json；不把“本次依赖未变”说成没有漏洞。当前不对这些既有告警作本次新增漏洞判断。

## 原始验证输出与边界

审查者独立运行：

```text
pnpm exec tsx --test tests/studio-legacy-pending.test.ts tests/studio-sessions.test.ts
ℹ tests 22
ℹ suites 0
ℹ pass 22
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 453.3101
```

```text
.venv/Scripts/python.exe -m pytest -q tests/test_studio_sessions.py tests/test_overseas_studio_conversations.py tests/test_studio_material_list.py
25 passed, 1 skipped, 2 warnings in 10.22s
```

Windows 跳过为 symlink 创建权限；警告为既有 Starlette/httpx、AnyIO 弃用。已读取 Linux 专项 `output/studio-sessions-release/linux-sessions-final.log` 原文：

```text
.........................                                                [100%]
25 passed, 2 warnings in 24.14s
```

```text
hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest -q scripts/release/test_studio_sessions_release.py
.............................                                            [100%]
29 passed in 1.11s
```

审查者独立类型检查，进程退出 0：

```text
> hengxin-smart-image-frontend@0.2.50 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

读取主 Agent 最终构建原日志 `output/studio-sessions-release/frontend-build-final.log`（本 reviewer 未重复 build）：

```text
> hengxin-smart-image-frontend@0.2.50 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
🚀 API_URL = /api/v1
🚀 VERSION = 0.2.50
vite v7.1.7 building for production...
transforming...
✓ 4673 modules transformed.
rendering chunks...
computing gzip size...
✓ built in 46.87s
```

pnpm 均有原有警告：package.json 的 `pnpm.overrides`、`pnpm.onlyBuiltDependencies` 被当前 pnpm 忽略。读取 `frontend-tests-final.log`：377 tests/377 pass/0 fail，9229.7403ms。新增独立复现暴露的是原测试未覆盖的缺陷，不是上述测试日志造假。

Linux 首轮失败不可隐去：2446 pass/121 skip/5 fail/29 fixture error。主 Agent 修复测试断言/迁移夹具并补齐 infra；supervisor 已通过相同源码只改 Docker --init 的 A/B（读取 init 日志为 8 passed in 42.21s），确认 PID1 孤儿保护环境差异。最终全量 `studio-sessions-test-2f48398d0a` 在报告编写时仍运行；不得写成全量通过。实际打包、安装、备份恢复和生产验收也尚未完成。

后续应先修 S1-01，新增真实旧快照回包回归，处理 S2-01，重新 prepare。重新从 Stage 1 开始，通过后完成 Stage 2；本报告不得用于批准新 candidate。
