# 国内换图记录范围筛选 · 本地验收

用户要求完成开发验证及独立审查后停下来，暂不提交 Git、不部署。本记录不代表生产发布或生产安装包验收。

## 已完成验证

| 层级 | 命令 / 方式 | 结果 | 证据 |
| --- | --- | --- | --- |
| 前端全套 | 前端目录 `node node_modules/tsx/dist/cli.mjs --test tests/*.test.ts` | 355 passed，0 failed，0 skipped | `output/records-scope-formal/frontend-tests.log` |
| 类型检查 | 前端目录 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit` | exit 0 | `output/records-scope-formal/typecheck.log` |
| 正式构建 | 前端目录 `node node_modules/vite/bin/vite.js build` | exit 0，33.20 秒 | `output/records-formal-build.log` |
| 后端专项 | `.venv/Scripts/python.exe -m pytest -q tests/test_api_image_records.py tests/test_list_summaries.py` | reviewer 独立复验 17 passed | `docs/RECORDS-SCOPE-REVIEW-20261022.md` 原始输出 |
| Windows 后端全套 | 后端目录 `.venv/Scripts/python.exe -m pytest -q` | 2047 passed，363 skipped，8 failed；7 项 POSIX 安全打开能力、1 项 symlink 权限限制，须 Linux 复验 | 后端执行记录，不视作全绿 |
| 发布脚本专项 | `.venv/Scripts/python.exe -m pytest -q scripts/release/test_record_filters_release.py`（解释器路径位于 backend） | 34 passed | `output/records-scope-formal/release-tests.log` |
| 浏览器与真实 HTTP | `scripts/records-scope/live-app.py` + `frontend/tests/records-scope.browser.mjs` | 8 组验收通过；35 个业务 GET，0 写请求，0 页面异常 | `output/records-scope-formal/browser-run.log`、`browser-evidence.json` |

浏览器运行真实 FastAPI 路由和正式生产构建，使用隔离内存 SQLite/MemoryStore：51 条未删除任务、3 个创建人。故障分支由隔离测试入口注入，不调用生产接口，不创建收费生图任务。已覆盖默认本人、全部、搜索选择同名及停用历史创建人、状态/日期/编号交集、北京时间边界和自定义同日、20/50/100 分页、全量统计、详情关闭/手动刷新/静默轮询保持页码、重置保范围、菜单重新进入默认本人、旧查询失败保留数据/新查询失败清除旧数据、无匹配与首次无任务、新身份隔离、390px 窄屏。

截图在 `output/records-scope-formal/01-mine-desktop.png` 至 `10-empty-new-identity.png`，另有 `04b-custom-date-inclusive.png`。验收服务 PID 14252 已停止，18926 端口无监听，内存数据随进程释放；证据 `cleanup.log`。

## 最终 Linux 验证

- 本地 WSL Linux、Python 3.12.13、PostgreSQL 18.6，独立 Unix socket 和网络命名空间；依赖按现有 uv.lock frozen 安装，所有测试库 URL 指向临时数据库。按正式 UTC 时区执行 `python -m pytest -q -ra`：**2394 passed，24 skipped，0 failed**，356.50 秒。证据：`linux-utc-full.log` / `.xml`，`linux-utc-status.log` 两项 exit_code=0。
- 新增 `test_api_image_records_pg.py` 六项真实 PostgreSQL 合同再次通过；首次 Asia/Shanghai 六项也已通过，筛选、日期边界与统计不依赖 UTC 会话输出。
- 24 项跳过明确为：22 项需专用 Redis 的身份服务用例、1 项需指定非 root WSL 环境、1 项仅 Windows junction 用例。10 条 warning 为现有测试依赖弃用和隔离 root 下 Celery 安全提示，不是失败。Windows 原先 8 项失败在 Linux 复验通过，首次 Linux 东八区的旧边界问题单独保留在下节。
- 临时数据库已停止、schema/database 无残留，自建 venv、HEAD 对照源码、缓存和临时数据已删除；证据 `linux-utc-cleanup.log`、`linux-utc-schema-cleanup.log`。首轮 HOME 覆盖仅位于隔离子进程，UTC 复验已去掉该设置，未修改宿主环境或用户配置。
- 独立 code-review 两阶段均 PASS，结论限本轮送审范围；报告 `docs/RECORDS-SCOPE-REVIEW-20261022.md`，候选快照 `e40dcd0f8dd9823e4cbb5752a2a4ed376c19f61c6a2365f7ec39b7e42537be5d`，已登记对应审查凭据。未发现本轮必须修复的问题，旧问题及环境/发布验证边界仍按本记录披露。
- 本轮尚未提交、打包或执行生产切换；发布脚本的单元验证不等同于生产部署验证。

## 全量回归发现的既有时区边界

首次 Linux 全套：`2393 passed, 24 skipped, 1 failed`，367.98 秒，见 `output/records-scope-formal/linux-full.log` / `.xml`。新增 PostgreSQL 六条合同全部通过，见 `linux-records-pg-early.log` 和 `linux-records-pg.log`。

唯一失败是既有 `test_api_retry_gate_pg.py::test_oversized_retry_after_survives_postgres_json_and_admin_resume`：上游返回极端大的 Retry-After，旧 `limiter.py:56` 保存 `datetime.max`（UTC），PG 会话使用 Asia/Shanghai 时输出跨到公元 10000 年，psycopg 无法转为 Python datetime。这是实际旧边界缺陷，不能归为本轮已修复或无意义测试失败。[psycopg 官方时间类型说明](https://www.psycopg.org/psycopg3/docs/basic/adapt.html#date-time-types-adaptation) 说明了 timestamptz 按连接时区输出，以及 Python 日期范围的限制。

隔离对照已证明当前代码和改动前 HEAD `11069a3` 在 Asia/Shanghai 下同样失败，在 UTC 下同样通过。证据：`linux-retry-timezone-status.log`、`linux-retry-{current,head}-{shanghai,utc}.log`。重试模块和该测试没有本轮代码改动，本轮不扩大到修改重试策略或执行器发布。

国内正式数据库只读查询返回 `16.15 (Debian 16.15-1.pgdg13+2)`、`Etc/UTC`，证据 `database-timezone-readonly.log`。查询以 `BEGIN READ ONLY` / `ROLLBACK` 执行，未修改生产数据、配置或服务；一次 SSH 超时后只读重试成功。Linux 隔离验证使用 PostgreSQL 18.6，因此不能宣称等同于正式 PostgreSQL 16.15 安装镜像验收。按正式 UTC 时区重跑全套已通过，保留上述失败及差异，不用新结果覆盖旧记录。本次审查结论限于换图记录筛选变更，不宣称整个系统在所有时区没有既有问题。
