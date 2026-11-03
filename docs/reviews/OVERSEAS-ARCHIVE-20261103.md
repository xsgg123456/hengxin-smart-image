# 成品库字段与图片缓存独立审查 · R1

日期：2026-11-03。审查者：独立 code-reviewer；使用 `.agents/skills/code-review/SKILL.md`。未修改业务代码、未提交、未部署、未登记批准。

- candidateId：`63d2cfc1d3bd35291ddfe4f30b229887fd3770148c193217ca79286155f0f3ee`
- Stage 1：**PASS**（本轮产品实现对照通过；生产安装验收仍待执行）。
- Stage 2：**FAIL**（1 项 MEDIUM 发布故障恢复缺陷，见 R1-01）。
- 本候选不得执行 `review-approve`。主 Agent 已收到缺陷并开始修复；报告末次 `review-status` 的 currentId 已变为 `f2358568e91e7b88a3d781b187e34b64a4eb4f0ee66de2e1bfd0195088f4106c`。此报告不批准该新版本，新候选必须重新固定并复核。
- 报告收尾时主Agent提供最终新候选 `99cf8747a7f5599cda2c3e70c3eaeabffe57206fabfcd9e24d1597a185125a18`，说明仅修复 `scripts/release/archive-deploy.py` 的临时文件所有权/清理和 `scripts/release/test_archive_release.py` 的三项故障测试。新鲜 reviewer 另行复核；本报告保留R1 FAIL，不替代新候选结论。主Agent已将release-final.log更新为26项，本报告中的23项原始输出是修复前已读取的证据。

## 范围与依据

完整读取 `docs/OVERSEAS-ARCHIVE-PENDING-20261103.md`，对照 `Product-Spec.md:1398`、`DEV-PLAN.md:1616` 与 `Design-Brief.md:212` 相关原文。范围为送审时全部 diff 和未跟踪新代码：前端 package 版本；archives API、共享 image-cache；归档页面、详情、字段、图片、查看器；Studio 归档入口；三个归档 composable；六个修改的前端测试、新增字段浏览器脚本；`scripts/archive-cache/` 五个文件；三个 `archive-*` 发布脚本和两个发布测试。无后端、数据库或依赖版本变更。

下文 `F/` 表示 `hengxin-smart-image/frontend/`，`B/` 表示 `hengxin-smart-image/backend/`；行号按 R1 实际读取版本。发布脚本及测试随后发生修复时，其行号可能移动，不应把旧行号视作新版本结论。

## Stage 1：需求逐条核对

