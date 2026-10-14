# 原生工作台独立审查 R5（2026-10-14）

- candidateId：`3fde16d6f7ec638ec7138489542d566e2e09b11133104915ad79b48db80fbf12`。
- **Stage 1：FAIL（1 项 HIGH）；Stage 2：未执行。不得登记两阶段 PASS。**
- 范围：本次 overseas studio、execution/runner、db、任务清理、0015 迁移与测试；前端 API/studio/Markdown/轮询/版本依赖与测试；native-studio deploy/runtime/package-overseas 与测试。不是历史全产品重审。
- 原文依据：AGENTS.md、`.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、`Product-Spec.md:1100` 原生工作台章节、DEV-PLAN.md 最后迭代、`docs/NATIVE-STUDIO-RELEASE-20261014.md`。前轮报告仅用作缺陷历史。本轮重新读实现、独立构造反例并运行专项。
- 审查开始及写报告前 review-status 均为上述 currentId。主 Agent 已确认保持冻结；reviewer 不改实现、不提交、不部署、不批准、不发生产付费调用。

## Stage 1 阻断

### HIGH S1-01：图片 alt 内的 Markdown 强调仍绕过非交付排除

Spec 原文（`Product-Spec.md:1106`）：“临时图、草稿、试验图、中间文件不显示、不归档”，“Markdown正文中的图片也遵守同一交付门禁”。明确标记非最终图片的引用不能仅因强调格式变化而成为正式图片。

位置：`hengxin-smart-image/backend/app/overseas/studio/delivery.py:47`–`:53`。`non_delivery()` 只遍历顶层 inline 子 token；遇到 `image` 时直接取 `child.content`。图片 token 自身还有解析后的 children，当前没有递归处理，alt 中的 `**` 因而保留，英文否定规则无法匹配。

独立复现使用 TemporaryDirectory、本轮 work/home、`.codex/generated_images/session`，Pillow 创建真实 12×13 PNG，baseline 为空；调用生产 `collect_delivery()`，summary 为成功完成、无 error、session_id=session。没有绕开图片归属/真实性校验。退出码 0，原始输出：

```text
'![not final images](/work/image.png)' accepted= [] warnings= []
render= <p><img src="/work/image.png" alt="not final images" /></p>
'![**not** final images](/work/image.png)' accepted= ['/work/image.png'] warnings= []
render= <p><img src="/work/image.png" alt="not final images" /></p>
'![not **final images**](/work/image.png)' accepted= ['/work/image.png'] warnings= []
render= <p><img src="/work/image.png" alt="not final images" /></p>
'These are **not** final images.\n\n![Image](/work/image.png)' accepted= [] warnings= []
```

其中 render 是同一后端 MarkdownIt commonmark 的标准渲染，用于证明图片子 token 的等价文本，不冒称正式前端截图。前端自定义 renderer 也不会再判定否定交付，只认后端批准映射。

影响链已经核对：`backend/app/overseas/studio/execution.py:85` 接收结果并保存对象，`:110` 发布 Picture；`queries.py:55` 返回 sourcePath；`frontend/src/views/overseas/studio/studio-markdown.ts:13`、`:42` 将已批准路径加载为图；`StudioTurns.vue:12` 提供选择，`backend/app/overseas/studio/service.py:93` 支持归档。因此不是无影响的正则差异，明确非最终图片能进入正式集合并归档。

R5 已修好正文强调的 R4 反例，未修完嵌套图片 alt。`backend/tests/test_studio_formal_delivery.py:118` 把 notice 放在正文/标题，`:98` 的 alt 用例没有格式化否定；138 项通过没有覆盖此反例。

修复验收：统一递归获取 Markdown 可见文字，图片 alt 内强调也须识别；覆盖直接图片、被下载链接包裹的图片、前后段落及标题作用域，保留肯定正式交付对照和原文。需真实 collector 与 runner→API 断言无 Picture，重新固定候选并从 Stage 1 重审。

## Stage 1 逐项核对

下表 backend/、frontend/ 相对 `hengxin-smart-image/`。匹配仅指所列实现和证据，不代表整体通过。日志为提供证据时明确标注，未冒充本 reviewer 重跑。

| Spec 条目/发布约束 | 结论与证据 |
|---|---|
| 普通消息原样，每新 CLI 会话首轮仅指定一句人设 | 完整实现：`backend/app/overseas/studio/execution.py:62`–`:68` 条件人设、原样 text、条件引用；`backend/tests/test_overseas_studio_conversations.py:37` 捕获 worker 精确 prompt，本轮独立测试通过。 |
| 仅选中附件/Skill，不重复商品背景、步骤数量格式，不改包 | 完整实现：`studio/service.py:51`–`:64` 只取显式 IDs，`execution.py:47`–`:68` 构造必要路径；本轮差异不含 Skill 包，发布 `scripts/release/native-studio-runtime.py:70` 只验证。 |
| 既有隔离/权限 | 匹配：`execution.py:19` 独立 conversation home，`:40` workspace-write；`transcript.py:90` 校验 claim/lease/任务/会话；`queries.py:15` 任务权限。专项含会话不符、claim 不符及撤权读取。 |
| 新对话重置 CLI，保留全部历史/资料/图片归档 | 完整实现：`service.py:73` 仅新建 Conversation，`queries.py:63` 全历史读取；`test_overseas_studio_conversations.py:16` 验新 home/非 resume/历史材料，`:57` 验多会话清理不删归档；本轮通过。 |
| 新对话在途及 uncertain 阻止、并发幂等 | 完整实现：`service.py:16` 锁及幂等，`:26` 非 TERMINAL 阻止；`frontend/.../use-studio.ts:14` 锁、`:79` 未知响应保留 key；提供真实 PG 日志 66 passed、0 skipped（本轮未重跑 PG）。 |
| 完整公开 assistant 多条与更新，顺序持久化；公开摘要/工具状态 | 完整实现：`transcript.py:15` 白名单、`:41` 追加快照、`:49` 独立 reply，`queries.py:92` ID 排序；`frontend/.../studio-transcript.ts:4` 按 turn/item 更新。长文、多条、更新、敏感工具字段不出 API 专项本轮通过。 |
| Markdown 代码/链接、HTML 不执行、图片及下载授权 | 部分实现：`frontend/.../studio-markdown.ts:4` 禁 HTML，`:18` 未批准本地链接文本化，API 校验图片任务/ID；但后端图片门禁被 S1-01 污染，不能整体判定匹配。 |
| 1 秒级增量、分页/重连去重、尾部 UTF-8 | 完整实现：`transcript.py:54` 字节游标，`backend/app/overseas/execution/runner.py:129` final_poll；`queries.py:92` 500+1 分页；`use-studio.ts:34` 1000ms、`:42` 连续补页。专项 502 条、半行、重复读取通过。 |
| 过程默认展开、终态折叠、历史不强拉底 | 匹配：`StudioTranscript.vue:4` open=running，`StudioTurns.vue:37`–`:41` 更新前后滚动；提供 browser 日志及 `frontend/tests/studio-native.browser.mjs` 的真实 scrollTop/终态断言通过，本轮未重跑浏览器。 |
| 隐藏/卸载停请求，返回补齐；静默自动刷新 | 匹配：`use-studio.ts:34` 可见性调度、`:62` abort/返回同步、`:105` 卸载，`:53` 手动 loading 分离；提供新旧浏览器 PASS 与 356 前端测试。 |
| 图片失败不丢文字、独立告知；失败/停止保文 | 完整实现：`execution.py:88`–`:107` 收取异常及逐图隔离，`runner.py:158` 异常尾读；本轮 runner→DB/API 失败/取消/崩溃/图片保存失败专项通过。 |
| 仅成功本轮最终引用、有效图片与归属/历史校验、不扫描发现交付 | 匹配：`delivery.py:114` 成功 final 门禁、`:91` 引用解析、`:132` `_local_file`/字节校验；`execution.py:37` baseline 只排历史。无引用、代码/裸路径、跨会话/inputs/Skill、坏图混合本轮通过。 |
| 临时/草稿/非交付不显示不归档，无候选区；正文同门禁 | **部分实现/HIGH**：`delivery.py:49` 对 image 取原始 content，见 S1-01；没有额外候选区。 |
| 预览、引用修改、SKU 归档保留 | 功能存在但受 S1-01 污染：`StudioTurns.vue:14` 预览、`:15` 引用，`use-studio.ts:102` 添加引用，`service.py:93` SKU/重复/归档保护；归档保存专项通过。 |
| 新会话确认/分界/成功清草稿，桌面与 390px、真实引导 | 匹配所提供 UI 证据：`OverseasStudio.vue:20` 确认、`StudioTurns.vue:5`/`:19` 分界、`use-studio.ts:76` 成功清空。本轮目视 `output/playwright/studio-native/running-markdown.png` 与 `mobile-confirm.png`：运行消息/代码/临时路径纯文字可见，390px 确认按钮在界内；没有实时邻居比较。 |
| 0.2.31 图需不限扩展/北京时间/真实 Skill 名描述保持 | 匹配变更边界：图需上传、时间公共实现和包无本轮改动；`OverseasStudio.vue:14` 保留 Skill 选择器；提供旧刷新/Skill 浏览器 PASS。工作台附件限制不等于图需上传规则。 |
| 海外0014→0015、旧回复/历史保留，国内0028不变 | 匹配源码与提供 PG 证据：`backend/migrations/overseas/versions/0015_studio_transcript.py:10` 增量迁移，`:48` 幂等回填，`:56` 禁降级；迁移/真实 PG 日志已读，实际生产迁移尚未进行。 |
| 0.2.32，同一安装测试镜像给 API/migrate | 匹配实现：`scripts/release/native-studio-runtime.py:12` 版本，`:37` 两服务同 image identity，`:80` 迁移前重核；提供发布专项通过。实际安装测试待审查通过后的发布阶段。 |
| 关闭接纳、双排空、完整备份、迁移切换 | 匹配实现：`native-studio-deploy.py:50` 关入口/停止API、排空、COMPLETE 备份后迁移；提供发布专项 73 passed。本 reviewer 未生产执行。 |
| 失败关入口，仅前进恢复，不降库/重放 | 匹配实现：`native-studio-deploy.py:20` 禁重放，`:37` 恢复边界，`native-studio-runtime.py:118` 失败关入口/记录实际 schema；提供故障路径发布测试通过。 |
| 国内/身份服务不动、14 Skill 181文件不动、不发生产付费调用 | 匹配本次代码边界：`native-studio-deploy.py:69` 仅海外切换、`:98` 资源不变验证，`native-studio-runtime.py:111` Skill 校验。本轮无生产操作；最终现场验证仍待发布。 |

未实现：未发现新增的整项缺失；图片门禁为部分实现且阻断。Spec 漂移：`studio/models.py:64` Transcript、`router.py:33` 新会话和 `:38` 增量 API 均对应需求；未发现新增无依据页面/候选区。提交、安装、生产迁移/切换与入口验收尚未完成，不能称交付完成。

## 测试与编译证据

本 reviewer 独立执行，退出码 0，原始输出：

```text
.venv/Scripts/python.exe -m pytest -q tests/test_studio_formal_delivery.py tests/test_overseas_studio_transcript.py tests/test_overseas_studio_conversations.py tests/test_overseas_studio_execution.py
........................................................................ [ 52%]
..................................................................       [100%]
138 passed, 2 warnings in 9.81s
```

warning 为 Starlette/httpx 和 anyio BlockingPortal 弃用。138 项通过不能覆盖 S1-01。

已读取的主 Agent 原始日志摘录（不是 reviewer 重跑）：

```text
# output/native-studio-backend-pg-20261014.log
66 passed, 2 warnings in 48.13s
# output/native-studio-frontend-tests.log
ℹ tests 356
ℹ pass 356
ℹ fail 0
ℹ skipped 0
# output/native-studio-frontend-final-typecheck.log
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
> hengxin-smart-image-frontend@0.2.32 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
# output/native-studio-build.log
✓ built in 37.70s
# output/native-studio-browser.log
PASS: incremental pages/updates, full messages/long text, safe Markdown and delivery images, failure/cancel/reload, scroll follow/history, draft selection persistence, idempotent new conversation, 390px
# output/native-studio-refresh-browser.log
PASS: idle/active/completed polling, manual spinner, silent auto refresh, error recovery, draft/attachment/skill/scroll persistence; full descriptions desktop/mobile
# output/native-studio-release-tests.log
Result: 73 passed, 26 subtests passed in 3.01s
Exit code: 0
Result: 1 failed, 242 passed, 1 skipped, 117 subtests passed in 13.78s
Exit code: 1
```

主 Agent 报告 typecheck/build exit 0，所读日志无编译错误。发布全目录失败为 `scripts/release/test_release_native.py:100` 旧 overlay 顺序断言，日志指出 HEAD 已以 materials 结尾，两文件本轮未改；保留失败，不宣称全绿。

报告落盘前 `output/native-studio-backend-full-r5.log` 仍在 61%，尚无最终摘要且未收到最终通知，**R5 整库不记已通过**。前轮全量结果不替代本轮。生产空任务状态来自主 Agent，本 reviewer 未实查；有数据工作台证据来自隔离浏览器，不冒充生产会话现场验证。

## Stage 2

**未执行**。按 skill，Stage 1 有 HIGH 必须停止；不提供质量、全面安全扫描、测试真实性全审及实时邻居页面视觉比较 PASS。源码功能阅读、提供截图、专项测试不替代 Stage 2。主 Agent 按 Stage 1 失败修复后重新 prepare/独立审查。本报告不得用于 review-approve，未写 `.needs-review`。
