# 国内与海外单轮 CLI 日志专项发布

本次分别切换国内和海外业务后端。每组短时停止接单、排空并重新启动本组服务。先发布国内，恢复接单并确认健康后再发布海外。两组使用各自原有镜像、依赖、数据卷及数据库版本。三个前端、共享账号服务保持发布前的挂载和进程。

## 基线和候选

生产主机为 `hengxin-prod` 指向的 `hengxin-ai-245`，入口为 `192.168.1.245:8080`。准备时正式 `verify` 通过，台账空闲，工具版本为 `b056e0ae4da64d89`。应用补丁来源为主线提交 `406eaf4abec3c6f8715d3e90e26d25d33ca218ae`。

| 业务 | 发布前后端 | 固定候选后端 | 继续使用的前端 | 实际数据库 |
| --- | --- | --- | --- | --- |
| 国内 | `009a1808f5c4` | `2d42d0d782429453f86ba31ba22f50e0a32c0d4d` | `009a1808f5c4` | `0046` |
| 海外 | `faab6d0434dc` | `476d7c610a303a79b84e9e88ac87a0b4773eb623` | `7b6caf1d98d6` | `overseas_0029` |

共享前端为 `faab6d0434dc`，共享后端为 `2bc8acc7ecf4`。国内基线早于海外反馈和创作工具集开发。打包脚本在独立 Git 对象目录读取目标业务的生产提交，对清单中的业务代码应用主线日志补丁，校验完整变更路径，并以固定作者、日期和消息重现候选提交。仓库的分支和索引均保持原状。

两组均包含实际调用的 CLI 执行和工作台公共模块。国内加入国内会话和 API 生图处理，海外加入海外工作台人工恢复入口。共享账号探针继续运行现有共享版本。生产门禁绑定各自的新旧完整提交和后端文件清单摘要，核对暂存登记、前端版本、schema、打包来源、运行时输入及依赖。国内和海外基线分别有 498 和 509 个后端文件。

## 打包与逐组发布

1. 使用通过独立审查的工具提交，在仓库根目录分别运行下列命令。它们复用 `package_release.py` 的 Git 归档、锁文件核验、前端构建和打包流程。记录两个压缩包的 SHA256，复核每个成员、源码清单并从包中运行对应业务的超 256 MiB 交付测试。

   ```powershell
   python scripts/release/intranet/cli_log_candidate.py --scope domestic --output output/cli-log-maint-20261121/lan-domestic-20261121-cli-logs-2d42d0d78242.tar.gz
   python scripts/release/intranet/cli_log_candidate.py --scope overseas --output output/cli-log-maint-20261121/lan-overseas-20261121-cli-logs-476d7c610a30.tar.gz
   ```

2. 从已审工具提交取 `release.py`、`release_cli.py`、`cli_log_maintenance.py` 和 `test_cli_log_maintenance.py` 安装至版本化工具目录。安装锁内核实旧指针、旧清单及全部文件摘要，确认无待处理事务。用宿主只读挂载和独立临时目录跑安装后的工具测试，验证台账和候选工具摘要，再原子切换工具指针。
3. 使用各自的新文件名上传至 `/opt/hengxin-lan/`，核对远端 SHA256。服务器命令使用 `/opt/hengxin-intranet-tools/current/scripts/release/intranet` 中的正式工具。每组以自己的 scope 和 name 运行以下命令。

   ```sh
   TOOLS=/opt/hengxin-intranet-tools/current/scripts/release/intranet
   python3 -B "$TOOLS/stage.py" "/opt/hengxin-lan/$name.tar.gz" --name "$name"
   python3 -B "$TOOLS/release.py" prepare-logs --scope "$scope" --release "/opt/hengxin-unified-releases/$name"
   python3 -B "$TOOLS/release.py" deploy --scope "$scope"
   python3 -B "$TOOLS/release.py" verify
   python3 -B "$TOOLS/release.py" status
   ```

4. 每组核实当前和上一成功后端、前端挂载及首页摘要、schema 和三个就绪入口。对照操作前的容器 ID、启动时间和 systemd 进程信息核验其他组、静态服务及数据服务。台账须清空 pending，目标事务须记录 `mode=backend` 和 `maintenance=cli-logs-20261121`。检查两版保留、自动清理回执及同口径净释放字节数。

## 中断和回退

仅准备后可运行 `release.py cancel --scope <组>`。排空超时或切换失败后，先看 `status`，使用 `release.py recover --scope <组>` 完成恢复、复核接单和原组版本。事务成功后需回退时用 `release.py rollback --scope <组>`，再运行 `verify`。回退使用当时的全局配置和该组自己的上一成功版本，保留另一组此后发布的版本；本次前后 schema 相同，全部数据沿用现状。若要回退两组，逐组执行和复核。

## 生产验收

2026-11-21 两组均已完成发布。应用来源为 `406eaf4abec3`，已审发布工具提交为 `ec3a47106eff`，安装版本为 `df22ab05060698b0`。正式工具在安装目录通过 615 项测试和 21 个子测试，11 项因环境条件跳过。

| 业务 | 当前后端 | 上一成功后端 | 发布包 SHA256 |
| --- | --- | --- | --- |
| 国内 | `2d42d0d78242` | `009a1808f5c4` | `899c44f407d8fd8bb04a3666e6ef877b479d3c6092e1e4ee8d7f67e9075a9a0b` |
| 海外 | `476d7c610a30` | `faab6d0434dc` | `bb01b35ac2c7bf67445e3b94c319870a964a00bea2ac8f6cb30dfb7ff5259112` |

- 国内首次切换停在排空阶段。当时仍有一条生产任务在运行。正式 recover 已确认原版本、清空 pending，国内、海外与身份接口均返回 200。待该任务自然结束，复用已暂存包重新 prepare、deploy 并通过 verify。随后海外通过同一套分组检查。
- 从两个实际包解出的后端在隔离环境分别完成超过 256 MiB 原始输出后的单轮图片交付。国内核对数据库和对象字节，海外另通过业务接口下载比对；重复调度只执行一次。前端类型检查通过，616 项前端测试通过。
- 在两组生产 Worker 的真实身份、解释器、当前源码目录下，各用无网络临时目录模拟 269,532,459 字节 CLI 输出，之后才发送最终图片引用。两组进程退出码均为 0，详细日志头为 224 字节，语义事件流为 393 字节；国内完成快照收取、海外完成文件收取，图片字节均匹配。本次探针只用合成数据，原故障任务未重跑。
- 两组正式 verify 和 status 均通过，pending 为空。三组首页摘要与发布前一致，国内、海外就绪接口与共享身份接口均为 200。按次核对容器 ID 和启动时间、原生服务 PID 和启动时间，仅切换目标后端服务。国内 schema 为 0046，海外为 overseas_0029。
- 两次正式 deploy 的自动清理均为 complete。按各自 LAN_CLEANUP 的 before_bytes 与 after_bytes，国内从 3,939,208,341 降到 3,930,004,629 字节，净释放 9,203,712 字节；海外从 3,946,884,245 降到 3,945,774,229 字节，净释放 1,110,016 字节。上述两个上一成功版本均由生产台账保留，可按组回退。
