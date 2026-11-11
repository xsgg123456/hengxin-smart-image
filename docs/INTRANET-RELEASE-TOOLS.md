# 内网生产发布工具

## 已确认范围

复用现有发布策略及已在 .245 验证的切换逻辑，提供内网专用入口；仅允许 `hengxin-ai-245`，旧公网脚本及环境不变。应用源码统一来自明确的 Git 提交，账号、业务数据、内网配置和 Codex 运行时保留。

1. 固定 Git 提交、构建内网前端、生成文件摘要并上传独立目录；预检时业务继续运行。
2. 复用旧发布锁、原子状态保存，登记当前、上一成功版和未完成事务。记录源码、静态文件、镜像、原生解释器及数据库版本，不能仅凭镜像认定版本一致。
3. 普通发布先备份配置和数据库，再关闭接纳、排空任务、切换统一源码、验证健康及两侧 Codex 文档运行环境；失败恢复原入口。纯前端发布只切换 web。
4. 恢复使用保存的事务及原始配置；状态不明保持阻断，不强杀任务、不自动恢复旧数据库。依赖清单或迁移文件变化阻止普通发布，要求单独准备兼容的依赖/数据库升级方案，禁止覆盖正在使用的 venv。
5. 保留当前、上一成功版及全部在用/未完成发布引用。首版不自动删除源码、依赖、镜像或备份，避免误删仍被原生解释器引用的旧目录。

此次只安装发布工具、只读验证和初始化现有版本台账，不为安装工具重启业务，不调用收费模型。恢复路径使用隔离故障测试验证，不在生产制造故障。后续正式功能发布使用同一入口。

## 验收

- 参数/目标隔离、并发锁、重复执行、摘要漂移、依赖/迁移变化阻断、正常发布及失败恢复有测试。
- 内网最终安装路径可运行；实际服务源码/前端与当前清单匹配，国内/海外健康及真实 UID 运行环境检查通过。
- 工具初始化前后应用进程与容器不重启、数据容器身份不变；旧公网无操作。

## 日常使用

本地从明确 Git 提交打包（HEAD 先解析为完整提交；工作区未提交内容不会进入制品）：

```powershell
python scripts/release/intranet/package_release.py --commit HEAD --output output/release/intranet.tar.gz
scp -i ~/.ssh/hengxin_devhub_prod output/release/intranet.tar.gz root@192.168.1.245:/opt/hengxin-lan/intranet.tar.gz
```

登录内网服务器后，使用安装目录里的工具。以下 `lan-日期-提交号` 每次换一个新名称：

```sh
TOOLS=/opt/hengxin-intranet-tools/current/scripts/release/intranet
python3 -B "$TOOLS/stage.py" /opt/hengxin-lan/intranet.tar.gz --name lan-日期-提交号
python3 -B "$TOOLS/release.py" prepare --release /opt/hengxin-unified-releases/lan-日期-提交号
python3 -B "$TOOLS/release.py" deploy
python3 -B "$TOOLS/release.py" verify
```

仅前端改动在 `prepare` 增加 `--mode frontend`。它仍校验后端应用代码、锁文件和迁移未变，只切换 web。普通发布复用原生 venv、容器镜像、CLI 和全部配置；不下载或升级运行时。

- `status`：查看当前前后端提交、有无上一成功版、有无未完成事务。
- `recover`：发布中断后恢复该事务原版本并验证；失败时保留事务，不强行解除门禁。自动恢复成功但 deploy 报错时，也用此命令核验并清除 pending。
- `rollback`：回到最近一次成功发布之前的版本；同样排空并验证。完成后不提供来回翻转，重新发版走新 prepare。
- `cancel`：取消尚未开始切换的候选，核对当前服务未变后清除 pending；不删除候选或备份。
- `init`：首次实查现有线上版本后登记。重复执行只核对，不覆盖已有台账。

发布使用旧 `release-retention-state.py` 的进程锁和原子写入，内网台账单独位于 `/var/lib/hengxin-release/intranet.json`，不改变旧镜像台账格式。事务及备份位于同目录 `intranet-transactions/`，权限 0700/0600；其中执行环境可能含凭据，不输出、不提交 Git。

