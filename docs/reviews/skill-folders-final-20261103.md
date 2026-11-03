# 海外 Skill 文件夹管理第二轮独立审查

## 快照、范围与结论

- 主 Agent 交付 candidateId：`0a12fa904ad5a886a8919aaa4e3a8bb63a07ba53a190a3fb09ad5b3eafc90cae`。2026-11-03 本 reviewer 执行 `review-status`，`currentId` 与其一致，`approved: false`。
- 范围：当前全部 changed/untracked 实现、测试、依赖锁文件、发布工具及本轮需求文档；源合同 `docs/SKILL-FOLDERS-IMPLEMENTATION-20261103.md:7`，补充 `Product-Spec.md:1401`、`DEV-PLAN.md:1621`、`Design-Brief.md:236`。下文 `backend/` 和 `frontend/` 路径相对 `hengxin-smart-image/`。
- 使用 `.agents/skills/code-review/SKILL.md`。独立 reviewer 未修复代码、未提交、未操作生产，仅检查代码、现有验证日志、执行隔离最小复现并写报告。
- **Stage 1：FAIL；Stage 2：未执行。不得用本报告登记 PASS。**

## Stage 1：HIGH，合法包仍被历史引用正则错误拒绝

合同第 1、2 项要求完整文件夹及合法资源完整保存，并仅拒绝明确缺失的包内引用。新的 CommonMark 校验 `backend/app/overseas/management/skill_transfer_store.py:19` 本身能识别真实链接及现存目录，但 `:172` 首先调用 `installed_tree.tree()`，该函数在 `backend/app/overseas/management/installed_tree.py:100` 继续调用旧 `check_references()`。旧逻辑 `:134` 用正则匹配整个文档，`:155` 只在文件字典中查找目标，因此：

1. 根 SKILL.md 正文 `[Assets](assets/)`，包内确实有空 `assets/` 目录，仍报资源不存在。
2. Markdown 围栏代码示例包含 `[example](assets/not-present.png)`，并非正文实际资源链接，仍报缺失。

这不是纯函数边缘差异：所有新上传都必经 `TransferStore.validate → tree → check_references`；后续安装复制 `backend/app/overseas/management/skill_publication.py:49`、安装复核 `:65` 及目录读取 `backend/app/overseas/management/installed_catalog.py:57` 也调用同一 `tree`。仅在 store 中补新校验不能消除误拒绝。

独立 reviewer 使用后端现有 `.venv/Scripts/python.exe`，创建两个隔离临时目录，分别写合法 YAML name/description 的 SKILL.md 和真实 assets 空目录；先运行新 `validate_references`（两例均通过），再执行实际 `tree`。原始输出：

```text
existing-directory ValueError Skill reference is missing: assets/
fenced-example ValueError Skill reference is missing: assets/not-present.png
```

修复须覆盖上传校验、安装副本校验、正式 catalog 和 frozen reader 的一致行为，并验证历史安装兼容。若变更共享 reader，需同步真实 API/native 发布范围、基线与安装态测试。增加完整 upload→validate→install→catalog→freeze 测试，不能只测新辅助函数。

## Stage 1 逐项覆盖

“有实现”指已读实现和测试断言，未把主 Agent 尚未完成的浏览器/生产验收记为通过。

