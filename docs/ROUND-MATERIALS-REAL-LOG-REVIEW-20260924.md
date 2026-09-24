# 真实 CLI 日志兼容增量独立审查（2026-09-24）

- candidateId：`30176f8f46b4e4a112b05ea81624f34f6fbe8bfbe72177bbc775744070b5de9e`。
- 批准基线：`2771bb95df27365459c36c64909f55ee33ae38713537bb34ab8991284701c477`，见 `docs/ROUND-MATERIALS-RELEASE-REVIEW-20260924.md:1`；完整功能证据沿用 `docs/ROUND-MATERIALS-CANVAS-FINAL-REVIEW-20260924.md:1`。
- **Stage 1 PASS；Stage 2 PASS。增量无未关闭 HIGH / MEDIUM。**
- 按 code-review skill 执行：先核对需求与事件/语法边界，再核对质量、安全及测试。仅审查相对 HEAD 的七个受控文件：两份材料解析模块、两份专项测试、前端 package.json、deploy.sh、frontend.py；同时读取本轮 Spec/CHANGELOG/发布记录。未修改实现、生产操作、提交或登记批准。
- 首尾 review-status 均匹配 candidateId，审查期间未发现代码漂移。生产实录只读验证、修正版安装测试和部署由主 Agent 另行执行，本报告不声称已经上线。

## Stage 1：Spec Compliance

需求依据：`Product-Spec.md:754` 明确兼容两类真实工具事件，保持轮次、时间、字面参数及脱敏边界；`Product-Spec-CHANGELOG.md:453` 和 `hengxin-smart-image/docs/ROUND-MATERIALS-CANVAS-RELEASE-20260924.md:24` 说明受限结果存储/展示尾部和 0.2.7 修正版。

下表 backend 路径前缀为 `hengxin-smart-image/backend/`。

| 条目 | 结论及证据 |
| --- | --- |
| custom_tool_call/input 和 function_call/arguments | 完整实现。`app/execution/material_history.py:75` 至 `:83` 按事件类型选唯一字段，仅 response_item、明确工具名和字符串参数进入解析。`tests/test_round_materials.py:42` 同一整合场景参数化验证两种格式。 |
| 不读取输出、未知工具或错配字段 | 完整实现。`material_history.py:76`、`:79`、`:87` 过滤；`tests/test_round_materials.py:71` 至 `:88` 四类反例均无 toolCalls。 |
| 轮次、时间、脱敏保持 | 完整实现。`material_history.py:65` 至 `:74` 每文件重置 active、过滤时间、用户消息切换；`:97` 保留 public_text 与 /work 路径过滤。`test_round_materials.py:34` 至 `:59` 实际写入前轮/本轮/后轮 JSONL，两种事件均只产生本轮两次调用，保留长提示词并移除内部路径。 |
| 真实结果存储和元数据展示 | 完整实现。`material_literals.py:92` 至 `:112` 固定 tokens 模式并验证结果和回调变量；`:161` 至 `:170` 仅允许字符串键与本次绑定结果。`test_material_literals.py:83` 至 `:104` 验证真实三张 /work 图片、原文、store 和投影尾部。 |
| 不把任意脚本当已执行调用 | 完整实现。`material_literals.py:122` 拒绝箭头前换行，`:137` 拒绝全局遮蔽/重复声明，`:148` 拒绝同脚本多生图，`:173` 要求显式分号，`:177` 全程序失败则不展示。`test_material_literals.py:10`、`:33`、`:107`、`:135` 覆盖 exit、前置失败、非法尾部、错结果/回调绑定、动态表达式、箭头拆分及注释换行。 |
| 字符串/模板安全 | 完整实现。`material_literals.py:17` 至 `:49` 解码字面量且拒绝动态模板、不合法转义；调用识别使用 tokens 而非字符串搜索，`:116` 至 `:119`。`test_round_materials.py:62`、`:91` 和 `test_material_literals.py:63` 的动态模板、注释与伪调用反例通过。 |
| 0.2.7 与现有生产 overlay | 匹配。`hengxin-smart-image/frontend/package.json:3` 为 0.2.7；`scripts/release/image-inputs-deploy.sh:25` 和 `scripts/release/image-inputs-frontend.py:39` 同步追加 materials-20260924-e3c60c9，保留原链和后续新 overlay。 |

