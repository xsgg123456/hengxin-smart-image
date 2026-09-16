# 开发机 Codex CLI 联调

本入口用于 Phase 11A。本地 API、Outbox、PostgreSQL、Redis、MinIO 继续由 `hx-local-test` Compose 项目提供；真实执行 Worker 运行在 Ubuntu-24.04 WSL 的非 root 用户 `hengxin` 下。每个任务的 CLI、会话和目录仍由现有执行管理器管理，不共享桌面 Codex 会话。模型网络已通过沙箱内 CLI 请求验证；真实业务验收仍需单独验证。

## 环境准备

2026-09-11 已在本开发机完成以下配置。脚本不自动安装系统或复制认证文件：

- Ubuntu-24.04 WSL、Python 3.12、bubblewrap、python3-pil。
- `/opt/hengxin-runtime/codex-0.153.4/` 下放置官方 Linux CLI 和配套 `codex-code-mode-host`，使用 npm 官方 tarball 并核对 registry SHA512。
- `/home/hengxin/runtime/venv` 使用后端 `uv.lock` 安装；Windows 控制脚本使用含 `python-dotenv` 的 Python 3.12。
- 独立 `/home/hengxin/auth/auth.json`，目录 0700、文件 0600，所属用户 hengxin；只复制所需认证文件，不挂载完整个人配置目录。认证续期后需同步该文件，不要将内容写入日志或 Git。
- `/home/hengxin/execution` 与 `/home/hengxin/skills` 是独立执行目录。
- 从 `infra/.env.local-codex.example` 创建忽略跟踪的 `infra/.env.local-codex`。基础 `infra/.env` 保持明确的 `APP_ENV=test`、fixture=true、codex=false，恢复模式时使用它。

WSL 必须能访问模型服务。`codex login status` 只检查已有登录状态，不能证明模型网络可用。开发机使用 WSL 镜像网络和 autoProxy 连接 Windows 代理。在 `.env.local-codex` 显式设置 `LOCAL_CODEX_PROXY_URL=http://127.0.0.1:7890`，本地 Worker 将其传给任务沙箱。仅 test/development 环境允许此选项，代理限定为无认证的 loopback HTTP(S) 端点；不会继承宿主的其它环境变量。沙箱同时设置大小写 HTTP_PROXY/HTTPS_PROXY/NO_PROXY，NO_PROXY 限定 localhost、127.0.0.1、::1。生产环境不启用本地代理选项。网络配置后须验证沙箱内模型请求，而非仅检查登录或 HTTP 隧道。

## 启停

2026-09-11 日常并行配置调整：用户反馈同时提交两个任务仍串行，实查基础 `.env` 的 `GENERATION_CONCURRENCY=1`，运行中 Celery pool 也只有一个进程。此前“并发2通过”指独立验收环境，不能等同日常环境已启用。此次将本机 `infra/.env` 显式设为 `GENERATION_CONCURRENCY=2`，保留项目通用默认值1；待所有任务终结后通过现有 controller 安全重启 API/Outbox/WSL Worker。验收核对实时 pool 上限2、两个消费者PID、API/Worker配置一致及原任务记录保留。同一任务的轮次仍互斥，两个不同任务可并行。

调整已生效：controller `start` 返回 PASS，实时 Worker `max-concurrency=2`、消费者 PID 24403/24404、prefetch=2；API/Outbox 容器并发配置均为2、API HTTP200。原任务 `09a502e4-99db-4ac9-9215-627dc84c2f8a` 和 `be1ed618-68f9-49a2-baf0-065f47fdc517` 均自然完成并保留，没有中断或重跑。运行核验存于 `output/playwright/local-parallel-enabled.json`；此次仅调整运行配置，未新建收费测试任务，业务源码及已批准代码快照未变。

2026-09-12 按用户要求直接在日常环境同步提交两个真实四图任务：采样确认 CLI 同时运行约 281 秒、独立会话与双向文件隔离通过。B 发布四张，A 因重做留下额外候选图而触发输出清单数量校验失败；未将整体业务验收标为通过。详细记录见 [日常环境双任务验证](DAILY-PARALLEL-VALIDATION-20260912.md)。

在仓库根目录的 Windows PowerShell 执行：

