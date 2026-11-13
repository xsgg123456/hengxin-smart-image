# Codex Fast 增量审查 · 2026-11-13

- candidateId：`663e4b1625f26a11ace2eb8b1a8b737e9a7621d58ff63d0a87792687b1a89eaf`
- 范围：本次 10 文件、49 行新增/3 行删除；三个业务启动入口、三个测试文件、版本号及 Spec/CHANGELOG/DEV-PLAN 的 Fast 条目。不是历史全产品重新验收。
- Stage 1：PASS。Stage 2：PASS。无本次阻塞问题。
- 审查前后 `review-status` 的 currentId 均等于上述 candidateId；未修改实现、未提交、未写 clean。主 Agent 应用同一 candidateId 登记批准。

## Stage 1 · Spec Compliance

依据 `Product-Spec.md:1`、`Product-Spec.md:3`，逐项核对本次条目：

| 条目 | 结论与证据 |
| --- | --- |
| 国内五工作台统一 Fast | 完整实现。`hengxin-smart-image/backend/app/modules/domestic_studio/runner.py:124` 在公共运行入口传入两个固定配置；`:127` 首轮/续聊分支均在配置之后。 |
| API 图片 CLI 修改统一 Fast | 完整实现。`hengxin-smart-image/backend/app/modules/api_image_edits/conversation_runner.py:156` 设置顶层配置；`:158` 保留首轮/续聊参数。 |
| 国外设计与旧协议统一 Fast | 完整实现。`hengxin-smart-image/backend/app/overseas/execution/runner.py:104` 先取协议参数，再于 `:106` 统一前置配置；覆盖有/无 arguments 的 handler。 |
| 首轮、续聊和重新启动适用 | 完整实现。上述三个入口每次构造 argv 时无条件设置；配置均处于 exec/resume 前，续聊仍带原 session。国外原续聊生成器见 `hengxin-smart-image/backend/app/overseas/studio/execution.py:61`。 |
| 保留模型、思考强度 | 完整实现。国内 runner `:125`、API conversation_runner `:160` 和国外 studio/execution.py `:62` 原模型及 high 参数不变；旧协议也未追加模型覆盖。 |
| 不传 1.5、不承诺固定耗时 | 匹配。三处只追加 `service_tier="priority"`、`features.fast_mode=true`，无速度数值或耗时承诺。 |
| 保留 Skill、上下文、沙箱、状态及重试 | 匹配。三个运行文件的完整 diff 仅变动 argv 配置，分别在 `runner.py:124`、`conversation_runner.py:156`、`overseas/execution/runner.py:106`；未改周边控制流程。 |
| 无新增 UI、依赖、迁移；排除诊断 | 匹配。前端仅 `hengxin-smart-image/frontend/package.json:3` 版本更新；全库 sandbox_command 调用检索发现其余调用为账号 probe/runtime_check/skill_probe，未见遗漏的业务执行入口。无 UI 引导变更，设计稿与邻居视觉比较不适用。 |
| CLI 支持与三个入口验收 | 匹配。`output/codex-fast-support.jsonl:2` 保存 priority 配置 exit_code=0、fast_mode=true；`:3`、`:4` 两组模型缓存均将 priority 命名为 Fast。三个入口测试证据如下。 |
| 分组排空、发布、失败回退 | 发布阶段待主 Agent 执行，非本次代码审查已完成事项。`DEV-PLAN.md:4` 明确后续流程；本报告不宣称已部署或已验证生产效果。 |

完整实现：以上代码条目。部分实现/未实现：无。Spec 漂移：无新增页面、API、数据表或共享配置。

参数语义交叉核对：[官方 Codex Speed](https://learn.chatgpt.com/docs/agent-configuration/speed) 说明 Fast 配置及 feature flag；[官方 Fast mode](https://developers.openai.com/api/docs/guides/fast-mode) 说明 priority 与 fast 对支持模型行为相同。结合本项目 CLI 与模型缓存证据确认选用 priority，不推断实际请求必然达到固定速度。

## Stage 2 · Code Quality

- 代码质量 PASS：三处均用常量 argv 列表，不引入动态命令拼接或额外控制流；三个生产文件分别 151、216、205 行。证据为上述三个配置位置及下方编译输出。
- 测试真实性 PASS：`hengxin-smart-image/backend/tests/test_domestic_runner_pg.py:40`、`tests/test_api_cli_conversation.py:55` 在真实 runner 到 execute 的边界断言 Fast 和原模型参数；API 新会话/续聊用例在 `tests/test_api_cli_conversation.py:111`，实际验证 resume/session 参数。`tests/test_overseas_runner.py:79` 参数化覆盖旧协议、Studio 首轮和续聊，使用真实 StudioProtocol.arguments。国内续聊配置继承由共同前缀的代码路径证明，本次国内测试未新增专门续聊用例。
- 安全 PASS：新增行没有密钥、eval、SQL 拼接或用户输入插值。对三处生产文件执行危险模式扫描未返回匹配；既有 sandbox_command 接收参数列表，见 `hengxin-smart-image/backend/app/execution/workspace.py:58`。无共享服务/数据库依赖变更。
- UI/视觉：不适用。唯一前端变动为 `hengxin-smart-image/frontend/package.json:3` 版本号，无渲染代码差异。

## 验证证据与边界

读取主 Agent 提供的 `output/codex-fast-tests.log`，原始 pytest 结果：

```text
.......................................                                  [100%]
39 passed, 1 warning in 35.97s
```

该日志来自本地 WSL 隔离测试，覆盖 test_domestic_runner_pg.py、test_api_cli_conversation.py、test_overseas_runner.py、test_studio_model_selection.py；本 reviewer 没有连接生产或执行生产测试。日志存在 WSL 提示编码混杂，未显示 warning 详细正文；不将此日志解释为远端模型速度验收。

reviewer 对六个变更 Python 文件逐一执行内存 compile，退出码 0，原始输出：

```text
PASS hengxin-smart-image/backend/app/modules/domestic_studio/runner.py (151 lines)
PASS hengxin-smart-image/backend/app/modules/api_image_edits/conversation_runner.py (216 lines)
PASS hengxin-smart-image/backend/app/overseas/execution/runner.py (205 lines)
PASS hengxin-smart-image/backend/tests/test_domestic_runner_pg.py (171 lines)
PASS hengxin-smart-image/backend/tests/test_api_cli_conversation.py (278 lines)
PASS hengxin-smart-image/backend/tests/test_overseas_runner.py (282 lines)
```

未执行前端完整构建：本次仅更新版本字符串，构建及部署核验属于后续发布验收。两阶段 PASS 仅批准本快照代码增量，不替代发布记录。
