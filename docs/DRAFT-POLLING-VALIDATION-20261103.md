# 草稿查询整改验证与发布记录

目标：0.2.61 / overseas_0026。用户批准范围见 [实施合同](DRAFT-POLLING-IMPLEMENTATION-20261103.md)。本轮未修改数据库模型、业务写锁、附件下载和 worker 实现。

## 验证证据

- 前端 `pnpm test`：481 passed，0 failed/skip（14.25 秒），`output/frontend-polling-tests.log`。包含真实控制器和正式 SFC 的条件轮询、慢 GET 去重及保存优先、隐藏自动保存/恢复、三次失败暂停、读写错误区分、上传完成补读与迟到/提交保护。
- `pnpm typecheck`：exit 0，`output/polling-release/typecheck.log`。正式 `pnpm exec vite build`：成功（39.16 秒），`frontend-build-final.log`。
- 正式 dist `http://127.0.0.1:3040` + 隔离 API 的浏览器脚本 `frontend/tests/overseas-requirement-drafts.browser.mjs` 通过，`output/polling-release/browser.log`：初始一次读取/空闲无 GET、可见恢复、三次失败暂停和手动重试、单 SKU 多记录选择、4 个后台附件及 2 个手动附件、持久化恢复、错误保留、跨账号/跨标签冲突、未知提交幂等与审核附件。测试不连接生产 API。
- 目视核对正式构建的桌面表单、查询暂停警告/重试入口及相邻任务列表。截图 `output/playwright/sku-drafts/desktop.png`、`output/polling-release/query-paused.png`、`tasks-neighbour.png`。窄屏用例检查文件名和提交按钮裁切；整页截图中的既有固定导航叠层不作本轮布局改动。
- 本地后端 HTTP/草稿/worker：23 passed；本机未配置 PG URL 的 7 条测试未计为通过，真实 PG 结果另记。
- 发布工具：新 19 + 旧 SKU 62 = 81 passed。4 个备份/恢复测试已独立拆到 `test_polling_database.py`；`python -m unittest discover -s scripts/release -p 'test_polling*.py' -q` 19 passed。日志 `release-tests.stdout`、`sku-release-regression.stdout`。
- 依赖未变更；`pnpm audit --prod --json`：critical 0、high 39、moderate 38、low 5，与上一版本记录一致，不声称零依赖告警。

## 发布边界与基线

- 只读核查：生产前端 0.2.60、数据库 overseas_0026；API 镜像 `sha256:82c9bda8995c2fc65b270b12b37056e4404cd14f05ab8cbd56fcd5eae09fa248`，容器 `77df61657114b52f5b0b6bcc82b2a87b55a8f358487944ee754395f5f607a18c`。证据 `output/polling-release/baseline.json`。
- API 制品只覆盖 `app/overseas/drafts/router.py` 和新增 `read.py`；复用真实镜像、依赖及原 Compose 配置，保留上游密钥覆盖层。原生服务可正常排空停启，但源码零替换；不迁移、不回卷数据库、不修改 Skill。
- 正式次序：已审中文提交 → 固定包及隐私/哈希验证 → prepare → 安装测试 → gate → backup（隔离恢复与全表指纹/schema 校验）→ api → frontend → verify → resume。
- gate 前后检查导入任务；若新导入与停止竞争，明确中止切换并恢复旧 API，让持久租约恢复，不冒充已排空。不得强杀生产工作进程。
- 切换前失败执行 `recover-before-switch`；切换后失败按 `rollback` 恢复旧 API 镜像和前端入口，数据库保持现状。正式包、旧镜像和备份目录均保留。
- 本地构建期间误产生的 `polling-20261103-candidate-80ec106e4fad` 已标记 INVALID，未上传、未部署；发布工具已增加入口资源完整性及 dist 二次字节一致校验，禁止使用该包作为证据。

## 真实 PostgreSQL 候选回归

候选 `ffac39640348` 在真实生产基线镜像上只覆盖两份 API 文件，使用无外网、无生产卷/环境的隔离 PostgreSQL 与只读安装容器运行 97 个海外模块：**824 passed，0 failed/skip，2 项既有弃用警告，632.79 秒**。包括本轮新增 7 条 PostgreSQL 用例，证明慢 GET 仅持 AccessShareLock、同账号保存及 complete 不受阻、一致快照、连接池属性复位、首次并发创建、清空/提交交错及真实子进程退出后的租约恢复。

命令 `python output/polling-release/candidate.py` exit 0。证据 `output/polling-release/candidate-ffac39640348.stdout`，结尾 `PRODUCTION_UNCHANGED`，stderr 为空。隔离 PG 容器及卷已由 finally 清理；候选镜像与测试日志保留。测试边界：没有对生产数据库制造锁等待或杀生产进程。

独立 `code-review` 两阶段 PASS，候选 `78616f8ad665d5e7c79be0070f78e6f72a289b0d54f0dcbf50342dc6d977b6d0`，报告 `output/polling-release/REVIEW.md`。发布测试文件超长问题已拆分并复核，未关闭 HIGH/MEDIUM 为 0。正式提交及生产结果在完成后追加。
