# 自然语言提示词与 Skill 路径验证 · 2026-09-17

本轮仅调整任务提示词与任务内完整 Skill 目录路径；没有修改前端、数据库结构、Skill 源码、线上环境或执行付费生图。

## 实现

- Skill 入口为 `/work/skills/{标识}/SKILL.md`，本地版本整目录只读挂载；历史 ZIP 整包解压到相同目录结构。旧名称不符合安全标识时使用 `legacy-{版本ID}`，不将名称作为任意路径。
- 提示词主体按“使用技能 → 底图/素材路径与实际数量 → 修改要求 → 可选补充要求”组织；底图逐张列出，兼容混合扩展名及非固定张数。壁纸模式使用用户确认的壁纸与镜头替换要求；商品、文字模式分别处理。
- 返工保留原底图、当前结果、本轮修改意见和局部 slot 到原 taskSlot 的映射。后台收图协议与全量 JSON 映射置于末尾。网页补充要求以 JSON 数据引用，保留全文。
- 检查部署和正式任务使用同一目录规则，目录命名不等于 Codex `$技能名` 自动发现。实际示例见 [PROMPT-FORMAT-EXAMPLE.md](PROMPT-FORMAT-EXAMPLE.md)。

## 当场验证

- 后端：`CODEX_VERSION=0.153.4 uv run pytest -q`，**645 passed、145 skipped**，33.33秒。跳过为依赖独立PG/Linux/外部集成开关的测试，不算通过；本轮不改迁移，前轮PG证据见 LOCAL-SKILL-VALIDATION.md。
- 编译：`uv run python -m compileall -q app tests`，exit 0。
- 独立 reviewer 抽测：33 passed、1 Windows 条件 skipped，编译通过；另独立复跑 WSL 隔离 9 passed。
- Linux 实际隔离：WSL Ubuntu、`RUN_LOCAL_SKILL_LINUX=1 /tmp/hengxin-skill-linux-venv/bin/python -m pytest tests/test_local_skills_linux.py -q`，**9 passed**。覆盖 `/work/skills/demo/` 下入口和脚本可读、只读挂载、邻居不可见及依赖/不安全发布拒绝。
- 新增 prompt 专项覆盖四张底图、一张/多张素材、商品/文字文案、返工当前图及 slot、目录越界拒绝；历史 ZIP 测试实际解包并核对 scripts/references/assets 均保留。模拟 CLI 的既有 runner 回归按新清单读取实际准备的文件。
- 首轮回归发现3个测试失败：观测 runner 测试的简化材料 fixture 缺少真实材料原本就提供的 mode/path 及新增 skillPath。已补齐 fixture 后重跑全量通过；未放宽生产提示词校验来迁就模拟输入。

没有验证真实模型输出与人工测试逐像素或效果一致；该对照需要部署后使用相同 Skill、依赖和那组真实图片执行。独立审查记录见 PROMPT-FORMAT-REVIEW.md。
