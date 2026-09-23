# CLI 壁纸单张修改原图对照审查

- 审查日期：2026-09-23。
- 最终 candidateId：`46a02346bc9ffc8bb7427a495ffa13f4bb734325c4f0169fb20ddae74e2afa45`。
- Stage 1：PASS；Stage 2：PASS。未发现本次范围内 HIGH / MEDIUM 缺陷。
- 范围：本次 git diff 的 Product-Spec.md、DEV-PLAN.md、Product-Spec-CHANGELOG.md，以及 `hengxin-smart-image/backend/` 下 `app/execution/{materials,prompts,final_delivery}.py`、`tests/test_{single_revision_materials,single_revision_prompt,final_delivery}.py`，共 9 个文件。以下后端路径均相对此 backend 目录。
- 独立审查仅读取代码、执行隔离测试、写本报告；未修复代码、提交或调用收费生图。两个既有未跟踪性能文档不在范围内。

## 快照变化

初始派发 candidateId 为 `4c03bb5ac3b25c5774d14c2e425def3bc622f43ce5a0dd5cb2359d63c93c83ef`。审查期间主 Agent 修正新增四槽位测试的模板请求：补必填 notes，并增加正确的 HTTP 200 断言（`tests/test_single_revision_materials.py:37`）。中间曾读到 HTTP 201 断言；最终已复读 HTTP 200，重新运行完整针对性测试，不能将中间结果用于批准旧快照。

主 Agent 重新 prepare 后提供上述最终 candidate。审查结束运行 `harness.py review-status` 的原始输出：

```json
{"currentId": "46a02346bc9ffc8bb7427a495ffa13f4bb734325c4f0169fb20ddae74e2afa45", "reviewedId": "0d022306567a537d110c03e55298f2785d7890aa6f6c340d5537b5d56387549a", "changedFiles": ["hengxin-smart-image/backend/app/execution/final_delivery.py", "hengxin-smart-image/backend/app/execution/materials.py", "hengxin-smart-image/backend/app/execution/prompts.py", "hengxin-smart-image/backend/tests/test_final_delivery.py", "hengxin-smart-image/backend/tests/test_single_revision_materials.py", "hengxin-smart-image/backend/tests/test_single_revision_prompt.py"], "approved": false}
```

当前代码匹配最终 candidate；批准登记由主 Agent 执行，本报告不写 `.needs-review`。

## Stage 1：Spec Compliance — PASS

对照 `Product-Spec.md:35`、`:37`、`:39` 全部新增条款：

| 条目 | 结论与证据 |
| --- | --- |
| 四个壁纸 Skill 统一单张行为 | 完整实现。`app/execution/prompts.py:29` 按 wallpaper 模式分派，不按 Skill 名特判；四名称参数测试 `tests/test_single_revision_prompt.py:8` 全通过。 |
| 选定冻结无标注成品是唯一基础 | 完整实现。`app/execution/materials.py:72` 读取 round.base_version_id 并校验槽位归属，`:84` 提供 currentPath；`prompts.py:9` 明确唯一修改对象。历史 V1 与最新 V2 不同字节及第四槽位测试 `tests/test_single_revision_materials.py:32` 通过。 |
| 自动取任务冻结模板对应槽位原图，不读最新模板、不重传 | 完整实现。`materials.py:35` 使用 task.template_snapshot，`:37` 按 round.target 选择，`:47` 写 original；`tests/test_single_revision_materials.py:179` 改变实时模板后断言仍读取冻结槽位的不同图片字节，通过。 |
| 原图缺失、删除、损坏、校验失败明确失败，不省略 | 完整实现。`materials.py:54` 检查记录状态和删除；`:18` 读取并校验 SHA256，异常向上传递，无忽略分支。`tests/test_single_revision_materials.py:157` 的 deleted/corrupt/missing 三场景全部通过。 |
| 手机屏幕素材、可选标注 | 完整实现。`materials.py:44` 保留来源素材；`:90` 读取独立标注；`prompts.py:13` 声明屏幕角色，`:16` 条件加入标注及禁止将标记放入成品。历史成品与本轮标注独立字节验证 `tests/test_single_revision_materials.py:60` 通过。 |
| 提示词顺序、意见原文 JSON、空意见兼容 | 完整实现。`prompts.py:8` 至 `:25` 顺序符合规范；`:20` 使用 json.dumps 原 note。`tests/test_single_revision_prompt.py:10` 覆盖无标注、空意见仅标注、多行意见，`:23` 检查顺序，全部通过。 |
| 原图结构/边缘/遮挡/光影职责，屏幕新壁纸/开孔职责 | 完整实现。`prompts.py:12`、`:15`、`:23` 明確区分；逐字核对 Spec 与提示词，并由角色提示词测试 `tests/test_single_revision_prompt.py:12` 验证。 |
| 局部修复及必要衔接，保留成果，不恢复旧壁纸或撤销无关修改 | 完整实现。`prompts.py:22`、`:23` 包含全部限制，代码文本与 Spec 匹配。 |
| 输出前对照及明确缺陷继续修复，不因无关疑虑整图重做 | 完整实现。`prompts.py:24` 包含对照对象、交界及错误类别与局部继续限制；`tests/test_single_revision_prompt.py:29` 验证存在对照指令。 |
| 当前尺寸、仅一张、未解决如实说明 | 完整实现提示词契约。`prompts.py:25` 明文规定；最终数量由 `codex_runner.py:176` 传入一个 target，`final_delivery.py:227` 精确检查数量。生成模型实际图像质量由用户后续实图验证。 |
| 沿用原会话，不挂载/调用首轮 Skill | 完整实现。`materials.py:99` 提前返回且 use_skill=False；`workspace.py:97` 隐藏 Skill 发现目录；`codex_runner.py:94`、`:118`、`:147` 取并校验原会话，以 resume 续接。坏 zip/local Skill 仍正常准备材料的测试 `tests/test_single_revision_materials.py:123` 及续接测试 `tests/test_codex_runner.py:136` 通过。 |
| /work/original 输入目录不能直接收为成品 | 完整实现。`materials.py:48`、`:62` 固定目录；`final_delivery.py:19`、`:202` 拒绝保护目录；`tests/test_final_delivery.py:107` 原图交付拒绝测试通过。 |
| 商品、文字、无成品重试、首轮及整套行为保留 | 完整实现。`materials.py:47` 只对 wallpaper 且 single_base 分支生效；`prompts.py:49` 仅单目标有成品时进入简化修改。其他模式和无成品提示词测试 `tests/test_single_revision_prompt.py:46`、`:57`，文字无原图与冻结空基础测试 `tests/test_single_revision_materials.py:83`、`:102` 均通过。既有首轮 runner 测试 `tests/test_codex_runner.py:113` 通过。 |
| 文档同步、上线排空和用户自行测图 | Spec、计划、变更记录一致（`Product-Spec.md:33`、`DEV-PLAN.md:3`、`Product-Spec-CHANGELOG.md:3`）。本报告仅验收代码及隔离回归；生产排空、部署和真实图片效果由主 Agent/用户另行完成。 |

