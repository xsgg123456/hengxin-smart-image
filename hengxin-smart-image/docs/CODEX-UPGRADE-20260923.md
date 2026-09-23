# 2026-09-23 生产 Codex CLI 升级

## 目标与范围

用户授权生产服务器 CLI 入口与项目执行器统一到官方最新稳定版0.156.1。npm latest 与 GitHub rust-v0.156.1 均于本次检查确认；GitHub published_at 为2026-09-23T02:41:36Z。

生产使用显式 CODEX_VERSION 和 CODEX_BINARY。后端0.153.4缺省及本地WSL示例继续兼容既有本地环境，不代表生产运行版本，本次不升级用户本地WSL。

## 执行与验收

1. 校验官方 Linux musl 发布包，安装到 root 拥有的 `/opt/hengxin-runtime/codex-0.156.1`，保留旧版。
2. 精确路径 AppArmor 许可；通过部署代码的 prepare_workspace/sandbox_command 验证认证、gpt-6-astra/high 调用、工具执行及会话续接。
3. 确认生产 Worker 没有活动/预取任务后，备份并切换生产环境配置、服务器 CLI 入口，重启该 Worker。
4. 验证运行中 Worker 配置、版本及就绪状态。测试使用独立临时工作区，不创建业务图片任务。

## 认证修复

检查时 `/home/codex/auth/auth.json` 缺失，而新账号已登录在该用户默认认证目录。已在服务器内部同步凭证并设置 codex 所有、0600；凭证没有传回本地或加入仓库。升级前0.153.4项目实际沙箱调用返回 HX_CODEX_OK。

## 发布包

来源：https://github.com/openai/codex/releases/tag/rust-v0.156.1

`codex-package-x86_64-unknown-linux-musl.tar.gz` SHA256：`8b711520beddf385467b8da4d2c93736637c6ba1e46811cf0d8606b7c490b6f6`。

## 结果

已完成切换前验证：

- 完整官方发布包 SHA256 匹配；安装 root 拥有的版本目录，入口指向包内 bin，包含同版本 helper 和官方资源。
- 新增 `/etc/apparmor.d/hengxin-codex-0.156.1`，仅许可 `/opt/hengxin-runtime/codex-0.156.1/bin/codex` 的 userns，不更改全局限制。
- 生产部署的 prepare_workspace/sandbox_command、gpt-6-astra/high、workspace-write：0.153.4创建会话，0.156.1续接同一ID，真实工具写入再读取测试文件，全部exit 0且turn.completed。0.156.1新会话同样通过。
- `pytest tests/test_codex_runner.py tests/test_execution_workspace.py tests/test_management_monitor.py -q`：57 passed、1 skipped（平台限定测试）、2项既有弃用warning；Linux真实沙箱另行验证通过。
- `docker compose --env-file .env.vps.example -f compose.yaml config --format json`：CODEX_BINARY与CODEX_VERSION均为0.156.1。验证进程先清除宿主继承的CODEX_VERSION，否则宿主变量会优先覆盖env文件。
- 生产Celery active/reserved/scheduled均0。正式切换前再次停止接收新任务并检查空闲。

生产切换完成：

- 暂停原Worker消费并复核active/reserved/scheduled为0后重启专用服务；队列恢复由服务正常启动接管。
- `/home/codex/.local/bin/codex`、`/usr/local/bin/codex`均指向固定root维护目录并返回 `codex-cli 0.156.1`。
- `/etc/hengxin-smart-image/worker.env`及生产Compose `.env`的CODEX_VERSION/CODEX_BINARY已同步；运行中Worker PID 686736读取版本0.156.1及对应新路径。
- 实际数据库健康心跳：state=ready、cliVersion=0.156.1、cli/isolation/authenticationConfigured均true，原并发5保持不变。
- 使用运行中Worker环境再次执行项目真实沙箱模型调用：LIVE_PROJECT_MODEL=PASS。服务器CLI原生模型及shell工具调用：NATIVE_CLI_MODEL_AND_SHELL=PASS。最终FINAL_VERIFICATION=PASS。
- 本次没有创建业务图片任务，也没有重新验证整套图片视觉效果。既有任务私有认证副本未批量替换，历史任务如有旧账号认证失败需按对应任务单独处理。

## 回退

服务器备份目录 `/var/backups/hengxin-codex-20260923T032904Z`（0700）保留升级前worker.env、Compose .env、compose.yaml和两个入口链接目标。回退时先暂停消费并确认空闲，再恢复配置和链接、重启专用Worker；旧0.153.4二进制与原沙箱规则仍在。新版精确路径规则可在不再有新版进程后卸载。凭证不写入本记录。