| 合同条目 | 结果及证据 |
| --- | --- |
| 单个目录拖入、递归至全部 readEntries 批次 | 有实现：`frontend/src/views/overseas/admin/skill-folder-read.ts:14`、`:41`；`frontend/tests/skill-folders.test.ts:16` 断言超过 100 项完整读取。 |
| 文件/空目录、相对路径、大小、SHA-256、目录树 | 有实现：`frontend/src/views/overseas/admin/skill-folder-read.ts:31`、`:37`、`:63`；`backend/tests/test_overseas_skill_transfers.py:78` 原始二进制及目录清单往返断言。 |
| 读取失败、冲突、不支持目录能力整体拒绝 | 有实现：`frontend/src/views/overseas/admin/skill-folder-read.ts:26`、`:32`、`:42`；`frontend/tests/skill-folders.test.ts:24`。 |
| 有效 YAML name/description，正文首 H1/无标题回退 | 上轮问题已修：`frontend/src/views/overseas/admin/skill-folder-metadata.ts:16` 使用 YAML 1.1 与 CommonMark；本地能力不足明确等待服务端判断；`frontend/tests/skill-folders.test.ts:102` 开始覆盖引号、注释、转义、折叠、合并、围栏和 Setext。服务端 `backend/app/overseas/management/installed_catalog.py:63`。 |
| agents/scripts/references/assets/其他资源完整保存 | 字节复制无扩展名过滤：`backend/app/overseas/management/skill_transfer_store.py:134`、`skill_publication.py:55`；**部分实现，合法目录链接和围栏示例误拒绝，见 HIGH**。 |
| 明确资源缺失拒绝 | 新通用校验存在：`backend/app/overseas/management/skill_transfer_store.py:19`；`backend/tests/test_overseas_skill_transfers_failures.py:173` 覆盖 agents/docs/逃逸；但旧误拒绝未消除，不能整体通过。 |
| 不把外部依赖当作可运行验收 | 有明确提示：`frontend/src/views/overseas/admin/SkillFolderUpload.vue:21`。 |
| 64 MiB/256 MiB/1000 文件/2000 条目 | 有实现：`backend/app/overseas/management/skill_transfer_schema.py:8`、`:24`、`:46`；`frontend/src/views/overseas/admin/skill-folder-read.ts:10`；服务端超限拒绝断言 `backend/tests/test_overseas_skill_transfers.py:163`。 |
| 暂存、服务端及安装副本全清单/哈希复核 | 有实现：`backend/app/overseas/management/skill_transfer_store.py:172`、`skill_publication.py:49`、`:65`、`:81`；失败不发布测试 `backend/tests/test_overseas_skill_transfers_failures.py:50`、`:173`。 |
| 新增关闭未分平台，更新保留原开关平台 | 有实现：`backend/app/overseas/management/skill_publication.py:176`；`backend/tests/test_overseas_skill_transfers.py:78`、`:99`。 |
| 持久状态、查询、失败重试、请求幂等 | 有实现：`backend/app/overseas/management/skill_transfer_store.py:51`、`:105`、`:128`；`skill_publication.py:118`；`frontend/src/views/overseas/admin/SkillFolderUpload.vue:23`、`:84`、`:128`；故障恢复断言 `backend/tests/test_overseas_skill_transfers_failures.py:22`、`:85`。 |
| 并发发布序列化，失败旧版本保留及恢复 | 有实现：`backend/app/overseas/management/skill_publisher.py:20`、`:144`；`skill_publication.py:88`、`:133`、`:154`；`backend/tests/test_overseas_skill_transfers_failures.py:65`、`:107`、`:133`、`:153`。 |
| 上传/更新/删除同 can_toggle 且 skills.manage；下载 skills.manage | 有实现：`backend/app/overseas/management/skill_transfer_router.py:11`、`:14`、`:60`、`:71`；publisher 二次授权 `skill_publication.py:19`；权限断言 `backend/tests/test_overseas_skill_transfers.py:151`。 |
| 同名同内容幂等，不同内容增删改清单及显式确认 | 有实现：`backend/app/overseas/management/skill_transfer_store.py:183`；`skill_publication.py:169`；`frontend/src/views/overseas/admin/SkillFolderUpload.vue:17`、`:30`、`:89`；交互断言 `frontend/tests/skill-folders-components.test.ts:50`。 |
| 新轮新包，已提交轮次冻结旧包 | 有实现：发布不移除旧 releases；`backend/app/overseas/management/installed_catalog.py:125`、`:135`；`backend/tests/test_overseas_skill_transfers.py:99`、`:140` 核对旧 frozen bytes。无真实排队/在途端到端新增证据，不据此声称实际任务已经验证。 |
| 仅保存文件夹、用户父目录、原 rootName/历史 name | 有实现：`frontend/src/views/overseas/admin/SkillFolderActions.vue:26`；`backend/app/overseas/management/skill_downloads.py:15`；`frontend/src/views/overseas/admin/skill-folder-save.ts:71`、`:76`。 |
| 固定 release、不混更新内容、逐文件及全树读回、无系统文件 | 有实现：`backend/app/overseas/management/skill_downloads.py:20`；`frontend/src/views/overseas/admin/skill-folder-save.ts:122`、`:147`；`frontend/tests/skill-folders.test.ts:49`。 |
| 目标同名不覆盖、中断明确、核验重试 | 上轮覆盖问题已有针对性修复：`frontend/src/views/overseas/admin/skill-folder-save.ts:43`、`:48` 全树归属/哈希检查，`:105` 目标归属，`:160` writer 创建后重检；`frontend/tests/skill-folders-save-conflicts.test.ts:19` 起 10 项故障用例。组件错误与重试 `SkillFolderActions.vue:20`。浏览器 API 无原子独占创建/CAS 的边界代码已注明，不能宣称防御任意外部进程瞬间并发写。 |
| 选择取消不导出、不支持浏览器提示、ACL/时间不保证 | 有实现：`frontend/src/views/overseas/admin/SkillFolderActions.vue:31` 目录选择先于请求；`skill-folder-save.ts:71`；组件测试 `frontend/tests/skill-folders-components.test.ts:114`；仅写结构和字节，无 ACL/时间保证声明。 |
| 删除二次确认名称/影响、取消、与移出平台区分 | 有实现：`frontend/src/views/overseas/admin/SkillFolderActions.vue:45`；`OverseasSkillCatalog.vue:22`；`frontend/tests/skill-folders-components.test.ts:88`。 |
| 删除版本冲突、当前所有平台/新轮移除、最后项空目录 | 有实现：`backend/app/overseas/management/skill_publication.py:190`、`:205`、`:210`；`installed_catalog.py:43`；`backend/tests/test_overseas_skill_transfers.py:123`。 |
| API 只读、独立 root UDS、权限 0660、拒绝链接/特殊/越界、不执行包代码 | 有实现：`scripts/release/skill-folders-deploy.py:46`；`backend/app/overseas/management/skill_publisher.py:129`、`:157`；`installed_tree.py:22`、`:46`、`:67`。已读 `output/skill-folders-release/linux-permissions.log:1`：实际 Linux 路径、API uid10001 只读且可连 UDS，其他 uid 拒绝。 |
| 操作者审计、现有配置字节保护 | 有实现：`backend/app/overseas/management/skill_publication.py:137`；部署基线与 Compose 差异约束 `scripts/release/skill-folders-deploy.py:70`、`:107`。 |
| 备份恢复测试、gate、native 限定 reader、API 与静态发布 | 有实现：`scripts/release/skill-folders-deploy.py:124`、`:132`、`:147`、`:153`、`:211`、`:245`、`:294`；native 范围 `skill-folders-runtime.py:18`、`skill-folders-native.py:16`。正式 release 安装、备份恢复和生产验收仍是后续交付，不用候选测试代替。 |
| 既有 ElCard/ArtTable/Dialog 样式、滚动树、错误进度、窄屏 | 静态匹配：`frontend/src/views/overseas/admin/OverseasSkillCatalog.vue:2`、`SkillFolderUpload.vue:2`、`:12`、`:14`、`:140`。主 Agent 最终浏览器证据尚未完成；不宣称实际页面/邻居视觉已验证。 |

