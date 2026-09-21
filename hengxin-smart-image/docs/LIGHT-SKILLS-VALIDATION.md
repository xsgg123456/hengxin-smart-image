# Skill 管理轻量化验证

日期：2026-09-21。以下为本地实现验证记录；后续已提交f02b1e0并部署生产，详情见`LIGHT-SKILLS-DEPLOYMENT.md`。未调用付费生图。

## 自动验证

- 前端119项测试通过，vue-tsc类型检查通过，正式Vite构建通过。输出：`output/light-skills-frontend-{tests,typecheck,build}.txt`。
- 后端全量801 passed、112条件跳过；输出：`output/light-skills-backend-tests.txt`。Linux隔离和环境专项须单独执行，不能把跳过视为通过。
- Ubuntu真实只读bubblewrap隔离：`RUN_LOCAL_SKILL_LINUX=1 CODEX_VERSION=0.153.4 /tmp/hx-light-skills-venv/bin/python -m pytest tests/test_local_skills_linux.py tests/test_skill_catalog_linux.py -q`，16 passed in 44.40s。覆盖旧布局及平铺目录、依赖探针、内容字节保留、软硬链接/FIFO/可写目录拒绝。
- 最终补充可执行权限保留后，重新运行`test_skill_catalog_linux.py`，7 passed in 6.80s。
- 最终定向17项通过，输出`output/light-skills-backend-focused.txt`，包含独立PostgreSQL的并发请求合并和0014迁移兼容测试，以及空值业务拒绝保护。新后端专项覆盖快照更新、新任务跟随、排队旧任务及移除后返工仍用原ZIP字节，停用保持、未知类型、存储失败和租约发布限制。
- PostgreSQL单独运行2项通过（1.31s），输出`output/light-skills-backend-postgres.txt`；后端compileall通过。全套也使用独立测试PostgreSQL，原始命令和环境见`output/light-skills-backend.md`。
- 独立审查后的最终相关回归51项通过（9.73s），输出`output/light-skills-backend-review-fix.txt`；其中真实PostgreSQL模板编辑/任务提交交错测试也单独通过（1.95s，`output/light-skills-template-concurrency.txt`）。修复全局同步与类型选择竞争、模板锁顺序及遗留Skill模板筛选一致性；保留旧模板版本的乐观并发检查。

## 浏览器交互

使用本机3010端口显式mock模式、超级管理员身份，未连接生产API。

- 管理页每个Skill一行，没有人工版本登记、版本列表与切换入口；继承现有Art/Element Plus样式。
- 使用用户提供的完整京东主图描述验证三行折叠与展开全文；1280×720视口无文字裁切，列表自然纵向滚动。
- 停用后全局同步仍保持停用；同步期间禁止重复点击和配置提交。
- 同步失败显示异常Skill和原因；再次同步恢复可用；其他正常Skill仍显示可用。
- 未知类型选择“替换壁纸”后自动进入同步并成为可用；未绑定的新登记可移除，绑定项显示解除引用提示并禁止移除。
- 移除对话框明确只撤销登记、保留服务器文件，确认后该行消失。
- 打开相邻模板库核对同一侧栏、卡片圆角、蓝色按钮和留白；模板配置中的Skill选择下方显示完整用途，说明后续任务跟随最近成功同步内容，未再显示Skill版本。

## 已知边界

- 历史本地任务继续依赖原`<name>/<version>`发布目录，不可因改为平铺管理而删除旧树；本轮新同步内容自动冻结对象快照。
- 模拟浏览器验证证明交互，后端测试证明API/Worker行为；未用真实付费模型验收图片效果。
- 独立两阶段审查结果见`LIGHT-SKILLS-REVIEW.md`，最终快照批准由主Agent另行登记。