```powershell
./hengxin-smart-image/infra/start_local_codex.ps1 -Action check
./hengxin-smart-image/infra/start_local_codex.ps1 -Action start
./hengxin-smart-image/infra/start_local_codex.ps1 -Action status
./hengxin-smart-image/infra/start_local_codex.ps1 -Action fixture
```

必要时用 `-Python` 指定含 python-dotenv 的 Windows Python。`check` 检查项目及数据库/存储发布端口归属、认证、固定 CLI 版本、真实任务沙箱和数据库空闲状态，不调用模型。`start` 核对 Redis 发布端口后重启 WSL Worker，确保读取最新配置，并在该节点响应 Celery ping 后开放 API。`fixture` 恢复基础 Compose 测试执行器。`stop` 停止该项目任务入口与消费者，保留数据库和文件数据。

切换前检查包括 queued、running、uncertain 等所有非终态任务；API 完全停止后再查一次，避免检查期间新提交任务。存在未结束任务会拒绝切换。消费者切换后发生错误时 API 保持关闭，先查看 `status` 和本地服务状态；脚本不会猜测并强制回滚。

Redis 仅发布在 Windows `127.0.0.1:16388`，供本机 WSL 使用。WSL 的 systemd 服务自身不能保证发行版持续运行，脚本使用隐藏的 `wsl sleep infinity` 保活，并验证 PID、创建时间与命令身份后管理自己创建的进程，不终止整个发行版。原有手工保活进程只复用，不自动结束。

## 诊断与下一步验收

- Linux 服务：`hengxin-local-codex.service`；执行证据在 `/home/hengxin/execution/<task>/control/<round>/`。
- 本次测试收据：忽略跟踪的 `output/playwright/local-codex/live.json`。日志可能含业务素材信息，不提交原始日志和认证文件。
- 批量验收使用下述独立环境，验证双图生成、单图/整套返工、同 session resume、下载和归档。
- 并发 2、Worker 中断、取消及超时均在独立环境执行，不修改日常开发配置；任务结束恢复 1 后清理本轮环境。
- 阶段结果见 [PHASE11A-VALIDATION.md](PHASE11A-VALIDATION.md)。

## 独立真实验收入口

在仓库根目录，从 Windows 调用既有 WSL 运行时。输入目录和结果目录必须是本轮新的 Linux 路径；`--task-id` 选择已有壁纸任务，仅从中读取 Skill 包、前两张模板图及第一张替换素材，不更新原任务。

```powershell
wsl -d Ubuntu-24.04 -u hengxin -- /home/hengxin/runtime/venv/bin/python hengxin-smart-image/infra/phase11a_inputs.py --task-id <已有任务UUID> --output /home/hengxin/runtime/<本轮输入目录>
wsl -d Ubuntu-24.04 -u hengxin -- /home/hengxin/runtime/venv/bin/python hengxin-smart-image/infra/verify_phase11a_live.py --run-live --inputs /home/hengxin/runtime/<本轮输入目录> --output /home/hengxin/runtime/<本轮结果目录>
```

第二条命令会实际调用模型并消耗额度，仅在明确需要真实验收时执行。脚本创建带本轮唯一标签的 PostgreSQL、Redis、MinIO 容器与卷、随机私有端口和非 root Worker；使用自己的数据库、队列、执行目录和 API，读取既有 CLI/认证引用，不停止日常服务。成功或异常退出均核对资源身份再清理，仅保留指定目录的报告与下载图片。普通 pytest 不启动真实模型。

脚本命令与服务经 Linux subreaper 托管，父进程退出后由内核收养后代，再依据 PID 出生身份回收。必须收到监督进程确认所有子进程已回收的凭据，才允许清理声明成功；无法确认时保留错误状态和工作目录，不把轮询未发现进程当作清理证明。

`report.json` 持续记录已完成阶段、公开执行事件、会话/轮次、PID、资源采样、退出原因与最终清理状态；`status=passed` 且 `environment.cleanupComplete=true` 才代表全流程通过。图片供效果审阅，原生尺寸按本阶段已确认例外处理。报告不是原始 CLI 日志，不包含认证内容。

需要完整 PostgreSQL 回归时，针对仍在运行的本轮容器单独执行 `phase11a_regressions.py --container <hx-p11a-本轮标识-postgres> --output <报告路径>`。该脚本核对标签和私有端口，在容器内另建随机 `_test` 数据库，结束即删除；不会在真实生图任务所在的数据库执行队列集成测试。
