# 海外成品库整套删除独立审查

- candidateId：`6513382a599911591ec438e83a5f7c27e90c9ecac0d167793de136b108d2fa20`
- Stage 1：**FAIL（HIGH 1 项）**。
- Stage 2：**NOT RUN**。依 code-review skill，Stage 1 存在 HIGH 时停止。
- 范围：送审时全部本功能 tracked diff 与 untracked 实现、迁移、前后端测试及真实浏览器脚本；需求为 Product-Spec.md:1221–1228 与 docs/ARCHIVE-DELETE-IMPLEMENTATION-20261019.md。未审其它独立功能、未验收生产部署。
- 主 Agent 已收到问题并表示将修改代码、新建仅元数据确认接口。本报告只对应上述旧快照，不批准任何后续版本；修复后须重新 prepare 和独立复审。报告中的位置均指本次读到的旧版本。

## Stage 1 问题

### HIGH：归档图永久缺失或损坏时，页面无法进入删除确认

需求：Product-Spec.md:1223–1227 要求二次确认后删除整套内容，原任务已删除的历史归档也支持，并以最新快照确认。

实际链路：

1. `hengxin-smart-image/frontend/src/views/overseas/OverseasArchiveDelete.vue:44` 使用普通 `api.get` 取得确认信息；只有成功才在第 47 行打开弹窗，第 50 行失败仅显示错误。
2. `hengxin-smart-image/backend/app/overseas/archives/service.py:99` 的详情调用 `access(..., metadata_only=True)`，但第 89–94 行仅在已经有删除凭据时绕过 protect；首次删除依旧执行 protect。
3. `hengxin-smart-image/backend/app/overseas/archives/snapshot.py:44` 对每个已存在 Asset 执行 `read`；`hengxin-smart-image/backend/app/overseas/studio/files.py:79–89` 对不存在对象或长度/hash 不符统一返回 HTTP 503。

因此，一张归档图永久丢失/损坏即可阻断整套删除确认；反复点击/刷新无法改变结果。后端列表可以取得 token、清理器可以容忍已缺失字节，但正常用户无法通过页面调用 DELETE。尤其原 Task 已删时也不能依靠来源重建解决。此结论来自完整确定性代码路径，未声称已做额外运行时复现。

建议：提供只读取最新归档元数据和 token 的确认路径，独立校验超级管理员权限并与删除/追加锁保持一致；不读取或复制图片。补充真实缺失/损坏归档对象、源任务已删除、二次确认成功清理的回归。

## Stage 1 逐条对照

