# 海外工作台多会话正式实现审查 · 2026-10-24

- candidateId：`4e9ce6f222b41ce4283de4361c35e764fcf2d1472142b38bc77f6c73bdff5ca3`
- 分支：`codex/studio-multi-sessions`。
- 范围：本次 backend Studio 会话模型/API/私有输入/执行互斥与并行/异步删除/归档来源、海外 0021 迁移、frontend 正式 API/controller/UI、测试、0.2.50 版本和打包/发布入口，以及 Spec/Brief/计划/实施合同同步。既有用户 AGENTS.md 修改不作为本次功能改动。独立 preview 属于已审设计基准，不是生产实现。
- 原文依据：`Product-Spec.md:1334`、`Design-Brief.md:218`、`DEV-PLAN.md:1552`、`docs/STUDIO-SESSIONS-IMPLEMENTATION-20261024.md:5`。
- **Stage 1：FAIL。HIGH 1 项，MEDIUM 1 项。Stage 2：未执行正式审查，因 Stage 1 HIGH 停止。不得 review-approve。**
- 审查中主 Agent 修改了 `studio-sessions.css` 和发布脚本空白布局。结束时 `review-status` 当前编号为 `8e855a49c8120e33cbc1abc6f76d16378ce1596ba2a61af6aacdeb728500263d`，不等于送审编号；下述行号对应读取时版本。修复后必须重新 prepare 并复核，不能把本报告套用新版本。

## 阻断问题

### HIGH S1-01：旧版未知发送恢复到另一会话，并清掉另一会话草稿

需求原文：实施合同第 4 条“后台请求迟到不能改写新会话、误清草稿或误投发送。未知发送状态按原会话/幂等键核实，不能跨会话重放”。

旧版 `use-studio.ts` 在任务级 `hx-studio-pending:{actor}:{task}` 保存未知请求，带 `draftConversationId=A`，发送 body 没有 `conversationId`。此数据是升级时可真实存在的输入，不是伪造的不可达状态。

正式实现 `frontend/src/views/overseas/studio/use-studio.ts:17` 读取该任务级 pending，`:77` 在默认 GET 返回 B 时将其迁入 B 的 storageKey；`:143` 重试未补充/核实原会话归属，`:114` 将原 body 直接发送。`backend/app/overseas/studio/service.py:57` 对未受理的旧请求使用 `current_conversation()`，因此会发到最新 B。成功后的 `use-studio.ts:120` 调用 `draft.clear(A)`，而 `studio-composer-draft.ts:82` 先清当前 engine 字段并 save，再删 A 存储，因此 B 草稿也被清空。

独立复现使用真实 Vue controller 和项目 fixture；只替换 API 默认会话为 B，预置符合旧版格式的 sessionStorage 和 B 草稿。未修改生产代码、未调用模型：

```text
BEFORE {"selected":"b","text":"B自己的未发送草稿","pending":{"key":"old-unknown-key","kind":"send","body":{"text":"A原待确认请求","skillId":null,"attachmentIds":[],"referencePictureIds":[]},"draftConversationId":"a"}}
RETRY_WIRE {"body":{"text":"A原待确认请求","skillId":null,"attachmentIds":[],"referencePictureIds":[]},"key":"old-unknown-key","implicitDestination":"b"}
AFTER {"selected":"b","text":""}
```

复现命令（frontend 目录，通过 `pnpm exec tsx` stdin 执行）：

```ts
import { fixture, flush, session, local } from './tests/studio-sessions-fixture.ts';
import { composerDraftKey } from './src/views/overseas/studio/studio-composer-draft.ts';
(async () => {
  const f = fixture();
  f.api.get = async (_t, _s, id) => f.snapshot(id || 'b');
  session.set('hx-studio-pending:designer:t', JSON.stringify({
    key: 'old-unknown-key', kind: 'send', draftConversationId: 'a',
    body: { text: 'A原待确认请求', skillId: null, attachmentIds: [], referencePictureIds: [] }
  }));
  local.set(composerDraftKey('designer', 't', 'b'), JSON.stringify({
    version: 1, text: 'B自己的未发送草稿', skill: '', attachments: [], references: [], revisions: []
  }));
  f.api.send = async (_t, body, key) => {
    console.log('RETRY_WIRE', JSON.stringify({ body, key, implicitDestination: body.conversationId || 'b' }));
    return f.snapshot('b');
  };
  const v = f.mount(); await flush();
  console.log('BEFORE', v.state.activeId.value, v.state.text.value, v.state.pending.value);
  await v.state.retry();
  console.log('AFTER', v.state.activeId.value, v.state.text.value, local.get(composerDraftKey('designer', 't', 'b')));
  v.close();
})();
```

修复验收必须包含：旧请求已受理/未受理、原会话已删除/无法确定、B 已有草稿、原 key/hash 兼容。仅向旧 body 加 conversationId 会改变已受理请求指纹，不能以 409 清除 pending 后重新发送作为解决方法。原会话不能证明时应停止重放并提供可核实结果。

### MEDIUM S1-02：正式 Skill 选择器与批准预览宽度不一致

