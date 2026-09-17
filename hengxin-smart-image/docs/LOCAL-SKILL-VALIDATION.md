# 本地 Skill 登记专项验证 · 2026-09-17

对应 Spec v0.25。本轮仅本机实现与验证，未提交、未部署 VPS，未调用付费生图。独立审查结果见 LOCAL-SKILL-REVIEW.md。

## 已执行验证

| 范围 | 环境与执行 | 结果 |
|---|---|---|
| 后端全量 | Windows，`CODEX_VERSION=0.153.4`，独立 PostgreSQL 16 测试库，`uv run pytest -q` | 658 passed，104 skipped |
| 后端编译 | `uv run python -m compileall -q app migrations tests` | exit 0 |
| 审查修复回归 | 版本说明持久化/HTTP 返回、旧 ZIP 回退、契约、真实 PG 迁移和并发测试 | 30 passed |
| 版本号修复回归 | 本地登记、文件树、manifest、历史 ZIP 兼容、ASCII/长度/SemVer 边界，共 6 个测试文件 | 56 passed，compileall exit 0 |
| Linux 实际隔离 | WSL Ubuntu，Python 3.12.13，真实 bwrap，`RUN_LOCAL_SKILL_LINUX=1 .../python -m pytest tests/test_local_skills_linux.py -q` | 9 passed |
| 前端单测 | Node 24.18.1，`node node_modules/tsx/dist/cli.mjs --test tests/*.test.ts` | 修复后 110 passed |
| 前端类型 | `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit` | exit 0 |
| 前端构建 | `node node_modules/vite/bin/vite.js build` | 成功 |
| 最终 reviewer 独立抽测 | 后端登记/说明/版本/执行等专项，前端管理与版本校验专项 | 后端 39 passed；前端 14 passed |
| 浏览器 | Chrome，1280×720，Vite mock 独立端口 3018 | 登记、重复报错、异步检查、显式启用、移除确认与移除、空态、读取失败提示 |

后端全量显式固定 CLI 版本以匹配既有 fixture，避免本机 `.env` 的版本值覆盖测试预设。104 跳过包含 Linux 与真实外部集成条件测试；其中新增 Linux 隔离 9 项已另外真实执行，不将跳过项算作通过。PG 迁移 0012 的升级、重复执行、旧 ZIP 保留、本地字段及降级保护和并发检查覆盖使用独立临时数据库，未触及业务数据库。

Linux 专项以管理员创建发布目录，子进程降权为 nobody，验证只读挂载、相邻版本不可见、依赖缺失、可写/执行用户所有的目录、符号链接/硬链接/特殊文件等。该结果不代表 VPS 的内核、服务账户、依赖和 systemd 配置已验收，部署后还需在那里点击真实“检查部署”。

浏览器截图在本机 `output/playwright/local-skills-*.png`；页面使用显式标识的模拟数据，不将 mock 交互称为真实后端联调。桌面正常/错误/空态已查看；390px 窄屏复用现有侧栏有遮挡，本轮未改应用移动端布局，不宣称移动端验收。真实生成效果、服务器并发容量、已有 Skill 目录发布仍待部署后验收。
