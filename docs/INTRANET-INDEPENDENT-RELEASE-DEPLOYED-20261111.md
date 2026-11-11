# 内网独立发布最终验收 · 2026-11-11

已完成内网 `192.168.1.245:8080` 拆分、重新部署、正式入口验收、旧发布物清理及清理后复核。复用原 release / engine / catalog / GC；没有另建一套发布系统。最终业务包来自 Git `fccbab5ba496cb2205d8a95172aa1b47786d7d7a`，工具入口 `/opt/hengxin-intranet-tools/current` 指向 `releases/210827f3bf7b164c`。

## 当前发布规则

国内、国外各自选择 scope 发布或回退，另一侧服务和成功记录不变。每组保留本次、上次成功的完整状态；成功验证后自动回收更早且无人引用的源码、镜像、上传包及发布附带备份。正在使用的解释器、依赖、容器/进程/挂载引用和全部组的两版都保护；业务数据库、图片、素材和账号数据不作为发布垃圾。

前端分 `/domestic/`、`/overseas/`、`/shared/`，同源登录与原根 hash 链接保留。普通后端发布只排空目标侧，排空失败退出恢复接入，不强杀任务；独立回退以当前全站配置合成目标变更，不倒灌数据库。共享后端、跨业务公共代码、依赖和 schema 升级仍明确拒绝，须另行联合维护；共享前端可单独发布。

| 组 | 当前前端 | 上一成功前端 | 两版共用后端 |
| --- | --- | --- | --- |
| domestic | `fccbab5` | `6501351` | `0a1cee0` |
| overseas | `fccbab5` | `6501351` | `0a1cee0` |
| shared | `fccbab5` | `6501351` | `0a1cee0` |

首次 previous 是迁移前实际运行的旧版，不把失败迁移算成功。每组两个完整运行状态不等于全机两个文件夹或两个 Docker 镜像。旧网关 `/assets/`、共同后端和原生 venv 的真实引用仍受保护。兼容资源不逐代递归复制；回退后的静态服务只读挂载切换前前端用于旧页面 assets，下一次切换替换引用。

## 真实生产结果

- 原 **17 个容器的 ID/StartedAt、7 个原生服务的 PID/启动时间均与迁移前相同**。仅新增 domestic-ui / overseas-ui / shared-ui 三个静态服务，现有容器数 20；原网关只 reload，边缘入口未重启。
- 仍为 **9 个镜像**，全部具有在用容器引用；三套静态服务复用现有 nginx 镜像，没有新增镜像。
- 国内/海外/共享后端来源仍是 `0a1cee0`，实际 app 文件摘要、原生 cwd/解释器/已安装包、运行二进制、数据容器身份及 schema 校验通过；已登记原配置除预期 compose/nginx 切换外不变。
- 三条任务队列前后均正确绑定：celery / overseas.cli / api_image_edits；两次只读观测 active/reserved/scheduled/database/broker 都为 0。没有暂停队列或停止业务 worker，没有修改业务数据库或文件存储。
- 正式 Chrome 验收根入口、三个裸入口及国内/海外旧 hash 深链共 6 个入口，未登录时均正常呈现共享登录；pageErrors=[]，failedPageAssets=[]。三 scope 实际构建图和入口脚本均正确，缺失 asset 为 404，不返回 SPA HTML。最终截图 `output/intranet-independent-release/after-login.png` 已目视核对，布局与原入口一致。
- 台账 version 2，无 pending，migration_pending=false；清理后再次 verify 成功。日常回退使用 `release.py rollback --scope domestic|overseas`；迁移整体 rollback 只用于首次验收未通过的恢复，不作为后续日常回退方式。

## 首次失败与处理（未计入成功版本）

第一次 `2b7b282` 包在正式验收发现裸地址白屏：仅 hash 的 location.replace 不重新加载文档，却跳过应用启动。立即使用原迁移回退恢复旧入口，只移除新增的三个 UI 容器，原 17 容器/7 原生进程不变。修复 6 行启动判断，补 24 项冷启动浏览器矩阵，独立复审通过后提交 `fccbab5`，重新打包部署；本记录只把最终重新验收通过的版本记成功。

