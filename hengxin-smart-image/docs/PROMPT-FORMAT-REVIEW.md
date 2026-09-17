# 提示词与 Skill 目录增量独立审查

审查日期：2026-09-17。candidateId：`9146276c4efa3fd86d5102947dd8e93e9fd2f748a7d06aa6dced68c75c589d34`。

**Stage 1：PASS。Stage 2：PASS。未发现本轮 HIGH / MEDIUM 阻塞问题。**

本报告承接 `LOCAL-SKILL-REVIEW.md:3` 中已批准候选 `6b62e18598cb6e4e2232254e9a908d929e07b17b476122e426910bf14c633674`，只审新旧候选之间的提示词/路径增量，不重新批准或扩大旧功能范围。依据 `Product-Spec.md:475` 的追加条目、`:483` 的挂载要求及 `DEV-PLAN.md:3` 的三步计划。

范围：`backend/app/execution/` 下 workspace.py、materials.py、local_skill_probe.py、codex_runner.py、新增 prompts.py；`backend/tests/` 下 test_execution_workspace.py、test_codex_runner.py、test_observed_runner.py、test_local_skills_linux.py、test_local_skill_execution.py、新增 test_task_prompt.py；相应源文档和交付说明。以下 backend 路径均相对 `hengxin-smart-image/backend/`。前后两次 review-status 显示 currentId 均为本候选，changedFiles 恰为上述 11 个代码/测试文件；未发现审查中代码变化。主线程补充的普通 Markdown 不改变代码候选。

## Stage 1 · Spec Compliance

| 逐条要求 | 结论与证据 |
| --- | --- |
| 完整 Skill 位于 `/work/skills/{标识}/` | 完整实现。workspace.py:20–24 校验标识并构造路径，:90–92 对本地版本做整目录只读挂载；materials.py:68–77 设置入口与固定树；:83–87 写入 ZIP 所有文件。真实 Linux test_local_skills_linux.py:66 同时检查入口和 poison.py 可读、写入触发只读错误。 |
| 部署探针与正式运行使用相同挂载目标 | 完整实现。local_skill_probe.py:50–57 使用同一 Workspace/sandbox_command，根路径由 workspace.skill_path 传入；正式入口 codex_runner.py:138 使用相同函数。local_tree.py:39、:90–93 保证发布目录标识与登记名一致。独立 Linux 9 项通过。 |
| 自然语言顺序、实际路径/数量/角色 | 完整实现。prompts.py:8–20 先入口再底图与素材，数量来自列表长度，逐张列出实际路径，文字模式底图独立描述；materials.py:39–47 按真实 MIME 生成扩展名。test_task_prompt.py:16–26 验证四底图/一素材及末尾完整映射，:46–51 验证多素材。 |
| 壁纸固定句、多素材指代 | 完整实现。prompts.py:22–24 使用确认句，单张“这张”、多张“这些”；test_task_prompt.py:21、:50 验证。 |
| 商品/文字模式不套手机要求 | 完整实现。prompts.py:12–15、:25–28 按 mode 分支；test_task_prompt.py:29–33 两种模式分别断言无手机屏幕/壁纸镜头文案。 |
| 可选补充保持原文并以 JSON 数据引用 | 完整实现。prompts.py:31–33 非空时 json.dumps(note, ensure_ascii=False)，不改写补充原文；test_execution_workspace.py:31–35 用引号、换行与指令式文本验证数据引用。空白输入不生成多余要求段落，test_task_prompt.py:25。 |
| 返工当前结果、原底图、本轮意见和槽映射 | 完整实现。materials.py:34–47 将选中目标重编局部 slot；:50–64 保留 taskSlot/currentPath；prompts.py:16–20、:29–33 描述当前/原图及返工意见；codex_runner.py:91、:147 传原会话 ID，失败无当前图时也识别返工。test_task_prompt.py:36–51 覆盖局部 slot 0 对原 taskSlot 3 和无成功结果的续接提示。 |
| 后台结果协议放末尾，保留完整输入、失败槽及真实结果校验 | 完整实现。prompts.py:34–40 放置完整协议及 manifest；codex_runner.py:166–178 继续调用失败清单、收集和来源校验。output_collector.py:67–100 校验 slot，provenance.py:116 起验证真实生成来源。test_observed_runner.py:54 起实际走编排的全失败路径；test_codex_runner.py:100 起覆盖结果保存及失败不发布。 |
| 历史 ZIP 安全目录回退、完整包保留 | 完整实现。materials.py:69 非安全名回退 legacy-版本 UUID；:83–87 遍历所有 package.files。test_local_skill_execution.py:65 起实际构造/解包含 scripts、references、assets 的 ZIP，使用 `../旧名称` 验证回退且逐个核对文件。package_validator.py:43–66 的既有路径/链接拒绝仍生效。 |
| 不宣称自动发现或与人工测试效果一致 | 匹配。docs/PROMPT-FORMAT-VALIDATION.md:10、:22 明确路径规则与真实模型效果边界；docs/PROMPT-FORMAT-EXAMPLE.md:3 标记结构示例。没有将模拟 CLI 结果当作真实模型效果证据。 |