| 条目 | 结论与实现证据 | 验证证据 |
| --- | --- | --- |
| 六字段同名、同序、同样式 | 完整实现。`F/src/views/overseas/OverseasArchiveFields.vue:10` 顺序为 SKU、目标平台、品牌、任务名称、品名、语言；`:27` 定义双列、14px、56px 标签、12/24px 间距。`F/src/views/overseas/studio/StudioArchiveFields.vue:2` 与详情 `OverseasArchiveDetail.vue:7` 直接共用同一组件。 | 字段 SFC 同值断言；`output/archive-fields-browser.log:1`；已目视 1366-single 与 390-multi 截图。 |
| 历史语言、空值和中文语言名 | 完整实现。`OverseasArchiveFields.vue:11` 至 `:15` 使用空值文案和 languageLabel，不从当前任务猜测历史语言。 | `F/tests/studio-process-component.test.ts` 字段测试覆盖四语言和历史缺值；390-multi 截图明确为“未设置”。 |
| 整套 SKU 与本批图片归属分开 | 完整实现。`OverseasArchiveFields.vue:24` 汇总全部 SKU；`F/src/views/overseas/studio/OverseasStudio.vue:44` 多 SKU 才出现“本次归档所属 SKU”；`:114` 单 SKU 自动归属，SKU 变化剔除失效选择。 | `studio-lifecycle-component.test.ts` 单/多 SKU 用例；字段浏览器脚本实际点归档并断言 SKU 与 `pictureIds=['p1']`。 |
| 来源会话、选图数量及原归档调用保留 | 完整实现。`OverseasStudio.vue:44` 说明区仍显示会话和张数，确认按钮继续走 doArchive。 | `F/tests/archive-fields.browser.mjs:112` 起确认实际请求载荷；`output/archive-fields-browser.log:1` PASS。 |
| 独立快照不覆盖历史 | 完整实现且后端未改。详情只读归档 API；`B/app/overseas/archives/snapshot.py:12` metadata 仍只在未初始化时捕获任务名称、语言和产品字段。 | diff 无后端修改；`F/tests/overseas-delete-component.test.ts:118` 附近的已删来源任务详情测试；真实 HTTP fixture 使用 `taskId:null/sourceDeleted:true`。 |
| 封面与详情小图走缩略图，不触发列表整套原图 | 完整实现。`F/src/views/overseas/use-archive-image.ts:6` 默认 thumbnail；`:23` 传 true；`F/src/api/overseas/archives.ts:76` 增加 thumbnail query；原封面调用沿用该 hook。预取只在详情/viewer挂载。 | `output/archive-cache/result.json:5` 起：列表原件 GET=0，详情六张缩略图宽240；截图中完整等比。 |
| 原图查看、缩放和下载保持原件 | 完整实现。`OverseasArchiveViewer.vue:22` 请求原件；`use-archive-image.ts:31` 校验 MIME/字节数；`use-archive-download.ts:12` 获取同一缓存租约并校验后 saveBlob，无转码。 | 浏览器原件 1600×1000、滚轮缩放、切图返回；下载 SHA256 实际/预期均 `a17a7b22637a636c8f0ae43697ba73c432435419962579556310c6bdc76b9f77`，见 result.json:36。 |
| 下载不依赖缩略图完成 | 完整实现。`OverseasArchivePicture.vue:8` 下载不以 thumbnail blob 禁用；独立 `use-archive-download.ts:8` 处理加载/错误。 | HTTP 验证延迟缩略图3500ms时，点击下载完成且缩略图尚未显示；对应 browser.mjs:57。 |
| 最多两个原图并发、点击优先、在途去重 | 完整实现。`F/src/api/overseas/image-cache.ts:79` active<2；`:93` 同URL合并并将前台 priority升为1；`:81` 按优先级出队。 | 独立重跑共享缓存测试；HTTP 六张原件最大并发2；既有工作台真实HTTP18项包含点击晋升与去重。 |
| 沿用128MiB/40张、淘汰及超大图按需 | 完整实现。`image-cache.ts:15` 预算、`:26` 跳过当前租约淘汰；`:139` 跳过大预取；`image-cache-http.ts:3` 单原件预取32MiB保护，`:17` 流读取也限额。 | 独立重跑容量、巨大原图释放、未知长度超限、在途不淘汰等单测。当前租约可暂超预算，释放后恢复，未宣称任何时刻总内存绝不超128MiB。 |
| detail/viewer/workspace owner 隔离 | 完整实现。`image-cache.ts:18` owner表、`:144` 创建独立owner；`:49` 汇总所有owner需要；`:122` 只取消无人需要且无前台消费者的作业。`use-archive-prefetch.ts:6` 每挂载实例独立创建。 | 独立重跑三个新增 owner/晋升/前缀隔离用例，工作台HTTP18项回归证据。 |
| 关闭、切筛选取消无用预取，保留完成缓存 | 完整实现。`use-archive-prefetch.ts:10` 卸载dispose；`OverseasArchiveDetail.vue:49` 仅预取筛选结果且筛选同步关闭查看器；`OverseasArchivePage.vue:62` 搜索/翻页关闭详情和预览。 | HTTP 延迟请求验证 abort、旧组第三张不发GET；列表搜索关闭直接查看器。 |
| 私有条件缓存及版本、权限重验 | 完整实现。`image-cache.ts:52` credentials+no-cache+redirect:error；`:64` HEAD/ETag；变更则丢弃后GET；`archives.ts:76` 缩略图no-cache。`B/app/overseas/archives/service.py:118` 先鉴权归档，再验证图片归属；`B/app/overseas/image_delivery.py:55` private/no-cache/Vary。 | 真实Chromium刷新后的六个GET均304/零正文；热缓存重新预览只有HEAD校验；版本变化由共享缓存单测和工作台HTTP回归覆盖。 |
| 退出/换号、撤权、删除、资源失效清缓存 | 完整实现。`F/src/views/overseas/OverseasPortal.vue:37` 身份变化同步setIdentity，`:178` 卸载清理；`archives.ts:17` 按归档URL前缀失效，get/content/download错误和remove成功使用；`OverseasArchiveDetail.vue:56` 401/403/404/409收起内容。 | HTTP403清空整套、删除响应即清缓存、换号/退出；独立重跑状态错误与owner撤权单测。 |
| 使用独立URL，不跨任务靠文件名复用 | 完整实现。`archives.ts:16` URL包含encodeURIComponent归档ID和图片ID；`image-cache.ts:17` 以完整URL为键。 | 前缀a与ab隔离单测；独立快照访问测试。 |
| 冷热请求、字节与耗时实证 | 完整记录。`scripts/archive-cache/browser.mjs:33` 记录冷、热操作；未将二者不同操作耗时相除作“加速比”。 | 冷：6GET/4,574,682正文bytes/144ms；热切换组合：新增0GET/0正文bytes/631ms。均为localhost fixture，不能推断生产带宽。 |
| 最小前端发布、已审制品门禁 | 实现存在。`F/package.json:3` 0.2.62；`scripts/release/archive-package.py:25` clean+reviewed_status、`:34` 重build、`:45` 逐文件隐私校验；`:55` 最终提交与快照再核对。 | 发布23项原始日志；package负向测试覆盖dirty/未审/源码竞态/dist竞态/隐私失败。后端无改动，不新增DB迁移。 |
| 入口备份、哈希资源保留、安装HTTPS哈希及后台不变 | 主路径完整。R1 `archive-deploy.py:30` switch先备份；`:79` rollback保留哈希资源；`:109` deploy比较前后baseline；`archive-runtime.py:112` installed核对最终安装路径与真实HTTPS入口/静态引用、国内海外ready。异常恢复可靠性缺陷列入Stage2。 | 原发布测试的真实临时目录switch/rollback、健康失败和服务漂移测试；生产只读baseline/protected-baseline文件。正式部署尚未执行，不把这些当安装后PASS。 |

