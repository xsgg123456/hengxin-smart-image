# 内网 Codex CLI 稳定版升级

用户授权：将内网服务器 Codex CLI 升级到官方当前最新稳定版。仅操作 `192.168.1.245`，不修改旧公网生产、业务源码、模型选择或账号授权数据。

2026-11-11 核对官方更新日志（https://learn.chatgpt.com/docs/changelog?type=codex-cli）及 npm `@openai/codex` 的 `latest`：稳定版为 `0.167.1`，官方发布日期 2026-11-10。实际国内、海外 worker 当前均为 `0.162.1`。

## 执行与验收顺序

1. 核对实际服务进程、环境文件、账号服务命令行和二进制引用；官方 Linux x64 包下载后校验 npm SHA-512 完整性。完成标准：确定升级范围与完整软件包布局。
2. 新版独立安装到版本目录，以两个实际服务身份验证版本、CLI 参数及项目 Bubblewrap 隔离启动；保留旧版。完成标准：安装路径可用，辅助进程来自同版软件包。
3. 暂停两套 Celery 消费，检查 active/reserved/scheduled 与数据库在途状态；确认账号管理无在途登录/检测子进程。完成标准：空闲得到明确证据，未知状态拒绝切换并恢复消费。
4. 备份并精确更新 `.245` 的持久化版本引用，重启必要服务；核对实际运行环境、账号服务命令行、队列恢复与 HTTP 健康。失败恢复配置和服务。完成标准：两业务实际执行路径均为 0.167.1，旧版和配置备份可回退。
5. 记录结果。版本与隔离启动测试不等于付费生图验收；不为了升级更换或重新授权账号。

脚本 `APPLIED` 只证明原生执行服务切换。主 Agent 必须随后实查 HTTP 首页、国内和海外 ready 接口、容器运行状态、授权文件摘要与实际版本；任一项异常先定位，若与升级有关则重新排空并按私有备份恢复，不在状态不明时强停。只有后置验收也通过才宣称完成。

## 已识别引用

- `/etc/hengxin-lan`：国内 worker、海外 worker、retention、domestic-deletions、overseas-outbox 的环境文件；账号服务的部署模板。
- `/etc/systemd/system/hengxin-codex-accounts.service`：`--binary` 参数。
- `/opt/hengxin-lan/native-env.json`：用于后续部署的环境清单，需同步固定版本，避免重部署退回旧版。
- 旧运行时 `/opt/hengxin-runtime/codex-0.162.1` 保留；新版本不得覆盖旧文件。

## 已完成结果

2026-11-11 已完成 `.245` 升级，切换脚本输出 `APPLIED 0.167.1`，退出 0。最终候选 `67dddc7f3eb5042e3d6f39dd1652025062dbde085103104f8e04c33c758b2122` 经 [两阶段独立复核](reviews/INTRANET-CODEX-UPGRADE-RECHECK-20261111.md) 并登记批准。初审发现的回退账号排空、恢复队列异常隔离均已修复，8 组本地故障注入通过。

- 官方 Linux x64 npm 包下载 173,799,203 字节，SHA-512 与 registry 元数据一致；保留完整 vendor 布局。正式二进制为 `/opt/hengxin-runtime/codex-0.167.1/bin/codex`，SHA-256 `dd5bfdf19d794dcc6fb482d2d5a2d9fb31d11f6caa44b303bb72890d461e8a02`；配套 helper 同版。
- 切换时两消费者已暂停，active/reserved/scheduled 与数据库在途计数全部 0；账号服务无在途线程、子进程及授权临时目录。没有强停生成任务。
- 新运行中的国内、海外 worker 环境均为 `0.167.1`，账号管理进程 `--binary` 为新版路径。retention、deletions、overseas-outbox 的持久化环境与实际运行环境同步；六项服务重启后 active/enabled，原凭据 broker 继续使用原 PID 3586。
- 从更新后的 worker 实际进程环境读取路径，分别以 `codex`、`hengxin-overseas` 真实 UID 执行：直接 `--version`、项目 Bubblewrap 内 `--version`/`exec --help`、同版 helper `--help` 均退出 0，版本均 `codex-cli 0.167.1`。
- 两个消费队列 `celery`、`overseas.cli` 已恢复。账号控制与 worker socket 恢复 0660。两项既有账号持久化文件 SHA-256 前后相同；未复制或重置授权。
- 切换后 HTTP 首页、国内与海外 ready 均 200，环境响应头为 `lan-245`；17 个运行容器 ID 前后完全相同。
- 旧版目录仍保留。远端私有证据目录 `/opt/hengxin-runtime/codex-upgrade-20261111`，`switch/paths.json` 对应 `switch/0` 至 `switch/7` 为原配置备份；`switch.log`、`switch/applied.json`、`verified.json` 记录执行与后置验收。

升级只新增运维脚本和文档，没有修改业务源码或提交/推送 Git。未调用付费生成或重新授权账号；本次 CLI 升级完成不代表此前账号连接问题已经解决。开机启动配置已持久化，本轮未整机重启实测。

## 后续验收状态

后续[运行时修复](INTRANET-CODEX-RUNTIME-FIX-20261111.md)补齐了该版本所需内层沙箱与文档工具，完成实际命令和模型调用验证。升级阶段仅--version/--help通过的证据范围保留，不再当作完整工具验收。
