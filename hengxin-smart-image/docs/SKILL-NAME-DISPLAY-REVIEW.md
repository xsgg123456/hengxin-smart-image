# Skill 名称播报增量独立审查

- 审查日期：2026-09-17。
- 最终 candidateId：`79892f0418655e7a45b90dc1794920cac38ef0c79d962b4884cf499769c0532e`。
- **Stage 1：PASS；Stage 2：PASS。** 当前范围无未解决 HIGH/MEDIUM 问题。
- 初次候选：`3c409c43e2b587d131fe4d999848759b7ec8008ec700afe04b0c92b844a7bd9c`。初审发现合法尾连字符名称被隐藏，主 Agent 修复并重新固定候选；本报告重新从 Stage 1 核验最终候选，不把旧结论覆盖新版本。
- 基线：已批准的 `59d22f5a86e4d5cde79d48205c0c2765552296f38fdb2a231c7588b30b3304bb`，原报告 `docs/FINAL-REPLY-DELIVERY-CLOSEOUT-REVIEW.md`。生产文件实际比较 `output/deploy/final-reply-20260917-59d22f5/backend/app/execution/`，不以 HEAD 累积差异代替本次增量。
- 范围：`backend/app/execution/public_messages.py`、`backend/app/execution/observation.py`、`backend/tests/test_public_messages.py`、`backend/tests/test_observation.py`。`review-status` 确认与已批准快照的变化恰为这四个文件。
- 依据：根目录 `Product-Spec.md:273`、`:274`、`:275`，`.agents/skills/code-review/SKILL.md` 与 `docs/HARNESS-REVIEW.md`。这是当前播报变更的增量审查，不重新验收全产品或历史阶段。

以下代码路径以 `hengxin-smart-image/` 为前缀，根目录 Spec 除外。

## Stage 1：Spec Compliance

| 当前范围要求 | 结论与证据 |
|---|---|
| 保留本轮绑定名称，普通文本、`名称`、`$名称` 均可显示，名称超过 32 字符不隐藏 | 完整实现。`backend/app/execution/public_messages.py:32` 精确放行两种行内代码写法并移除反引号，`:40` 对完整长标识执行精确相等检查。`backend/tests/test_public_messages.py:72` 的三名称 × 四种写法覆盖两个实际生产名称与尾连字符名称，共 12 个参数化用例，独立运行通过。 |
| 白名单仅来自已准备的实际任务绑定，不采信模型声明 | 完整实现。`backend/app/execution/materials.py:65` 根据任务绑定版本读取 Skill，`:69` 设置 workspace 名称；`backend/app/execution/public_messages.py:13` 校验名称格式，未从事件文本解析白名单。`backend/tests/test_public_messages.py:83` 验证相似长标识、无绑定及非法绑定不获豁免。 |
| Observer 初始化早于素材准备，也要读到正确绑定 | 完整实现。`backend/app/execution/codex_runner.py:104` 创建 Observer，`:109` 准备素材，`:130` 监视回调以及 `:152` 最后强制 tick；`backend/app/execution/observation.py:124` 每次读取当前 workspace.skill_name，`:52` 传入过滤器，没有在构造时缓存默认名称。`backend/tests/test_observation.py:142` 在 Observer 创建后设置名称，走事件文件、tick、数据库、HTTP API，独立验证名称完整展示。 |
| 其他长标识、路径和凭证继续过滤 | 完整实现。`backend/app/execution/public_messages.py:26` 和 `:45` 保留脱敏前后凭证标记整条拒绝，`:36` 至 `:39` 先过滤链接和路径，`:40` 仅豁免完全匹配项。`backend/tests/test_public_messages.py:83` 验证前后缀、其他长标识、路径、链接、代码块、明文及 HTML 拆分凭证；原路径、控制字符、凭证测试也通过。Skill 豁免没有凌驾于既有凭证、代码块及限长策略。 |
| 只公开完成的 agent_message；不公开 reasoning、命令或工具原始输出 | 完整实现。`backend/app/execution/public_messages.py:15` 至 `:22` 约束事件类型和数据形状；`backend/app/execution/observation.py:59` 至 `:64` 工具事件仅显示固定活动文案。`backend/tests/test_public_messages.py:10`、`:15` 与 `backend/tests/test_observation.py:20`、`:105` 独立通过。 |
| 纯文本、限长、归属 Codex；播报不能直接标成功 | 完整实现。`backend/app/execution/public_messages.py:23` 至 `:47` 保留现有过滤和 800 字符上限，添加 Codex 前缀；`backend/app/execution/observation.py:95` 仅保存观察数据。`backend/tests/test_public_messages.py:55`、`:67` 及 `backend/tests/test_observation.py:120`、`:152` 验证内容过滤、长度与非 completed 状态。 |
| 不按绑定名称猜测回填历史已脱敏记录 | 完整实现。变更只在 `backend/app/execution/observation.py:52`、`:124` 读取新增 CLI 事件时传递绑定；`:95` 至 `:108` 写入当前受认领约束的 attempt。四文件差异没有历史记录修复、遍历或占位符反向替换。`backend/tests/test_observation.py:129` 历史事件不伪造用例通过。 |
| UI、引导真实性与 Spec 漂移 | 本次无新增页面、组件、API 或数据表，改动只有既有播报内容过滤与参数传递。`backend/app/execution/public_messages.py:32`、`:40` 和 `backend/app/execution/observation.py:124` 均对应新增 Spec；不存在新增操作提示或死引导。本次没有 UI 样式调整，设计数值比较不适用。 |