部分实现/未实现：产品条目未发现缺项；发布实施与正式入口验收属于下一步尚未执行工作，不能宣称已交付。无新增业务API、数据库表或未获授权页面，未发现Spec漂移。查看器下载按钮直接服务合同的原件下载要求。

## Stage 2：问题与质量审查

### R1-01 · MEDIUM · 原子复制内部失败遗留临时文件，阻塞回退重试

位置：R1 `scripts/release/archive-deploy.py:18` atomic_copy（固定临时名、`open('xb')`、chmod、replace，未在异常时清理）；`:99` rollback再次调用相同函数；`:123` deploy异常恢复。测试盲区：R1 `scripts/release/test_archive_release.py:147` 的 partial switch测试是在调用atomic_copy之前抛错，未走到临时文件已创建的状态。

独立复现：复用已有测试fixture建立真实临时安装目录，仅令 `os.replace(..., frontend/package.json)` 第一次抛 `PermissionError`，之后恢复正常。结果：原始错误被自动rollback中的FileExistsError覆盖；故障已解除后的再次rollback仍抛相同错误。实测原入口内容最终恢复，**未观察到数据损坏或新旧入口混用**，因此列MEDIUM，不夸大为HIGH。证据：`output/archive-release/reviewer-atomic-failure.json:2`。

原始输出（临时目录随机段省略）：

```text
deployException: FileExistsError: [Errno 17] File exists: .../frontend/package.json.archive-new
originalEntriesRestored: true
leftoverTemporary: [frontend/package.json.archive-new]
retryRollbackException: FileExistsError: [Errno 17] File exists: .../frontend/package.json.archive-new
```