|需求|结论与证据|
|---|---|
|超级管理员专属、后端独立鉴权|完整实现。`backend/app/overseas/archives/deletion.py:55,73` 均校验 task.delete；`backend/app/overseas/permissions.py:24` 仅 super_admin 获得该能力。前端 Portal 传入权限、Page:41 控制入口；专项测试覆盖四种非管理员 DELETE/状态 403。以下缩略路径均相对 hengxin-smart-image。|
|二次确认、品名/数量/不可恢复及源任务保留提示|正常对象完整实现；损坏/缺失对象部分实现，见 HIGH。`frontend/src/views/overseas/OverseasArchiveDelete.vue:5–9,40–50`；查看了 output/playwright/archive-delete/confirm-desktop.png 和 confirm-mobile.png，桌面及 390px 文案可读，取消/确认按钮完整可操作。|
|归档图片、资产、历史及成品真正清理|完整实现。`backend/app/overseas/archives/cleanup.py:31,76` 枚举并验证对象删除后再在第 58 行清理业务行；回执第 103 行才置 deleted。tests/test_overseas_archive_deletion.py:24 的两种源任务生命周期与 SQL 失败/无效 remove 测试覆盖真实状态断言。|
|其他任务/成品/共享对象保护|完整实现。`cleanup.py:20–55` 严格 UUID 命名空间、来源 task 校验、五类源对象及其它 ArchiveAsset 共享引用拒绝；对应 unsafe/source_reference/other_archive 与另一成品存活测试。|
|持久化、失败重试、刷新/重启恢复、最小回执|完整实现。`archives/models.py:51` 仅 ID、状态、安全错误及时间；`deletion.py:55` 提交后返回，`cleanup.py:104–120` 持久失败/扫描待清理，`execution/outbox.py:21` 接入维护循环；前端 Delete.vue:35,66 恢复轮询。浏览器结果记录真实 MinIO 停机及恢复重试。|
|禁止追加、保护复制及下载，并发任务清理不复制回来|完整实现。`archives/snapshot.py:28`、`studio/service.py:113,140`、`archives/service.py:89` 检查回执；`tasks/cleanup.py:40,58` 两事务均阻止跨阶段重建；PG 专项覆盖追加优先/删除优先、任务 detach 及两事务间请求。|
|最新快照、冲突重确认、重复提交幂等|内容 token 与锁完整实现：`deletion.py:18,28,55` 将归档/Asset/Event 全字段纳入 hash，并按 Task→Archive→Receipt 顺序上锁；同数量内容变化覆盖 409，旧回执幂等。确认入口另受上述 HIGH 阻断。|
|删除后列表、总数、分页及关闭详情/预览|完整实现。`frontend/src/views/overseas/OverseasArchivePage.vue:42–55`；frontend/tests/overseas-archive-ui.test.ts:95 验证页码请求 1,2,2,1 和总数归零。|
|来源任务保留、解除归档、后续重新归档、旧 key 不复活|完整实现。`cleanup.py:58–71` 清除相关 Picture.sku、重开 studio/generating 并使旧归档/完成请求 hash 失效；专项 tests 的 studio、completed、legacy 重归档断言覆盖旧 key 409、新 key 成功。|
|取消、权限、重复、冲突、失败、源任务两态及并发验收|大部分已有专项和真实环境证据。缺失/损坏对象的首次确认链路缺少验收，已成为 HIGH；全后端测试尚未完成且已出现 F，不可宣称全套通过。|

## Spec 漂移

本次新增 DELETE/状态查询、receipt 表及维护接入均对应 Spec 的真实删除、恢复与幂等要求，未发现新增产品范围。证据：archives/router.py:43、models.py:51、migrations/overseas/versions/0019_archive_deletion.py:11、execution/outbox.py:21。

## 已查阅验证证据（不等于 Stage 2 通过）

主 Agent 提供日志，本 reviewer 读取原始结果；未另行重复执行全套测试。

`output/archive-delete-pg-tests.log`：

```text
Command: python -m pytest tests/test_overseas_archive_deletion_postgres.py tests/test_overseas_archive_deletion_migration.py -q
......                                                                   [100%]
6 passed, 2 warnings in 9.00s
```

`output/archive-delete-frontend-tests.log`：

```text
ℹ tests 300
ℹ suites 0
ℹ pass 300
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8975.4202
```

`output/archive-delete-frontend-build.log` 原始结尾：

```text
dist/assets/echarts-OiDiNeVO.js                                                           756.30 kB │ gzip: 244.76 kB
dist/assets/index.vue_vue_type_style_index_0_lang-C02CcRx_.js                             814.14 kB │ gzip: 275.63 kB
dist/assets/index-D1encsut.js                                                             963.71 kB │ gzip: 307.80 kB
✓ built in 34.28s
```

`output/playwright/archive-delete/result.json`：四组 checks，errors 为 []，modelCalls 为 0；覆盖权限、取消、刷新 pending、真实 MinIO 故障恢复/隔离。已查看桌面及窄屏确认截图作为 Stage 1 UI 证据。Stage 2 邻居页面实际渲染对比与安全/质量完整审查未执行。

`output/archive-delete-backend-tests.log` 审查时尚未结束，包含：

```text
..........................F...........................sssssss........... [ 54%]
.............................................ss...sss................... [ 57%]
```

该 F 原因当时尚无汇总，不能归因于本改动，也不能忽略并登记全套通过。

## 交接

主 Agent 修复 HIGH 后重新固定 candidateId，复审从 Stage 1 开始。当前快照不得 review-approve；没有写入 clean，没有修改产品代码，没有提交。
