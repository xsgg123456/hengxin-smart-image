# Phase 7 独立集成验证

验证入口：`infra/verify_phase7.py`。2026-09-09 审查修复后的完整 API/Worker 与真实浏览器验证通过，进程退出码 0。

## 隔离与运行

从仓库根目录执行（需 Docker Desktop Linux 引擎；Python 3.12）：

```powershell
& 'C:/Program Files/Docker/Docker/resources/bin/docker.exe' build -t hengxin-smart-image-backend:phase7 -f hengxin-smart-image/infra/Dockerfile.backend hengxin-smart-image
& 'C:/Users/82358/AppData/Local/Programs/Python/Python312/python.exe' -u hengxin-smart-image/infra/verify_phase7.py --browser
```

脚本随机生成 Compose 项目名 `hx-phase7-test-<随机值>`、凭据与 API/PG/MinIO/Vite 端口。只操作本次项目的 PostgreSQL、Redis、MinIO、Skill 安装四卷；不读写正在运行的开发库，不使用 8008/3008。后端全套 pytest 显式使用该项目内新建的 `hengxin_test` 数据库，模板并发测试另建随机 schema。凭据不写文件、不打印，失败信息做凭据替换。`finally` 删除四卷并检查残留；可选浏览器使用专用 CLI session，收尾关闭并删除会话数据，结束 Vite 和临时日志目录。

不带 `--browser` 时只运行 API/Worker。浏览器用已有 npx/Playwright CLI，调用根目录 `scripts/phase7/catalog-flow.js`。日志示例：根目录 `scripts/phase7/integration.log`（忽略的运行产物）。

## 最新实测结果

- Linux 容器从空卷迁移到 head、重复迁移及 Python compileall 通过。
- 后端全套 pytest：**108 passed，2 warnings，5.82s**；包含 PostgreSQL 队列、模板并发、默认绑定跨事务停用锁校验和存储失败后同版本重传测试，无跳过。警告来自 Starlette TestClient/httpx 和 anyio 别名弃用。
- ZIP 经真实 HTTP multipart 上传至私有 MinIO，真实 Celery Worker 解压安装；1.0.0/2.0.0 成功，缺可执行依赖的 1.0.1 失败，旧版保持 available。
- Redis 实际停止期间受理安装请求；恢复后 Worker 完成 1.1.0。成功和失败 outbox 已结束，经历后续重启后 dispatch_count 未继续增加。
- 模板草稿、模块默认、专用优先、默认切换保留旧绑定、再次保存解析新默认、图片次序及历史不可变、409 乐观锁冲突、422 类型错配通过。
- Worker/API/PG/MinIO 重启后，数据库安装路径及 Worker 卷内 SKILL.md 可读取，旧模板仍绑定旧版。停用显式 Skill 保留其绑定并使模板不可用，不回落到新默认。
- 主管/设计/运营直接上传、安装、启停及改默认均 403；共享模板读取和创建允许。第二个可信测试用户可编辑、停用、删除原用户模板，删除审计记录实际操作者，3 个历史版本和原始图片记录保留。
- 合法 Phase 8 任务请求仍返回 501，没有模拟生成成功。四个隔离卷最终全部清理。
- 浏览器真实上传/安装 3.0.0、设置默认、新建模板、默认绑定冻结、编辑图片顺序、模拟一次409后表单保留并真实保存、查看v1/v2历史、1024px宽度、邻接创建页与删除落库通过，**pageerrors=0**。API阶段另行验证了真实409；浏览器注入409只用于表单错误恢复。
- 最终日志：`PHASE7 BROWSER PASS`、`PHASE7 INTEGRATION PASS (four isolated volumes)`、`PASS isolated Compose volumes cleaned`。稳定截图在根目录 `output/playwright/phase7-skills.png`、`phase7-history.png`、`phase7-neighbor.png`。

## 验证边界

当前使用服务端显式开发身份，真实钉钉登录属于 Phase 12。本阶段只验证受控包校验、安装及绑定；没有执行 Codex CLI、真实图片生成或业务 Skill 效果。测试图片为2×2白色像素，不用于效果评测；运行结束不保留浏览器身份数据。