修复验收：清理仅本次成功创建且拥有的临时文件，不删除预先存在的未知文件；在atomic_copy内部replace/写入故障进行回归，证明异常不被覆盖、入口恢复、故障解除后rollback可重试。由主Agent修复，重新prepare后独立复审。本报告不判断正在写入的新修复是否通过。

### 其余质量、安全与视觉

- 代码质量检查通过范围：送审新增/修改代码文件均未超过300行；新增生产TS无any类型。缓存继续集中在 `F/src/api/overseas/image-cache.ts:13`，缩略图/租约、下载、预取职责分别在三个hook。无第二套缓存。
- 安全扫描：检查了送审文件中的密钥前缀、敏感环境变量、eval、dangerouslySetInnerHTML/innerHTML、用户绝对路径及类型any。命中仅AbortSignal.any/Python any等非危险调用；测试中已有动态SFC编译不属于用户可达业务执行。`archives.ts:16` 编码资源路径，`image-cache.ts:52` 禁重定向；发布 `archive-runtime.py:35`/`:58` 检查链接、路径与清单哈希，`archive-package.py:45` 复用隐私检查；未发现本轮新增HIGH安全问题。
- 视觉已实际打开新截图和邻居基准：`output/archive-preview/review-detail.png`、`output/materials-archive-release/archive-single.png`；对照本轮 `output/playwright/archive-fields/1366-single.png`、`390-multi.png` 及 `output/archive-cache/02-detail.png`、`03-viewer.png`、`05-narrow-detail.png`、`06-narrow-download.png`。六字段排列和窄屏单列匹配；蓝色主操作、弱化标签、白色弹窗与等比图片延续现有组件；长名称换行，确认按钮/下载可达。图片HTTP fixture未加载完整Art主题，不能把其默认Element圆角或字体差异当正式主题回归；完整dist字段截图用于正式shell/弹窗样式判断。
- 测试真实性：浏览器图片测试未使用request routing，走真实localhost HTTP/ETag/304，下载哈希和浏览器naturalWidth/Height均是行为断言。字段浏览器测试使用隔离API，能证明前端归档请求，不能证明生产写入。部分组件测试stub预取和Element组件；相应缓存/交互由HTTP浏览器与共享缓存单测补充。独立复跑33项通过。
- 明确盲区：本次未生产写入/删除/生图；生产真实身份/存储内容与安装路径尚待主Agent正式部署后的只读验收。未进行进程kill/断电级发布恢复测试。R1-01说明原23项发布测试并未完整覆盖函数内部文件故障。
- 依赖审计为已有告警（记录critical0/high39/moderate38/low5），本轮package仅改版本，无锁文件/依赖修改；不把“无新增代码安全发现”写成“项目无漏洞”。

## 编译与测试证据

读取主Agent最终原始日志：`output/archive-all-tests-final.log`、`output/archive-typecheck-final.log`、`output/archive-build-final.log`、`output/archive-release/release-final.log`；正式字段浏览器日志PASS、图片HTTP13项及工作台HTTP18项。类型检查退出0由主Agent提供，日志本身仅有命令头、无错误，不把没有报错单独推定为退出码证据。没有重复全量构建。

原始输出摘录（完整日志见上述路径）：

```text
ℹ tests 486
ℹ suites 0
ℹ pass 486
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 11909.3641

> hengxin-smart-image-frontend@0.2.62 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit

✓ built in 32.40s

----------------------------------------------------------------------
Ran 23 tests in 0.938s

OK
```

独立复跑命令：在 `hengxin-smart-image/frontend` 执行 `pnpm exec tsx --test tests/overseas-image-cache.test.ts tests/overseas-delete-component.test.ts tests/studio-process-component.test.ts tests/studio-lifecycle-component.test.ts`，工具返回exit_code=0。原始结果：

```text
ℹ tests 33
ℹ suites 0
ℹ pass 33
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 3629.1884
```

该次输出另有既有测试stub的ElTabs/ElTabPane解析警告，以及pnpm配置迁移warning；未伪报为无警告。已发现的发布内部失败路径独立复现实验不包含在这33项中，其失败结论为R1-01。