`frontend/src/views/overseas/studio/studio-sessions.css:8` 的 `max-width:70%` 在正式 `OverseasStudio.vue:36` 中作用于 `.studio-input-tools` 包装层；预览 `preview-studio-sessions/App.vue:27` 的 ElSelect 是工具栏直接子元素，宽度基准不同。

独立新建 Chrome tabs 打开正式本地隔离任务和批准预览，均 1920px viewport；截图观察并通过 DOM `getBoundingClientRect()` 得到：

```text
正式 { height: 32, viewport: 1920, width: 185.5 }
预览 { height: 32, viewport: 1920, width: 265 }
```

主 Agent 已修改 CSS，尚待新快照桌面和窄屏复核。其它已观察的会话列、归档区域、Shell、按钮尺寸/色彩与批准预览一致；此结论不代表忽略上述尺寸差异。

## Stage 1 逐项核对

以下是实现定位及验证范围，不把未完成的 Linux 验证写成 PASS。路径前缀 B=`hengxin-smart-image/backend/`，F=`hengxin-smart-image/frontend/`。

| 合同条目 | 完整性结论与证据 |
|---|---|
| 1. 最多 10，会话新建/命名/删除，保留超限历史 | 已实现计数检查：B`app/overseas/studio/conversations.py:12` 在任务写锁内计数，`:23` 校验版本/权限/幂等；B`studio/schemas.py:67` 约束 1–30 字。B`tests/test_studio_sessions.py:45` 覆盖 10 上限、11 条历史和重命名；真实 PG 并发用例 B`tests/test_overseas_studio_postgres.py:52` 已检查代码，执行结果待取。删除确认 F`OverseasStudio.vue:126`，正在执行禁止删除 B`conversations.py:59`。 |
| 2. 同会话互斥、跨会话并行、只停目标、不抢选中、完成前全任务无在途 | B`studio/service.py:36`/`:57` 只检查目标会话，B`execution/claims.py:81` 认领时再次检查会话，仍保留 5 槽；`:99` 停止精确 turn.job_id。B`tests/test_studio_sessions.py:64` 独立运行通过，证明两个会话同时 running、同会话拒绝和停止隔离。F`use-studio-sessions.ts:36`/`:93`/`:102` 更新汇总和未读，不自动切换。B`service.py:148` 完成校验所有任务 job、清理状态和有效归档。 |
| 3. 独立 CLI、目录、消息、草稿、Skill、私有附件/图片 | B`studio/execution.py:22` 按 conversation 查询历史，`:44` 按 conversation.id 创建 workspace 且 copy_auth=False；B`queries.py:34`/`:50` 强制附件/图片归属，历史共享图片有精确消费者例外。B`files.py:84` 上传命名空间包含会话，B`material_list.py:10` 限公共或当前上传。B`tests/test_studio_sessions.py:93` 私有输入和跨会话引用拒绝独立运行通过；B`tests/test_overseas_studio_conversations.py:16` 原会话 CLI home 与新会话分离独立运行通过。 |
| 4. 身份/任务本地选择，草稿/滚动，迟到与未知请求 | **部分实现，HIGH S1-01 未满足旧版未知请求。** 新格式 engine 独立，F`use-studio-sessions.ts:70`、`studio-session-state.ts:20`；选择存储 key 包含 actor/task，`:141` 保存滚动，`StudioTurns.vue:35` 恢复 scrollTop。F`tests/studio-sessions.test.ts:24`/`:39` 覆盖新格式迟到发送、上传及重试，但没有覆盖升级前任务级 pending，不能据此宣称完全隔离。 |
| 5. 当前会话归档、任务/SKU/来源确认，删会话保留归档 | B`service.py:109` 强制同会话图片和任务 SKU；B`archives/snapshot.py:65` 固化来源、独立复制存储；B`archives/models.py:24` 来源无会话外键依赖。F`OverseasStudio.vue:43` 显示任务/来源/SKU，F`OverseasArchiveDetail.vue:26` 来源筛选与展示。B`tests/test_studio_sessions.py:107` 删除源会话后归档仍可下载独立运行通过。 |
| 6. 全任务只读、可切换；确认解冻，历史/草稿/成品保持，不自动执行 | B`service.py:148`/`:166` 只切任务状态/版本，不创建 job；写操作入口要求 studio 状态。F`OverseasStudio.vue:15`/`:45` 有只读条与确认/取消，`use-studio-sessions.ts:52` 将任务状态传播所有 engine；F`tests/studio-sessions.test.ts:66` 覆盖草稿不丢和无自动发送。主 Agent 提供真实组件+隔离 API 完成/取消/确认流程及 `output/studio-sessions-release/completed.png`、`reopen-confirm.png`；未以预览模拟按钮充当正式验收。 |
| 7. 批准 UI、原功能保留、收起及窄屏 | **部分实现，MEDIUM S1-02 尺寸差异。** F`OverseasStudio.vue:21`/`:28`/`:42` 保留真实材料、附件、标注组件，`:24` 当前会话归档；`StudioSessionList.vue:1` 收起/数量/状态；`studio-sessions.css:10` 窄屏浮层。独立打开正式/预览两页已比实际渲染；主 Agent 的 390px 无横溢出证据不能替代本次宽度修复后的重测。 |
| GET/Transcript/Send/管理接口兼容 | B`studio/router.py:19`/`:40`/`:45`/`:51`/`:57`，F`api/overseas/studio.ts:65`，有 conversationId/query、版本、幂等及 DTO 状态校验。旧普通请求默认最新会话存在；旧未知发送重放兼容缺口见 S1-01。 |
| 异步删除、失败占额、重试、共享历史、原生文件路径限制 | B`conversation_cleanup.py:117` 两次事务间持久归档及 manifest，`:22` 校验进程退出/worker归属，`:34` 保护共享材料/图片/档案并列出专属资源，`:89` 清理记录；复用 B`tasks/cleanup_files.py:99` 链接与根目录边界检查。B`execution/outbox.py:24` 原生维护调度。独立运行 `test_failed_delete_retains_slot_and_retries_without_false_success`、`test_legacy_cross_session_picture_reference_survives_source_deletion` 通过；Windows symlink 用例跳过，须 Linux 补证。 |
| 0020→0021 保全与归档来源回填 | B`migrations/overseas/versions/0021_studio_sessions.py:17` 增量字段/表；历史上传保持 NULL 共享，不猜来源；精确联表回填 archive 来源；不删除超限会话；禁 downgrade。B`tests/test_studio_sessions_migration.py:13` 建立 12 会话历史、逐字段比对和再次调用 upgrade；代码已审，真实 PG 结果待主 Agent 取回。 |
| 打包、生产基线、迁移、权限/代理/worker 保持 | `scripts/release/package-studio-sessions.py:12` 固定 0.2.50/国内0032/海外0021并拒绝 preview HTML；`overseas-studio-sessions-deploy.py` 原送审 `:170` preflight、`:247` migrate、`:281` deploy 绑定安装测试回执，权限完整保留、worker argv/5槽和broker元数据检查；`overseas-studio-sessions-data.py:25`/`:63` 原字段逐表哈希及新字段精确校验。追溯继承链的实际调用钩子，没有把旧版本定义误当实际执行分支。29 项发布回归独立运行通过；真实打包/部署尚未执行，不能写成发布完成。 |

