# CLI 单张成品修改简化审查

最终 candidateId：`daf60c91c556044428d09c1812be98cc6dac9f6d23c346f8430ce75469ea7d48`。

结论：**Stage 1 PASS；Stage 2 PASS**。旧候选发现的 HIGH 已修复并独立复验；最终候选无待修复问题。本结论覆盖仓库实现，不代表生产发布或付费生图效果验收。

范围：根目录 `Product-Spec.md:3`、`DEV-PLAN.md:3`、`Product-Spec-CHANGELOG.md:3` 的本次条目；项目目录 `backend/app/execution/{prompts,materials,workspace}.py` 及五份相关测试 `test_task_prompt.py`、`test_single_revision_prompt.py`、`test_single_revision_materials.py`、`test_revision_execution.py`、`test_execution_workspace.py`。以下代码路径均相对项目目录 `hengxin-smart-image/`。使用 code-review 技能和根目录 `docs/HARNESS-REVIEW.md` 协议。

相对上次批准快照 `90829f4285c9afb9251bc30a6d49c38db98bf83d0c8a98850314e7d31c52e1ff`，受控文件仅上述八份。CLI 升级配置与详情首轮指令沿用 `docs/CODEX-UPGRADE-20260923-REVIEW.md`、`docs/DETAIL-PROMPT-20260923-REVIEW.md` 的既有审查，未将新增单张分支冒认为已审代码。

## 审查中变化与已关闭问题

初始 candidateId `fbf3e2046873b130cc1c4f413c0b087a35ff98596f7c9fd80319101fe53a460f`：Stage 1 FAIL（HIGH），Stage 2 未执行。

问题：文字模式 sources 本身就是原图，`backend/app/modules/tasks/snapshots.py:28` 不产生模板快照。初始 `materials.py:44` 无条件将全部 sources 写入 `/work/inputs`，`workspace.py:91` 将工作目录整体提供给执行器。虽然文字提示词隐藏 inputs，模型工作区仍含整套原图；任一旧原图损坏还会在 `materials.py:55` 读取时阻断成品修改。这与 `Product-Spec.md:5` 的“不传原底图”不匹配。

主 Agent 修复后重新提交最终候选：`materials.py:44` 在文字模式且已有单张基础版本时将 inputs 清空，其他模式及无成品重试保留 sources。新增 `tests/test_single_revision_materials.py:67` 通过真实任务/返工入口创建两张文字原图，破坏两份原对象，再修改第二张成品，验证准备成功且 inputs、targets 目录均为空。独立测试通过，HIGH 关闭。最终候选重新完整检查 Stage 1 后才进入 Stage 2；旧结论不批准新快照。

## Stage 1：Spec Compliance

| 条目 | 结论与证据 |
|---|---|
| 同一个 CLI 会话续接、保留历史 | 完整实现。`codex_runner.py:94` 读取持久会话，`:115` 校验历史文件，`:134` 构造 resume；`workspace.py:31` 保留任务 home。`tests/test_revision_execution.py:48` 通过实际任务和返工接口检查 resume ID、当前文件字节及失败后会话不变。 |
| 指定无标注成品为唯一修改基础，保留历史版本选择 | 完整实现。`materials.py:42`、`:68` 优先冻结 base_version_id，旧轮次才取 current_version_id；`:71` 校验目标归属。`tests/test_single_revision_materials.py:31` 用不同字节的 V1/V2 检查第四位置明确选中 V1，不只检查标签。 |
| 本轮不传原底图 | 完整实现。`materials.py:50` 跳过 targets 读取；`:44` 同时排除文字模式的原 sources。`tests/test_single_revision_materials.py:67`、`:107` 分别覆盖文字多原图和壁纸模板原图损坏，准备仍成功；断言工作目录不存在旧图文件。 |
| 保留原手机屏幕素材，商品/文字语义正确 | 完整实现。`materials.py:44` 在壁纸/商品模式保留原 sources；`prompts.py:9` 按模式分别称手机屏幕参考素材、商品参考素材，文字模式不列参考素材。`tests/test_single_revision_prompt.py:37` 检查商品/文字命名与引用；材料测试 `:107` 检查实际 inputs 文件存在。 |
| 可选标注图、可选意见及固定顺序 | 完整实现。`materials.py:86` 读取冻结标注；`prompts.py:8` 至 `:20` 顺序为成品、素材、标注、意见、单张交付。`:15` 明确标注不进入成品。`tests/test_single_revision_prompt.py:8` 覆盖有图无意见、无图有意见及图文同时存在；材料测试 `:55` 比较标注字节。 |
| 其他保持不变且仅交付一张 | 完整实现。`prompts.py:19` 明确指令；`materials.py:37` 单目标；`codex_runner.py:167` 按 targets 数量收图。`tests/test_single_revision_prompt.py:8` 对完整输出检查。图片模型实际遵从效果未付费验证。 |
| 不读取/挂载首轮 Skill、不重复整套要求 | 完整实现。`materials.py:95` 在 Skill 数据和对象读取前返回；`workspace.py:97` 隐藏本轮 `.agents` 发现目录且不绑定 Skill。`prompts.py:25` 在读取 skillPath 前走简化分支。材料测试 `:107` 同时破坏 ZIP/本地 Skill 并让本地校验函数抛错，仍通过；`tests/test_execution_workspace.py:44` 验证挂载参数不含旧 Skill 且不删除宿主旧目录。 |
| 主图与详情统一规则 | 完整实现。`prompts.py:25` 按单张/currentPath 选择分支，不受 Skill 名称影响；`tests/test_single_revision_prompt.py:8` 参数化四个指定 Skill，并在移除 skillPath、原图 path 后再次验证同一提示词。 |
| 无成品失败重试保留生成逻辑 | 完整实现。冻结空 base 在 `materials.py:42` 不退回后来出现的结果；`:95` 不命中简化返回；`prompts.py:25` 不命中简化提示。材料测试 `:86` 验证显式空基础与旧轮次回退；`tests/test_single_revision_prompt.py:49` 检查失败图仍含 Skill 和底图。 |
| 首轮和整套返工保持 | 完整实现。`materials.py:39` 仅单目标判断基础；`prompts.py:25` 仅 singleRevision 生效。`tests/test_task_prompt.py:35` 覆盖首轮/整套返工、四 Skill 及相似名称、多素材原指令；`:61` 检查整套返工仍引用原图。 |
| UI 一致性、引导真实性 | 不适用。本次受控差异全部在服务端执行文件和测试，没有页面、文案引导或组件变化，不存在新增页面可做邻居渲染比较。 |
| Spec 漂移 | 未发现。`prompts.py:6`、`materials.py:38`、`workspace.py:97` 分别实现本次约定的指令、输入和 Skill 隔离，没有新增 API、表或页面。 |