部分实现/未实现：无。Spec 漂移：无新增页面、API、数据表或任意执行能力。引导真实性、UI 一致性：本次没有组件、布局、样式或提示文案增量；前端仅版本变化，沿用功能基线证据，不重复浏览器视觉对比。

## Stage 2：Code Quality、安全和验证

- 结构：`material_literals.py:92` 将固定展示模式独立为函数，解析失败仍统一收敛为空结果；模块共 179 行，history 共 114 行，两测试分别 145/244 行，未超过 300 行。无新增依赖或动态类型 any。
- 安全：新增代码只读取/比较 tokens 和字面量，不执行日志中的 JavaScript；存储语法也仅识别、不调用 store（`material_literals.py:161`）。受审模块/发布脚本扫描未检出 eval、HTML 注入、前端密钥变量、sk-ant/sk-proj 模式。既有 /work 测试路径及 /opt 发布路径是业务路径，不是新增凭据。
- 测试真实性：`test_round_materials.py:46` 转换完整真实风格事件，真实落盘 JSONL 后调用 read_history；不是 mock 返回解析结果。其轮次隔离和脱敏断言对 custom/function 两种格式共同执行。`test_material_literals.py:84` 的真实尾部与交接实录一致；故障测试断言整份脚本无调用而非仅过滤尾部。106 项专项独立通过。
- 视觉对比不适用本增量：package 版本以外前端实现无 diff；未冒充重新视觉验收。生产实录和 Linux 安装验证仍由主 Agent 负责。
- 主 Agent 同步的只读生产实录证据：修正解析器放置于独立 diagnostic 文件，未替换运行代码；根 request 510 字符精确匹配，真实 custom/input 解析出 1 次调用、提示词 2160 字符，图片顺序为 `/work/current/00.png`、`/work/inputs/00.png`、`/work/original/00.jpg`。此项为主 Agent 实查结果，非 reviewer 独立生产操作；进一步证明 `material_history.py:75` 和 `material_literals.py:92` 的兼容目标可达。

## 原始验证输出

独立使用 bundled Python，backend 工作目录、`PYTHONPATH=.venv/Lib/site-packages;.`，运行 `-m pytest tests/test_material_literals.py tests/test_round_materials.py -q --basetemp ../../output/reviewer-real-log-pytest`，exit 0：

```text
........................................................................ [ 67%]
..................................                                       [100%]
106 passed, 3 warnings in 2.38s
```

三条 warning 为既有 Starlette httpx/BlockingPortal 弃用提示及 `.pytest_cache` 写权限提示，未跳过或失败测试。

独立解析三个受审 Python 实现文件、部署 shell 语法检查：

```text
PYTHON_AST_OK 3
BASH_SYNTAX_EXIT=0
```

`git diff --check` exit 0，仅 CRLF 转 LF 提示。已读取主 Agent 构建日志 `output/materials-release-20260924/frontend-027-build.log:4`，未重复构建：

```text
> hengxin-smart-image-frontend@0.2.7 build
> vue-tsc --noEmit && vite build
✓ built in 1m 27s
```

首尾快照关键结果：

```json
{"currentId":"30176f8f46b4e4a112b05ea81624f34f6fbe8bfbe72177bbc775744070b5de9e","reviewedId":"2771bb95df27365459c36c64909f55ee33ae38713537bb34ab8991284701c477","approved":false}
```

主 Agent 可用本报告登记同一 candidateId 的两阶段 PASS；不得用旧报告批准变化后快照，不写 `.needs-review`。
