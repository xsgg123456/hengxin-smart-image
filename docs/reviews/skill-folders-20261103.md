# 海外 Skill 文件夹管理独立审查

## 审查快照与范围

- 首轮 candidateId：`d3eefd67248a115f3041688f4ece119ad732195e709fa364d523fb22b624bff2`。
- 范围：主 Agent 交付的全部 git diff 与未跟踪实现、测试、发布工具；需求依据 `docs/SKILL-FOLDERS-IMPLEMENTATION-20261103.md:7` 及 Product-Spec、DEV-PLAN、Design-Brief 末尾本轮补充。
- 审查过程中主 Agent 调整浏览器测试选择器，并启动修复。只读 `review-status` 已返回当前 `4bfb347b4bdc8d11bba83528fbdd39e73f0cd885fee538989b096ea21776be37`，与送审候选不同。本报告是首轮失败记录，不能批准后续快照。
- 使用 `.agents/skills/code-review/SKILL.md`。独立 reviewer 只读代码、执行最小复现并写报告，未修改实现、未提交、未执行生产变更。

## Stage 1：FAIL

### HIGH：导出可覆盖本地已有文件

合同第 5 项要求“目标同名不覆盖；中断明确不完整并支持核验重试”。`hengxin-smart-image/frontend/src/views/overseas/admin/skill-folder-save.ts:23` 仅在创建根目录时枚举；`:60` 对每个文件无条件 `getFileHandle(create:true)` 并 `createWritable()`，`:61` 写入。网络传输期间出现同名文件，或中断后用户编辑已保存文件再重试，均会覆盖用户内容，最终仍报告成功。

独立执行真实 `prepareFolderSave` / `writeFolder`，使用项目 `MemoryDirectory` 文件系统接口实现：准备完成后在目标创建 `SKILL.md`，内容为 `USER-OWNED EXISTING BYTES`；再执行写入。原始输出：

```text
EXISTING_FILE_AFTER_WRITE=---
name: fixture
description: 完整目录测试
---
# 测试技能
```

应在写入及恢复前核对目标归属与已写指纹，意外同名或用户改动必须冲突并保留字节；重试不能无条件覆盖已有文件。新增测试必须覆盖准备完成之后、网络等待期间及失败重试之前的目标变化。

### MEDIUM：本地预览不按 YAML / Markdown 解析

合同第 1、2 项要求读取有效 YAML name/description、正文首个一级标题。`hengxin-smart-image/frontend/src/views/overseas/admin/skill-folder-read.ts:54` 至 `:60` 使用正则提取，合法 YAML 引号键被拒绝，行末注释被当成描述，代码块中的 `#` 被当成标题。服务端实际安全 YAML 解析在 `hengxin-smart-image/backend/app/core/skill_package.py:99`，实际 Markdown 标题解析在 `hengxin-smart-image/backend/app/overseas/management/installed_catalog.py:64`，两端行为不同。

独立以 `node --import tsx --input-type=module -` 调用真实 `scanFolder`，原始输出：

```text
SKILL.md 必须声明 name 和 description
{"name":"fixture","description":"\"hello\" # comment","displayName":"Fake title"}
```

第一例为合法 `"name": fixture` / `"description": valid YAML`；第二例为 `description: "hello" # comment`、代码块中的 `# Fake title`、代码块后的 `# Correct title`。需真实解析及引号键、注释、转义、折叠描述、围栏代码、Setext 标题测试。

### MEDIUM：明确包内资源缺失未完整拒绝

合同第 2 项要求“明确的包内资源引用缺失拒绝”，且资源不限于固定目录。新上传在 `hengxin-smart-image/backend/app/overseas/management/skill_transfer_store.py:143` 调用 `tree`，后者沿用 `installed_tree.py:143` 的固定目录子串判断。明确的 Markdown 相对链接指向 `agents/missing.yaml` 或 `docs/missing.md` 时跳过校验；这不满足本轮新上传契约。

通过 AST 提取并执行文件中原 `check_references` 函数，原始输出：

```text
agents/missing.yaml: ACCEPTED
docs/missing.md: ACCEPTED
assets/missing.png: REJECTED Skill reference is missing: assets/missing.png
```

可以在新上传路径追加通用资源校验，避免改变历史冻结包读取语义；若修改共享 reader，必须同步 API/native 发布范围与基线。

### 逐项覆盖