部分实现：无。未实现：无。上述通过仅适用于当前增量，不表示线上真实生成或视觉效果已验收。

### 初次发现与修复复核

初次候选存在 **MEDIUM**：`backend/app/execution/public_messages.py:40` 使用末尾单词边界，合法绑定 `jd-main-image-wallpaper-camera-swap-` 的尾部连字符不在匹配内，导致精确比较失败，三种写法均输出 `[标识已省略]-`。`backend/app/contracts/management.py:159` 和 `backend/app/execution/materials.py:69` 均接受此名称，属于可达输入。

最终候选 `public_messages.py:40` 改为完整标识字符集的前后断言；`backend/tests/test_public_messages.py:74` 补充尾连字符名称。独立构造 `SkillRegisterInput(name=..., mode='wallpaper', version='1.0.0')` 并调用过滤器复核：

```text
registration_accepted=True
{"input": "Use jd-main-image-wallpaper-camera-swap-", "output": "Codex\uff1aUse jd-main-image-wallpaper-camera-swap-", "bound_name_preserved": true}
{"input": "Use `jd-main-image-wallpaper-camera-swap-`", "output": "Codex\uff1aUse jd-main-image-wallpaper-camera-swap-", "bound_name_preserved": true}
{"input": "Use `$jd-main-image-wallpaper-camera-swap-`", "output": "Codex\uff1aUse $jd-main-image-wallpaper-camera-swap-", "bound_name_preserved": true}
```

## Stage 2：Code Quality

| 项目 | 结论与证据 |
|---|---|
| 结构、命名、类型与大小 | 通过。`backend/app/execution/public_messages.py:11` 沿用过滤函数职责，新增可选绑定参数；`backend/app/execution/observation.py:29` 与 `:124` 显式传递，没有全局可变白名单或额外持久状态。生产文件 47/141 行，测试文件 96/199 行，均不超过 300 行；无新增 any、动态执行、外部依赖。 |
| 错误处理 | 通过。`backend/app/execution/public_messages.py:13` 非字符串或非法绑定回退原过滤；`:15` 至 `:22` 拒绝畸形事件；`backend/app/execution/observation.py:113` 保留观察故障不打断执行。`backend/tests/test_public_messages.py:15`、`:95` 与 `backend/tests/test_observation.py:96` 通过。 |
| 测试真实性 | 通过。`backend/tests/test_observation.py:142` 使用真实 Workspace，按照生产顺序先创建 Observer 再设置名称，通过文件事件读取、数据库保存和 HTTP `/execution` 获取；不是只测纯函数。`:105` 覆盖脱敏和状态隔离，`:60` 覆盖失去认领权。另独立运行 `backend/tests/test_codex_runner.py` 12 项生产 runner 回归。 |
| 安全扫描与边界 | 通过。对两个生产文件扫描 eval、exec、innerHTML、dangerouslySetInnerHTML、VITE KEY/SECRET/TOKEN、硬编码密钥前缀和 password 赋值，无命中。`backend/app/execution/public_messages.py:13` 限制白名单格式和长度，`:33` 与 `:41` 只作字符串相等比较；路径/链接及凭证仍先过滤，没有新增文件读取、命令执行、SQL 或凭据发布入口。 |
| 视觉对比 | 不适用。四文件范围为后端过滤、观察和测试，无新增或调整页面。未打开浏览器，不把静态代码审查称为实际页面视觉验证。 |

## 独立验证原始输出

工作目录：`hengxin-smart-image/backend`。未安装依赖、修改业务代码、测试、Skill 或提示词。

```text
$ .venv/Scripts/python.exe -m pytest tests/test_public_messages.py tests/test_observation.py tests/test_codex_runner.py -q
..................................................................       [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
66 passed, 2 warnings in 3.80s
```

编译命令与原始输出：

```text
$ .venv/Scripts/python.exe -m compileall -q app/execution/public_messages.py app/execution/observation.py tests/test_public_messages.py tests/test_observation.py
stdout: （空）
stderr: （空）
exit_code: 0
```

首次误指定不存在的 `tests/test_execution_runner.py` 导致未运行测试，随后修正为真实文件 `tests/test_codex_runner.py`；该首次失败未当作验证通过。两条最终 warning 为现有依赖弃用提示。

最终读取 `review-status` 的 currentId 为上述最终候选；审查中首次代码变化已明确记录并按新候选重审。本 reviewer 只新增本报告，没有写 clean、批准凭据、提交或部署。主 Agent 可为最终候选登记两阶段 PASS，并在登记及交付前再次核对快照。