部分实现：无。未实现：无（上述生产部署与实图效果不作为本次代码审查已完成事项）。Spec 漂移：未发现；新增 originalPath、目录保护和壁纸提示词均对应 `Product-Spec.md:35` 至 `:39`。

UI 一致性、引导真实性：不适用，本次 9 文件不涉及页面、前端引导或设计改动；未声称进行浏览器视觉验证。

## Stage 2：Code Quality — PASS

- 结构与大小：`materials.py:31` 沿用已有材料流程，仅增加原图分支；`prompts.py:6` 将壁纸短提示词独立为函数；`final_delivery.py:19` 复用既有保护目录校验。三个实现文件分别 132、84、253 行，三个测试文件分别 198、64、273 行，均小于 300 行。未引入 Any、全局可变状态或额外依赖。
- 安全：按 skill 给出的密钥、eval、HTML 注入、前端 secret、用户绝对路径模式扫描三个实现文件，无匹配。新增路径由固定目录和索引构成（`materials.py:48`、`:58`），不拼接用户文件名；意见经 JSON 编码（`prompts.py:20`）；输入保持校验（`materials.py:26`）；最终原图路径拒收（`final_delivery.py:202`）。没有本次新增安全问题。
- 测试真实性：`tests/test_single_revision_materials.py:32` 通过真实测试 HTTP 接口创建任务和返工，并用不同字节证明冻结成品；`:179` 用不同原图字节与改变后的实时模板证明冻结映射；`:157` 验证故障路径。不是只检查 manifest 标签。使用 fixture runner 和对象存储替身，未验证付费模型能否忠实遵守所有视觉指令。
- 测试边界：Windows 无符号链接权限导致既有 `tests/test_final_delivery.py:261` 用例跳过；普通 original 目录拒收测试已执行。真实 CLI 生图、真实页面与生产安装验证不在本次隔离审查中。不存在本次新增 UI，邻居页面视觉对比不适用。
- `git diff --check` 退出码 0，无差异格式错误；仅提示两个 Markdown 文件 CRLF 将归一化 LF。

## 验证原始输出

最终 candidate 独立执行命令：

```text
.venv/Scripts/python.exe -m pytest tests/test_single_revision_materials.py tests/test_single_revision_prompt.py tests/test_final_delivery.py tests/test_codex_runner.py -q -rs
........................................................................ [ 69%]
................s..............                                          [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
SKIPPED [1] tests\test_final_delivery.py:261: symlinks unavailable on this host
102 passed, 1 skipped, 2 warnings in 7.03s
```

编译命令退出码 0，原始输出：

```text
.venv/Scripts/python.exe -m compileall -f app/execution/materials.py app/execution/prompts.py app/execution/final_delivery.py tests/test_single_revision_materials.py tests/test_single_revision_prompt.py tests/test_final_delivery.py
Compiling 'app/execution/materials.py'...
Compiling 'app/execution/prompts.py'...
Compiling 'app/execution/final_delivery.py'...
Compiling 'tests/test_single_revision_materials.py'...
Compiling 'tests/test_single_revision_prompt.py'...
Compiling 'tests/test_final_delivery.py'...
```

完整后端回归由主 Agent 另行执行，不以其尚未交付结果替代本报告的独立测试证据。