下表“有实现”表示本轮已读到相应代码及所列测试断言，不替代未完成的独立运行/浏览器验收。

| 合同条目 | 结论与证据 |
| --- | --- |
| 单个完整目录拖入，分页超过 100 项 | 有实现：`frontend/src/views/overseas/admin/skill-folder-read.ts:13`、`:41` 循环至空批次；`frontend/tests/skill-folders.test.ts:16` 检查 206 文件、4 次 readEntries。路径均相对 `hengxin-smart-image/`。 |
| 原字节、空目录、SHA-256、数量、大小、目录树 | 有实现：`frontend/src/views/overseas/admin/skill-folder-read.ts:30`、`:37`、`:63`；`backend/app/overseas/management/skill_transfer_store.py:113` 原始流写入；`backend/tests/test_overseas_skill_transfers.py:78` 比对下载二进制及完整清单。 |
| 任意读取失败/路径冲突/不支持目录能力整体阻止 | 有实现：`frontend/src/views/overseas/admin/skill-folder-read.ts:25`、`:32`、`:42`；`frontend/tests/skill-folders.test.ts:24`。 |
| YAML 名称描述、首 H1、名称回退 | **部分实现**：服务端真实解析，本地拒绝合法 YAML、预览错误，见上项。 |
| agents/scripts/references/assets/其他资源与引用 | **部分实现**：流和发布复制无扩展名过滤；明确引用校验漏 agents/docs，见上项。`backend/app/overseas/management/skill_publication.py:54`。 |
| 外部依赖不等于可运行提示 | 有实现：`frontend/src/views/overseas/admin/SkillFolderUpload.vue:21`。 |
| 64 MiB / 256 MiB / 1000 文件 / 2000 条目 | 有实现：`backend/app/overseas/management/skill_transfer_schema.py:8`、`:24`、`:46`；`frontend/src/views/overseas/admin/skill-folder-read.ts:8`、`:29`、`:34`。服务端参数化拒绝测试在 `backend/tests/test_overseas_skill_transfers.py:163`。 |
| 暂存、服务端全清单与安装副本核验 | 有实现：`backend/app/overseas/management/skill_transfer_store.py:143`；`skill_publication.py:49`、`:65`、`:79`。故障断言在 `backend/tests/test_overseas_skill_transfers_failures.py:50`、`:173`。 |
| 失败旧版本不变、发布恢复 | 有实现：`backend/app/overseas/management/skill_publication.py:88`、`:133`；pending 阻止新读取位于 `installed_catalog.py:97`。指针/提交故障及审计恢复测试在 `backend/tests/test_overseas_skill_transfers_failures.py:65`、`:107`、`:133`。 |
| 新增关闭未分组，更新保留配置 | 有实现：`backend/app/overseas/management/skill_publication.py:176` 仅新增重置；`backend/tests/test_overseas_skill_transfers.py:78`、`:99`。 |
| 持久状态、查询、失败重试、幂等 | 有实现：`backend/app/overseas/management/skill_transfer_store.py:16`、`:67`；`skill_publication.py:118`；`frontend/src/views/overseas/admin/SkillFolderUpload.vue:23`、`:86`；丢失状态保存恢复测试在 `backend/tests/test_overseas_skill_transfers_failures.py:85`。 |
| 并发发布序列化 | 有实现：`backend/app/overseas/management/skill_publisher.py:20` 进程内锁及 `:144` 进程锁；`skill_publication.py:154` DB gate；并发断言在 `backend/tests/test_overseas_skill_transfers_failures.py:153`。 |
| 上传更新删除同开关权限且 skills.manage，下载 skills.manage | 有实现：`backend/app/overseas/management/skill_transfer_router.py:11`、`:14`、`:60`、`:71`；publisher 再授权 `skill_publication.py:19`。权限测试在 `backend/tests/test_overseas_skill_transfers.py:151`。 |
| 同名同内容幂等；不同内容完整 diff 与明确确认 | 有实现：`backend/app/overseas/management/skill_transfer_store.py:155`；`skill_publication.py:165`、`:169`；`frontend/src/views/overseas/admin/SkillFolderUpload.vue:17`、`:30`、`:96`；SFC 交互测试 `frontend/tests/skill-folders-components.test.ts:50`。 |
| 更新后新轮用新包，历史冻结保留 | 有实现：`backend/app/overseas/management/installed_catalog.py:125`、`:135`；`skill_publication.py:75` 保留 immutable release；`backend/tests/test_overseas_skill_transfers.py:99`。 |
| 仅文件夹导出、父目录选择、原 rootName/历史 name | 有实现：`frontend/src/views/overseas/admin/SkillFolderActions.vue:26` 先目录选择再请求；`backend/app/overseas/management/skill_downloads.py:15` 回退旧 name；文件夹写入 `skill-folder-save.ts:20`。 |
| 固定 release、逐文件读回及全清单、无系统文件 | 有实现：`backend/app/overseas/management/skill_downloads.py:20`；`frontend/src/views/overseas/admin/skill-folder-save.ts:34`、`:58`、`:62`；`frontend/tests/skill-folders.test.ts:45`。 |
| 不覆盖、失败重试 | **不匹配 HIGH**：仅初次根目录检查，写入及重试可覆盖。见首项复现。 |
| 取消选择不导出、不支持浏览器明确说明 | 有实现：`frontend/src/views/overseas/admin/SkillFolderActions.vue:31`；`skill-folder-save.ts:15`；`frontend/tests/skill-folders-components.test.ts:114`。 |
| 删除确认名称影响、取消不变、与移出平台区分 | 有实现：`frontend/src/views/overseas/admin/SkillFolderActions.vue:45`；`OverseasSkillCatalog.vue:22`；`frontend/tests/skill-folders-components.test.ts:88`。 |
| 删除版本冲突、所有平台及新轮移除、最后合法空目录 | 有实现：`backend/app/overseas/management/skill_publication.py:190`、`:205`、`:210`；`installed_catalog.py:43` 允许空列表；`backend/tests/test_overseas_skill_transfers.py:123`。 |
| 删除不破坏已冻结/排队/在途/重试 | 有实现：仅 current 指针与可用状态更新，旧 release 不删除；`backend/app/overseas/management/installed_catalog.py:135` 直接读 frozen release；`backend/tests/test_overseas_skill_transfers.py:140` 核对旧内容。真实队列端到端证据仍待最终集成。 |
| API ro、root UDS 专用受控发布、拒绝越界/链接/特殊文件、不执行脚本 | 有实现：`scripts/release/skill-folders-deploy.py:31` 限定 env、`:46` 三挂载、只读根；`skill_publisher.py:129` root 身份及 `:157` socket 权限；`installed_tree.py:22`、`:46`、`:67` 拒绝异常树；所有包代码仅复制不执行。实际权限原始日志待主 Agent 提供。 |
| 操作者审计、保护原配置与部署范围 | 有实现：`backend/app/overseas/management/skill_publication.py:137`；`scripts/release/skill-folders-deploy.py:70` 校验基线、`:107` 限制 Compose 差异、`:295` 检查回退前 Skill 树；`skill-folders-runtime.py:15` 固定 9 个 API 文件和 1 个 native reader。 |
| 现有 UI 体系、目录树滚动、错误进度、窄屏 | 静态接线存在：`frontend/src/views/overseas/admin/SkillFolderUpload.vue:2`、`:12`、`:14`；实际页面和邻居视觉比较尚未执行，因 Stage 1 HIGH 停止，不宣称通过。 |

### Spec 漂移

未发现本轮新增独立业务页面或数据库表；新增 transfer API、publisher、临时状态目录和发布工具对应合同第 3、7 项。证据：`backend/app/overseas/management/skill_transfer_router.py:20`、`skill_transfer_store.py:43`、`scripts/release/skill-folders-runtime.py:15`。本结论仅覆盖已读的送审实现，后续修复快照仍需复核。

## Stage 2：未执行

存在 Stage 1 HIGH，不进行或登记 Stage 2 PASS。代码质量、安全扫描、完整测试真实性检查与真实邻居视觉比较留待修复后的新候选。

## 已读取的测试/编译输出

主 Agent 提供的旧候选前端日志 `output/skill-folders-frontend-all-final.log` 原始尾部：

```text
ℹ tests 501
ℹ suites 0
ℹ pass 501
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9921.947
```

`output/skill-folders-frontend-build.log` 原始结果：

```text
✓ built in 38.03s
```

以上是读取既有日志，不是本 reviewer 重新运行。后端 43 项、UDS 实际权限及浏览器结果目前只有交接说明；尚未读取原始日志，不用其作为最终 PASS 依据。后续修改须重新测试并以新 candidateId 从 Stage 1 复审，主 Agent 不得以本报告执行 review-approve。