当前业务来源可能分别为 backend、frontend 两个发布目录，台账分别记录；完整发布统一到一个目录。旧源码目录可能仍包含在用 venv，全部保留，不运行旧公网的镜像清理入口。初次登记没有虚构“上一成功版”；第一次通过本入口正式发布后才建立 previous。

后端普通发布备份国内/海外 PostgreSQL 并校验归档，同时保存账号和配置。此备份供人工灾难恢复参考，回退代码不自动倒灌数据库；上传文件及对象存储沿用原数据卷，不在每次发布复制全量素材。定时备份与灾难恢复演练不是本次新增范围。

新依赖、新系统包、CLI 升级或数据库迁移需另行准备升级；普通发布发现锁文件、迁移内容变化会提前拒绝。已有基线清单无 runtime_inputs 时只核对已安装二进制/依赖与后端输入；新清单之间还比较 Codex 部署输入。拒绝不是自动升级失败，也不能靠删台账绕过。

## 实施验证

2026-11-11 已安装并初始化：`/opt/hengxin-intranet-tools/current` 指向 `releases/56b6cdbebd619d9d`，13 个安装文件逐项 SHA256 一致。台账登记现有业务提交 `ea905adcc3786e8faf590d108d15bd61a6bdb0d2`（后续 `ca186c8` 未改变前后端业务源码），previous 为空、pending 为空。此次没有重新发布业务。

- 本地独立审查最终回归：`79 passed, 7 subtests passed`，11 个 Python 文件编译通过。审查记录：[完整审查](reviews/INTRANET-RELEASE-TOOLS-REVIEW-20261111.md)、[安装适配复核](reviews/INTRANET-RELEASE-BINDING-REVIEW-20261111.md)。最终批准快照 `15f14f9282bd58afa0c22eb836c62e1f4f80cfc0ea3c0f680551363f022a4d23`。
- 用当前 Git 提交 `ca186c8de0412206493eba6f31f2e11da5b66b00` 实际打包：冻结锁安装复用 782 个缓存；`vue-tsc --noEmit` 通过；Vite 52.80 秒；包 5,931,649 字节、421 个后端文件及 695 个前端文件。全部摘要及 renderer 0755 核验通过，包 SHA256 为 `4bbc891767bbac6a2bb1b4f7bbe1017892a6f5a80b2f831c93fc85dac20b37f7`。完整/纯前端模式均与现有发布的真实依赖和 app 清单兼容。
- 从内网最终安装路径，用实际 worker 解释器执行工具全套测试：`79 passed, 7 subtests passed in 2.44s`。随后实际 `init` 和 `verify` 均成功；两次均以国内/海外原进程 UID、GID、环境和解释器运行 `app.execution.runtime_check`，返回两侧 `RUNTIME_OK`。检查覆盖命令沙箱、脚本及文档 PDF 转换，不收费调用模型。
- 全过程 7 个原生服务的 PID/启动时间、16 个应用及数据容器的 ID/StartedAt 完全未变。再次核对：15 个应用服务的 353 个 app 文件与清单一致、695 个当前前端文件一致；25 个账号/配置文件摘要不变，7 个数据容器身份不变，国内/海外/身份接口 HTTP 200。
- 首次只读 init 暴露网页仅绑定 LAN 地址：已将核验地址改为真实 `192.168.1.245:8080`；同时按既有迁移源码分别读取国内 `alembic_version` 和海外 `overseas_alembic_version`，追加回归并重新审查。首次失败未写台账或激活入口，期间业务未重启。

本地原始证据位于 Git 忽略的 `output/intranet-tools/`：`verification.log`、`postcheck-final.json`、`installation*.json`、`package/build-verified.log` 和验证包。服务器 `tools-manifest.json` 保存工具摘要，私有 `intranet.json` 保存运行版本与依赖/schema 摘要。

边界：恢复及失败路径通过隔离故障测试；此次未在生产制造停机/回退，也未重跑收费模型任务。实际 PPT 和图片模型链路沿用同日 [统一发布验收](INTRANET-UNIFIED-RELEASE-20261111.md) 的证据，业务和 CLI 版本未变。