失败的三个源码目录、三个上传包及迁移 work 已通过原 GC 回收，净回收 37,249,024 字节，镜像和业务数据未删；失败 marker 仅保留小型归档证据。原始记录在 `output/intranet-independent-release/first-attempt/` 与 `discard-failed-attempt.log`。

## 测试和审查证据

- Python/Linux：292 passed、9 subtests，无跳过；真实交错代码 A→海外 X→国内 C→国内回退保持 X、scope 排空/恢复、全部组两版引用、真实 POSIX GC 均覆盖。Windows 对应 201 passed、72 POSIX-only skipped；不能把 Windows 跳过当通过。
- 前端：546/546 单测、typecheck、三 scope 构建通过。最终 Git 正式包再次验证三个 module graph 隔离及 31 个真实 Chromium 浏览器场景（24 冷启动 + 原 7 身份/跳转回归）。身份接口使用隔离 fixture，不创建生产业务数据。
- 真实隔离 nginx：scope/legacy assets、4 条 API 路径及 query、回退前版本资源 fallback、缺失资源404、替换国内静态服务而国外和网关不重启均通过。
- Docker GC：真实删除旧测试镜像，保护上一版/停止容器引用/未知镜像，测试资源归零。一次并发运行两个 Docker smoke 引起全量容器断言竞态，随后串行重跑通过；没有把失败记 PASS。
- 实际生产执行过首次静态迁移的回退与重新部署；没有在生产制造后端故障、插入模型任务或调用付费模型。后端故障与交错回退在隔离引擎测试中验证，生产做只读运行核验。
- 整体实现批准快照 `ec1d678644a57928bea32bea22a34aa705d8194cf98890ba14a7814d4e90d85a`，见 [第三轮审查](INTRANET-INDEPENDENT-RELEASE-REVIEW3-20261111.md)。裸入口修复最终批准快照 `d3a967332ae14940e06e774849782af11917f8c7bc2e0902deee6d698edc3ce1`，见 [修复审查](INTRANET-INDEPENDENT-RELEASE-BARE-ENTRY-REVIEW-20261111.md)。
- 依赖审计 critical=0；仍有既有 high=39 / moderate=35 / low=5，本次没有更改依赖或锁文件，不宣称零漏洞。正式包文件/摘要/权限及私有文件、密钥模式、前端开发者路径扫描通过。

## 清理结果与口径

最终清理只删除失去保留引用的旧事务 `/var/lib/hengxin-release/intranet-transactions/lan-20261111-0a1cee0-1794391664007779451`（含该旧发布附带备份），源码和镜像本次没有可删除候选。三个类别 status 均 complete、errors 均为空，当前/上一版与在用依赖保留。

同范围 `release-sources + lan-root + ledger + Docker LayersSize`：清理前 3,697,884,309 字节，清理后 3,697,089,685 字节，扣除回执变化净释放 **794,624 字节**。这不是整个迁移的净释放声明；首次拆分新增了三组独立包及源码。另已删除本任务的三套未启用中间工具和四套 Linux 测试目录，独立口径释放 139,665,408 字节，不把它混作生产旧版本清理量。

## 最终上传包

| scope | 字节 | SHA256 |
| --- | ---: | --- |
| domestic | 5498108 | `14f3cf932f4bf800f2f510a687a25078bb407bf599083798735e2e5525dcdfc8` |
| overseas | 2624313 | `9f474780f4dce544be7bda32b992fcf97faaa1bff561aee2f98e5d2245ea67b5` |
| shared | 2025225 | `87f450c50d461d703a495e8d556b2c40fd5214da4220ac8b3c523aae4552e96c` |

原始证据（Git 忽略的本地工作目录）：`output/intranet-independent-release/verify.json`、`production-browser.log`、`cleanup-report.json`、`checks-210827f3bf7b164c.log`、`nginx-smoke.log`、`retry/packaged-browser.log`、`retry/packaged-artifacts.log`、`test-copy-cleanup.log`。服务器私有台账及清理回执在 `/var/lib/hengxin-release/`；工具逐文件摘要在安装目录 `tools-manifest.json`。日常命令见 [发布工具说明](INTRANET-RELEASE-TOOLS.md)。