部分实现：无。未实现：无（限上述增量）。Spec 漂移：没有新增页面/API/表；prompts.py:5 的抽离和 workspace.py:20 的路径属性均直接服务本轮条目。UI 与视觉对比：不适用，本候选相对上次已批准快照无 UI 文件变化，不虚构浏览器对比。

## Stage 2 · Code Quality

- 结构与大小：prompts.py 40 行，materials.py 87 行，workspace.py 97 行，local_skill_probe.py 64 行，codex_runner.py 218 行，均不超过 300。提示词单独负责排版（prompts.py:5），材料层负责映射（materials.py:28），未新增动态 eval 或前端 any。
- 安全：五个实现文件扫描 eval、shell=True、innerHTML、dangerouslySetInnerHTML、sk-ant/sk-proj、VITE 密钥变量无命中。workspace.py:22、materials.py:69 的白名单阻止目录穿越；test_task_prompt.py:54–57 覆盖斜杠、反斜杠、绝对路径、空名和换行。local_skill_probe.py:55 使用 argv 与超时，不把技能标识或用户意见拼入 shell。prompts.py:33 的 JSON 引用是提示边界，不宣称能绝对阻止模型提示注入；实际文件边界仍由 sandbox_command 保障。
- 错误处理：materials.py:72–76 保持固定部署错误转换，codex_runner.py:197–200 保持脱敏失败路径；本轮移动路径没有放宽冻结版本/hash 校验（materials.py:66、:79–82）。
- 测试真实性：test_codex_runner.py:25–41 明确 mock CLI/存储及隔离边界，只证明真实业务编排和物料落地；test_local_skill_execution.py:19–47 mock validate_local，只证明冻结参数传递且不复制本地树。真实权限/挂载证据来自 test_local_skills_linux.py:20–49：root 发布、子进程清组并降到 nobody，实际运行 bwrap。独立复跑成功，不将 mock 作为 Linux 隔离证据。
- 测试边界：test_task_prompt.py:36 的返工是构造 manifest 的文本契约测试，不是付费模型返工；当前/原图读取实现另据 materials.py:50–64 核对。真实同素材效果、VPS 部署和付费生图均未执行；不影响本轮路径/格式实现审查，但不能据此宣称这些验收完成。

## 独立复跑证据

工作目录：`hengxin-smart-image/backend`。Windows 设置 `CODEX_VERSION=0.153.4`。

专项命令：`uv run pytest tests/test_task_prompt.py tests/test_execution_workspace.py tests/test_codex_runner.py tests/test_observed_runner.py tests/test_local_skill_execution.py -q`。原始结果：

```text
...............s..................                                       [100%]
33 passed, 1 skipped, 2 warnings in 3.15s
```

1 项跳过是 POSIX symlink 用例的 Windows 条件（test_execution_workspace.py:46）。2 项 warning 来自 Starlette TestClient/httpx 与 anyio 弃用，不是本轮失败。

全量命令：`uv run pytest -q`，退出码 0。原始汇总：

```text
645 passed, 145 skipped, 14 warnings in 33.04s
```

跳过项不计为通过；全量用于回归，不扩大本报告的人工代码审查范围。warning 为 Starlette/anyio/cookie 弃用及现有 auth dependencies.py:28 的 NULL primary key 提示。

编译命令：`uv run python -m compileall -q app tests`。原始 stdout/stderr：空；退出码：`0`。正确后端工作目录执行。

真实 Linux 命令：`wsl -u root -- bash -lc 'cd /mnt/d/Work_Project/hengxin-smart-image/hengxin-smart-image/backend && RUN_LOCAL_SKILL_LINUX=1 CODEX_VERSION=0.153.4 /tmp/hengxin-skill-linux-venv/bin/python -m pytest tests/test_local_skills_linux.py -q'`。原始 pytest 输出：

```text
.........                                                                [100%]
9 passed in 8.96s
```

退出码 0。WSL 启动另有 localhost 代理提示，与测试结果分开记录；没有连接付费模型。

审查员只新增此报告，未改代码、提交、部署或登记批准。主 Agent 应以此 candidateId 执行 review-approve 并再核对 review-status；不得将本报告用于不同代码快照。