## Spec 漂移

已读新增 API、publisher、状态目录及发布工具均对应合同第 3、7 项，未发现新增独立业务页面或数据库表。证据：`backend/app/overseas/management/skill_transfer_router.py:20`、`skill_transfer_store.py:78`、`scripts/release/skill-folders-runtime.py:15`。没有据此将未完成的 Stage 2 安全扫描记作 PASS。

## 已读取的编译与测试原始输出

以下为读取主 Agent 已运行日志，独立 reviewer 未重复运行全套。`output/skill-folders-frontend-build.log:2`、`:3` 及末尾：

```text
> hengxin-smart-image-frontend@0.2.63 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4807 modules transformed.
✓ built in 34.36s
```

`output/skill-folders-frontend-all-final.log` 末尾原始输出：

```text
ℹ tests 514
ℹ suites 0
ℹ pass 514
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 10897.285
```

`output/skill-folders-backend-final.log` 与 `output/skill-folders-release/linux-pytest.log` 原始结果：

```text
26 passed, 2 warnings in 23.70s
48 passed, 2 warnings in 23.91s
```

`output/skill-folders-release/linux-permissions.log:1` 原始输出：

```json
{"image": "hengxin-skill-folders-test:358116fe29283ef2", "productionShapedPaths": true, "apiUid": 10001, "socketMode": "0660", "minimalEnvironmentStartup": "PASS", "apiReadOnlyCatalogAndSocket": "PASS", "unauthorizedUid": "DENIED"}
```

这些通过不能覆盖上述真实复现的合法输入失败。

## Stage 2：未执行

因 Stage 1 HIGH 停止。代码质量、完整安全扫描、测试真实性与实际邻居视觉比较未登记结论。修复后重新固定 candidateId，从 Stage 1 重新审查，再进入 Stage 2。本报告不能批准后续变化，也不写 `.needs-review`。