未发现本次新增业务页面/API超出实施合同的明确 scope creep。来源筛选、删除状态表和发布校验属于合同要求的来源可查、异步删除与生产保全。正式生产路径没有预览演示按钮接入证据；打包测试检查了 preview HTML 排除。

## 验证原始输出与限制

审查者独立运行：

```text
backend/.venv/Scripts/python.exe -m pytest -q tests/test_studio_sessions.py tests/test_overseas_studio_conversations.py tests/test_studio_material_list.py
.......s..............                                                   [100%]
21 passed, 1 skipped, 2 warnings in 8.85s
```

跳过是 Windows 创建 symlink 受限；警告为既有 Starlette/httpx 与 AnyIO API 弃用，不是通过了 Linux 文件安全用例。

```text
hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest -q scripts/release/test_studio_sessions_release.py
.............................                                            [100%]
29 passed in 0.99s
```

首次直接用系统 Python 运行发布测试返回 `No module named pytest`，随后使用项目 venv 得到以上结果；不是忽略测试失败。

正式编译由主 Agent 执行；审查者读取 `output/studio-sessions-release/frontend-build.log`，原始关键输出：

```text
> hengxin-smart-image-frontend@0.2.50 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
🚀 API_URL = /api/v1
🚀 VERSION = 0.2.50
vite v7.1.7 building for production...
transforming...
✓ 4672 modules transformed.
rendering chunks...
computing gzip size...
✓ built in 33.40s
```

日志同时有 pnpm 忽略 package.json 的 `pnpm.overrides`/`pnpm.onlyBuiltDependencies` 配置警告。此为原候选构建，CSS 修改后须重构建。

主 Agent 交接记录前端 365/365、backend Windows 139 pass/5 skip、相关发布 160 pass/48 subtests；这些不是审查者独立复跑的数字。Linux/真实 PG 全量仍在诊断环境 errors，**本报告不将其记为通过**。主 Agent 表示生产只读 preflight/schema 检查已通过，生产发布尚未发生。

## Stage 2 与后续审查边界

因 HIGH S1-01 停在 Stage 1，安全、质量、测试真实性和邻居视觉的完整 Stage 2 尚无 PASS 结论。审查过程中已提前提示新发布脚本原为 307 行，主 Agent 随后压缩空白至 288 行；这是已声明的快照漂移，后续 reviewer 应核对仅布局变更及实际职责。现有依赖审计高危告警由主 Agent 提供，不能因为未新增依赖就声称无漏洞。

修复后应从 Stage 1 重新开始：重点跑旧 pending 升级回归，再核对新 candidate、桌面 265px 和窄屏渲染、Linux PG/文件真实验证及正式构建；Stage 1 通过后再完成 Stage 2。主 Agent 不得使用本 FAIL 报告登记两阶段 PASS。
