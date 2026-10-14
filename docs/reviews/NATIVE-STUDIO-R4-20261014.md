# 原生工作台独立审查 R4（2026-10-14）

- candidateId：`9bbf15b0ee82e2efc25e1dcde5935d2f9c371c7d95d0323e94a57fcbc44a62db`。
- **Stage 1：FAIL（1 项 HIGH）；Stage 2：未执行。不得登记两阶段 PASS。**
- 范围：本次海外 studio、公共海外 execution/runner、db、任务清理、0015 迁移与测试；前端 API、studio、Markdown、轮询、版本依赖与测试；native-studio 发布、runtime、package-overseas 与测试。非全产品历史需求重审。
- 依据：AGENTS.md、`.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、`Product-Spec.md:1100` 原生工作台章节、DEV-PLAN.md 最后迭代及 `docs/NATIVE-STUDIO-RELEASE-20261014.md:3`。先读原文，再检查实现和证据；前三轮报告只作缺陷历史。
- 开始及报告落盘后的 review-status 核对同一候选。主 Agent 在收到阻断后确认源码保持冻结；本 reviewer 只增加报告，未修改实现、提交、部署、批准或调用付费模型。

## Stage 1：阻断问题

### HIGH S1-01：Markdown 强调使英文否定交付失效，明确非最终图片仍进入正式交付集合

需求原文：`Product-Spec.md:1106` 要求“临时图、草稿、试验图、中间文件不显示、不归档”，“Markdown正文中的图片也遵守同一交付门禁”。本次确认的否定正式交付排除不能因为文字加粗而改变。

位置：`hengxin-smart-image/backend/app/overseas/studio/delivery.py:24`、`:32`、`:61`、`:62`。

`negative` 使用仍含 Markdown 标记的 `token.content` 匹配；英文 DECLINED 只允许词间空白/连字符，不能跨越 `**`。与此同时 `formal_prose()` 读取已解析的 text 子 token，可识别去掉强调标记后的 `final images`。相同可见句子的否定与肯定在不同文本表示上判断，导致明确否定变为肯定。

**独立复现**：TemporaryDirectory 中创建本轮 work/home 和 `.codex/generated_images/session`，Pillow 写入真实 12×13 PNG；直接调用生产 `collect_delivery()`，summary 为 `turn_completed=True, error=None, session_id='session'`，baseline 为空。本轮文件真实、归属有效、最终消息成功；未伪造非法路径或损坏图片。原始输出（退出码 0）：

```text
'These are **not** final images.\n\n![Image](/work/image.png)' accepted= ['/work/image.png'] warnings= []
'These are not **final images**.\n\n![Image](/work/image.png)' accepted= ['/work/image.png'] warnings= []
'These are not final images.\n\n![Image](/work/image.png)' accepted= [] warnings= []
'## Formal delivery\nThese are **not** final images.\n\n![Image](/work/image.png)' accepted= ['/work/image.png'] warnings= []
```

正常的 Markdown 强调是原生回复可达输入，不是攻击性构造。`execution.py:89` 收取后于 `:103` 存储、`:120` 创建 Picture；`queries.py:51` 进入 DTO；前端 `studio-markdown.ts:42` 为 sourcePath 提供授权图片映射，`StudioTurns.vue:12` 提供选中，`service.py:93` 允许归档。因此错误分类会实际成为可显示、可归档图片，而非仅正则内部的无影响差异。

**修复验收**：否定与肯定应使用语义一致的 Markdown 可见文字表示，保持图片/文件名/代码不能声明正式范围的约束，不能靠继续追加某几个原始字符串规避。覆盖强调、加粗、换行与行内链接等常见结构中的否定，以及前置/后置/父标题作用域；保留独立肯定正式交付对照。增加真实 collector 和 runner→API 回归，断言原文保留且无 Picture。重新固定快照并从 Stage 1 审查。

R1–R3 的已知反例在本轮 102 项专项中通过，R4 新增测试也通过；这不覆盖上述 Markdown 结构等价性反例。当前不能批准。

## Stage 1：逐项对应

下表 backend/、frontend/ 均相对 `hengxin-smart-image/`；“匹配”只限所列实现和验证，不代表整个 Stage 1 通过。提供的日志均已读取，未冒充 reviewer 重新执行。

| 需求 | 结论和证据 |
|---|---|
| 普通消息原样、每新会话首次一句人设 | 匹配：`backend/app/overseas/studio/execution.py:62` 仅无 previous_session 时加指定句，`:64` 追加原文；`backend/tests/test_overseas_studio_conversations.py:37` 捕获真实 worker 首轮/续轮精确 prompt，本轮通过。 |
| 仅主动附件/Skill引用，不加商品背景/步骤/数量/格式，不改 Skill | 匹配：`studio/service.py:51`、`:60` 仅显式输入；`execution.py:65`、`:67` 条件添加路径。快照变更无 Skill 包文件，发布 `native-studio-runtime.py:70` 只验证包。 |
| 原 CLI 权限、上下文隔离 | 匹配：`execution.py:19` 每 conversation 独立 home，`:40` workspace-write；`transcript.py:90` claim、lease、task/turn/conversation 验证；本轮错 session/claim 和撤权读取用例通过。 |
| 完整公开消息、顺序与更新持久化 | 匹配：`transcript.py:15` 公共白名单，`:41` 追加文本快照；`queries.py:92` ID 顺序；`frontend/.../studio-transcript.ts:4` 按 turn/item 原位更新；长文、多个消息、末尾 UTF-8 专项通过。 |
| 公开摘要/工具状态，不输出隐藏推理和任意工具输出 | 匹配：`transcript.py:31` 仅公开 reasoning.text，`:36` 工具固定标签；`test_overseas_studio_transcript.py:42` SECRET/PRIVATE 字段不进入 API，本轮通过。 |
| Markdown代码、链接完整；HTML不执行，图片/下载授权 | 匹配但受 S1-01 分类污染：`frontend/.../studio-markdown.ts:4` html:false、`:13` 图片映射、`:18` 未批准本地链接为文字；`frontend/src/api/overseas/studio.ts:33` 精确任务/图片路径校验。已看运行态截图，代码、链接和 HTML 字面文字可见。 |
| 1秒级事件、分页/重连去重和尾部补齐 | 匹配：`transcript.py:54` 字节游标/半行，`runner.py:129` final_poll，`queries.py:92` 500+1，`use-studio.ts:34` 1000ms、`:42` 连续页；502条/半行/重复读取专项通过。 |
| 过程默认展开、终态折叠 | 匹配：`StudioTranscript.vue:4` open=running，`StudioTurns.vue:30` 状态集合；运行态截图已目视，提供浏览器日志及 `tests/studio-native.browser.mjs:99` 终态关闭断言。 |
| 历史滚动不跳底、底部跟随 | 匹配：`StudioTurns.vue:37`–`:41` 更新前读位置、更新后跟随；`tests/studio-native.browser.mjs:74`、`:83` scrollTop/底部距离实际断言；提供日志 PASS，本轮未重跑浏览器。 |
| 隐藏/卸载停请求，返回补齐 | 匹配：`use-studio.ts:34` 可见性调度、`:62` abort/恢复、`:105` 卸载取消；提供刷新浏览器和前端回归通过。 |
| 失败/停止保留公开文字 | 匹配：`runner.py:158` 异常尾读，`transcript.py:49` 独立 reply；`test_overseas_studio_transcript.py:96` failure/cancel/crash 实际 runner→DB/API，本轮通过。 |
| 图片无效/收取失败不丢文字、独立警告 | 匹配：`execution.py:88` 收取异常、`:93` 逐图隔离、`:107` reply 独立返回；`test_overseas_studio_transcript.py:125` 失败保文及 collector 坏图混合，本轮通过。 |
| 仅当前成功最终引用、不扫描发现图片 | 匹配：`delivery.py:103` 成功 final 门禁，`:80` Markdown 引用；`execution.py:37` baseline 仅历史排除；无引用、失败/未完成、代码/裸路径专项通过。 |
| 图片真实、所有权/历史隔离、去重 | 匹配：`delivery.py:118` 调用 `_local_file`，`:123` 真实字节/图片验证；`backend/app/execution/final_delivery.py:45` 跨目录、inputs/Skill/跨会话/历史/硬链接约束；本轮专项通过。 |
| 非交付图片不显示/归档，Markdown同门禁，无候选区 | **部分实现，HIGH**：`delivery.py:61` 否定与肯定解析不一致，见 S1-01。未发现候选区代码；下游图片集合被污染，无法算匹配。 |
| 新对话清上下文，保留旧对话、材料、图片、归档 | 匹配：`service.py:73` 仅新建 Conversation，`queries.py:63` 读全历史；`test_overseas_studio_conversations.py:16` 新 home、材料历史保留，`:57` 多会话删除与归档兼容，本轮通过。 |
| 在途/uncertain禁止，新会话并发/幂等 | 匹配：`service.py:16` 锁与幂等，`:26` 非TERMINAL阻止；`use-studio.ts:14` pending锁、`:79` 未知响应保留同key。已读真实PG并发 `test_overseas_studio_postgres.py:15`、`:33`，提供66 passed、0 skip。 |
| 新对话确认、分界、成功清草稿/选项 | 匹配：`OverseasStudio.vue:20` 确认，`StudioTurns.vue:5`、`:19` 分界，`use-studio.ts:76` 成功后清空；390px确认截图已目视，提供浏览器失败/重试同key及原文发送断言通过。 |
| 预览、引用修改、SKU归档保留 | 匹配但受 S1-01 影响：`StudioTurns.vue:14` 预览、`:15` 引用，`use-studio.ts:102` 添加引用；`service.py:93` SKU、重复、归档保护；本轮归档保留专项通过。 |
| 0.2.31上传不限扩展名/北京时间/真实Skill描述/静默刷新保持 | 匹配（变更边界与提供回归）：图需上传、公共时间和 Skill 包无本次差异；`OverseasStudio.vue:14` 仍复用Skill选择器，`use-studio.ts:53` 手动loading/自动刷新分离；356前端测试及旧刷新/Skill浏览器PASS。工作台附件限制与图需上传不同，未混同。 |
| 桌面/390px及真实引导 | 已核对所提供实际截图：运行态代码/公开消息/临时路径纯文字、窄屏确认框和按钮在界内；`OverseasStudio.vue:5`、`:13`、`:20` 控件连接实现，`studio.css:13` 保持已有间距/变量。Stage 2 新旧邻居实时对比未执行。 |
| 海外0014→0015、保留旧会话/回复，国内0028不变 | 匹配：`migrations/overseas/versions/0015_studio_transcript.py:10` 加列/表及去任务唯一约束，`:48` 去重回填，`:56` 禁降级；已读 `test_overseas_studio_migration.py:16` 历史逐列/重复升级/国内快照验证，提供PG日志通过。 |
| 0.2.32，同一已安装测试镜像用于API/迁移 | 匹配源码/提供测试：`scripts/release/native-studio-runtime.py:12` 版本/schema，`:37` 两服务image identity，`:80` 迁移前重核；实际安装仍待审查后发布。 |
| 关接纳/双排空/完整备份/迁移切换；失败关入口、只前进、不重放 | 匹配源码/提供测试：`native-studio-deploy.py:20` 拒重放，`:50` 关入口后排空/backup COMPLETE后迁移；`native-studio-runtime.py:118` 故障关入口并记录实际schema；提供重点发布73 passed。尚未生产执行。 |
| 国内/身份服务不重启、14Skill181文件不改、生产不付费调用 | 匹配本次实现范围：`native-studio-deploy.py:69` 仅海外切换，`:98` 资源不变检查；`native-studio-runtime.py:70`、`:111` 验证Skill。没有 reviewer 生产操作；实际发布后的最终核对仍待完成。 |

未实现：没有额外确认的整项缺失；正式交付分类为部分实现且阻断。Spec 漂移：未发现额外无需求页面、API或候选区；`studio/models.py:64` Transcript、`router.py:33` 新会话和 `:38` 增量API对应本次需求。提交、安装测试、生产切换和真实入口验收是后续阶段，不能称已完成。

## 验证与编译原始输出

本 reviewer 独立执行，退出码 0：

```text
.venv/Scripts/python.exe -m pytest -q tests/test_studio_formal_delivery.py tests/test_overseas_studio_transcript.py tests/test_overseas_studio_conversations.py tests/test_overseas_studio_execution.py
........................................................................ [ 70%]
..............................                                           [100%]
102 passed, 2 warnings in 9.34s
```

两项 warning 为 Starlette/httpx 与 anyio BlockingPortal 弃用。102项通过不覆盖 S1-01 的独立反例。

已读取的主 Agent 证据摘录（不是本 reviewer 重跑）：

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

主 Agent 报告 typecheck/build exit 0，已读日志无编译错误。发布全目录 `scripts/release/test_release_native.py:100` 旧overlay末项断言失败；提供日志说明HEAD/current已以materials而非annotation结尾，两文件未改。如实保留失败，不称全绿。

报告写入时 R4 整库 `output/native-studio-backend-full-r4.log` 尚无最终摘要，未收到主 Agent 最终结果通知，**不标记最终整库回归完成**。后续通过也不能消除此 HIGH。

生产当前无测试任务的只读情况来自主 Agent，本 reviewer 未实查。后续可验证生产真实入口/空列表/权限；带数据工作台和新会话只能使用隔离浏览器证据，不得冒充生产真实会话现场验证。

## Stage 2

**未执行**：code-review skill 明确要求 Stage 1 出现 HIGH 即停止。本轮没有出具质量、全面安全扫描、测试真实性全审或打开邻居页面实际渲染比较的 PASS；源码阅读与已提供截图不替代这些检查。

按 Stage 1 失败交主 Agent 修复；新快照由 fresh reviewer 重审。本报告不用于 review-approve，未写 `.needs-review`。