部分实现、未实现：无。`DEV-PLAN.md:7` 的生产发布与运行健康属于主 Agent 运维步骤，不包含在本次仓库 PASS 内。

## Stage 2：Code Quality

- 质量 PASS：三份实现分别为 59、128、108 行，未超过 300 行；`single_revision_prompt` 和 `use_skill` 表达具体用途，复用原冻结版本校验及持久会话机制。没有新增 any、异常吞噬、外部依赖或命令字符串拼接。原有未注解的函数风格及既有无用导入不作为本次增量问题。
- 测试真实性 PASS：历史选择测试 `test_single_revision_materials.py:31` 比较真实不同字节；`:67` 真正破坏存储原对象，`:107` 破坏原图和 Skill 并阻止 validate_local；真实任务/返工路由被调用。`test_revision_execution.py:48` 走执行编排与持久化，但 CLI 子进程、版本和沙箱由 `test_codex_runner.py:33` 模拟，不能声称测试证明真实 Linux 隔离或生成质量。
- 安全扫描 PASS（本次增量）：对三份实现搜索 eval、exec、HTML 注入、前端密钥、硬编码密码和 shell=True 无命中。`prompts.py:18` 保留 JSON 意见引用；它是格式边界，不宣称阻止所有模型提示注入。`materials.py:18` 保留校验和/大小检查，`:71` 保留版本归属检查；`workspace.py:95` 保留链接检查，新增挂载参数为固定字符串，没有扩大外部路径访问。
- 视觉比较不适用：`workspace.py:97` 等改动没有 UI 渲染，未虚构页面截图证据。生图视觉效果不在本次自动化审查范围。
- 转交证据：主 Agent 报告真实 Linux、codex 用户执行隔离探针输出 `SINGLE_REVISION_SANDBOX_PASS`；reviewer 未独立访问生产，故仅记录为补充信息，不据此声明生产已经发布。

## 独立验证原始输出

在 backend 目录执行 `.venv/Scripts/python.exe -m pytest -q tests/test_single_revision_prompt.py tests/test_single_revision_materials.py tests/test_revision_execution.py tests/test_execution_workspace.py tests/test_task_prompt.py`，退出码 0：

```text
.............................s...............................            [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
60 passed, 1 skipped, 2 warnings in 3.51s
```

跳过项为 `tests/test_execution_workspace.py:65` 的 POSIX 符号链接测试，本机 Windows；两项 warning 来自既有依赖。初次尝试无 PATH python、uv 缓存权限失败，后来使用获准的项目虚拟环境成功运行，不将失败尝试算作产品问题。

编译命令 `.venv/Scripts/python.exe -m compileall -f app/execution/prompts.py app/execution/materials.py app/execution/workspace.py`，退出码 0，原始输出：

```text
Compiling 'app/execution/prompts.py'...
Compiling 'app/execution/materials.py'...
Compiling 'app/execution/workspace.py'...
```

`git diff --check` 未报空白错误，只有两个测试文件 CRLF 转 LF 提示。主 Agent 后续转交最终修复版全后端摘要 `865 passed, 166 skipped, 15 warnings in 50.75s`，并说明 compileall 退出 0，记录于 `docs/SINGLE-REVISION-20260923.md`。这组全量结果非 reviewer 独立执行，不替代上述独立专项证据。

## 快照结论

修复后独立 `review-status` 原始输出：

```json
{"currentId": "daf60c91c556044428d09c1812be98cc6dac9f6d23c346f8430ce75469ea7d48", "reviewedId": "90829f4285c9afb9251bc30a6d49c38db98bf83d0c8a98850314e7d31c52e1ff", "changedFiles": ["hengxin-smart-image/backend/app/execution/materials.py", "hengxin-smart-image/backend/app/execution/prompts.py", "hengxin-smart-image/backend/app/execution/workspace.py", "hengxin-smart-image/backend/tests/test_execution_workspace.py", "hengxin-smart-image/backend/tests/test_revision_execution.py", "hengxin-smart-image/backend/tests/test_single_revision_materials.py", "hengxin-smart-image/backend/tests/test_single_revision_prompt.py", "hengxin-smart-image/backend/tests/test_task_prompt.py"], "approved": false}
```

reviewer 仅写本报告，不修改实现、不提交、不写 `.needs-review`。主 Agent 应对最终 candidateId 登记本报告的两阶段 PASS，交付前再次核对当前快照；新代码变化需重新复核。
