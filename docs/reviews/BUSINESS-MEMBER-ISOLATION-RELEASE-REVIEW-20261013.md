# 国内与海外成员隔离发布：独立增量审查

- 日期：2026-10-13；reviewer：独立 code-reviewer。
- candidateId：`99c8fa9dd583842ba26d3a4ee75e0b7c3ac7ba195be4aa359ec50fb87596916b`。
- 基线 HEAD：`0f653b9e2850a201af90dfe61247dbf80959914d`。
- **Stage 1：PASS；Stage 2：PASS。** 本轮未发现须修复的 HIGH / MEDIUM 问题。
- 该结论批准源码与发布控制器，不表示生产安装、迁移、流量恢复或四人清理已执行。

## 范围与快照

已读取 AGENTS、code-review skill、reviewer 角色和 `docs/HARNESS-REVIEW.md`。源合同为 `Product-Spec.md:1081`、`DEV-PLAN.md:1`、`Product-Spec-CHANGELOG.md:1` 和 `docs/BUSINESS-MEMBER-ISOLATION-RELEASE-20261013.md:3`。后者第5行的后续明确授权限定四条已展示的海外空档案；其余人员不在删除范围内。

本轮增量共10个文件：`frontend/package.json`，`scripts/release/member-release-{deploy,runtime,drain,backup,verify,tests,topology-tests}.py`，`scripts/release/package-overseas.py`，`scripts/release/test_package_overseas.py`。下文 `frontend/`、`backend/` 均相对 `hengxin-smart-image/`；其余路径相对仓库根目录。

独立比较 `output/member-review-file-inventory.json` 的114个旧 feature 文件，当前摘要全部与旧审查清单一致。原快照 `a527f5b1b6eef7553b8d6699408ad6ac980c22a580eaa2831d197fbf575e0bd1` 的完整业务逐条矩阵、双库HTTP、浏览器与维护工具结论继续由 `docs/reviews/BUSINESS-MEMBER-ISOLATION-REVIEW-20261013.md:25`、`:90`、`:104` 覆盖，本轮没有把未复跑的2151项后端/335项前端测试说成重新执行。

审查开始、独立 build 完成后及报告落盘后运行 `review-status`，当前编号均为本报告 candidateId；差异文件仅上述10项。报告为普通Markdown，不改变代码快照。不修改产品代码、不提交、不写 `.needs-review`、不自行登记 approval。

已追加读取主Agent的只读schema查询原文 `output/member-schema-preflight.py:3` 及结果 `output/member-schema-preflight.json:1`：国内52张、海外32张用户表均在public，无其它用户schema表。因此下述public逐表指纹覆盖本次生产全部用户表（迁移版本表按明确版本单独校验）。这不是对将来新增非public业务表的保证；拓扑变化后须重新核对范围。

## Stage 1：Spec Compliance — PASS

| 合同要求 | 结论与证据 |
|---|---|
| 发布前实查、按稳定身份核对，生产名单不入Git | ✅ `docs/BUSINESS-MEMBER-ISOLATION-RELEASE-20261013.md:19` 记载国内28/海外6的基线；已读取忽略目录 `output/member-production-before.json` 与 `output/member-queue-preflight.json`：三个worker的active/reserved/scheduled/broker/unacked以及两业务pending和variants均为0。它们是主Agent实查证据，本reviewer没有连接生产；controller仍在prepare/deploy重新探测，不将旧预检当永久空闲凭据（`member-release-runtime.py:173`、`member-release-drain.py:81`）。 |
| 固定0.2.29、国内0028、海外0014与共享identity同批发布 | ✅ `frontend/package.json:3` 仅改版本；`package-overseas.py:16`、`:44`、`:178` 固定版本及两迁移，`member-release-runtime.py:87` 再校验manifest；`member-release-deploy.py:23` 两库迁移后按identity/domestic/overseas启动同一镜像。 |
| 从已审、已提交源码打包，逐文件摘要和隐私检查 | ✅ `package-overseas.py:79`、`:152` 要求全部tracked修改已提交及review approved，从HEAD读取源码，再比本地；`:178` 写commit/candidate/文件SHA256，`:182` 再查无漂移；`:186` 归档及落盘回读逐字节校验。独立检查600个源码候选及843个生产资源通过。 |
| 运行模块/维护工具闭包完整 | ✅ `package-overseas.py:26`、`:30`、`:56` 必含5个新发布模块、旧helper、两迁移、共享identity和8个维护模块；`:60` 排除隐藏文件、其它维护文件及输出目录。独立将选中的发布helper复制到临时目录导入成功；`test_package_overseas.py:140` 在临时目录真实启动两维护CLI的`--help`。 |
| 实际镜像隔离安装测试、与manifest同源码 | ✅ `member-release-deploy.py:95` 先校验源包；build仅调用 `overseas-deploy.py:25`，同函数先构建、无网逐文件hash、再无网pytest，成功才写INSTALL_TEST_IMAGE_ID。`member-release-runtime.py:96` 对prepare/deploy钉住该镜像ID。生产镜像安装测试本轮尚未执行，不能由本地71项替代。 |
| 保留三套Compose配置、所有挂载、共享14个Skill，prepare不重启 | ✅ `member-release-runtime.py:51` 按live labels读取原项目/路径/env/cwd并记录容器、挂载、配置hash及native文件；`:119` 比对现运行配置；`:179` 只叠加image/build，`:109` 拒绝其它参数变化。prepare仅创建新native目录、复用相同依赖、探测并落盘，未stop/start。`:192` 与 `overseas-skills-runtime.py:96` 验证14包/181文件、API与非root worker及sandbox同目录、只读挂载，不重新安装Skill。 |
| 禁止拓扑漂移后切换 | ✅ `member-release-deploy.py:49` 拒绝上次已开始迁移的重放；`:55` 比对完整拓扑；`:56` 再核Compose配置；`:62` 在生产变更前验证edge布局。测试 `member-release-tests.py:95`、`:103` 确认这些失败不发生cutover。 |
| 关闭三个API；outbox保留到队列排空 | ✅ `member-release-runtime.py:198` 为三业务API加`^~` 503，覆盖原国内SSE regex；`:219` 逐一停API，即使某个停止失败仍尝试另外两个。`member-release-deploy.py:65` 先确认公开503；`member-release-drain.py:95` 第一次等待全部空闲之前不停止outbox。 |
| 两轮DB/worker/broker/variant空闲才停执行者；未知不强停 | ✅ `member-release-drain.py:13` 检查active/reserved/scheduled、精确消费队列、所有优先级broker长度和unacked；`:37` 使用实际进程环境并确认运行/配置cwd一致。`:81` 每次要求连续两次空闲；`:97` 首次完成才停三个outbox，`:101` 再等两次，之后才停executors。超时/无应答均抛错。`member-release-tests.py:115`、`:135`、`:148` 覆盖忙碌、未知、多个node及晚到消息。 |
| 两库完整备份、配置/静态入口/native指针、真实无网恢复 | ✅ `member-release-backup.py:77` 保存原Compose、env、静态入口、edge、unit/dropin/env及指针；`:102` 真实pg_dump和pg_restore list；`:114` 使用原数据库镜像启动network none临时库，真实restore并比逐行指纹，仅清理由本次成功创建的容器。`:142` 等executors停止后备份，前后指纹一致才写COMPLETE。reviewer独立本地PG17真实执行两库dump/restore，均成功，见原始输出。 |
| 迁移保留原成员、身份、授权及全部既有业务行，仅增加分类 | ✅ `member-release-backup.py:30` 对public每张非版本表按完整jsonb行排序hash；只剔除新增directory_state，再于`:57` 单独逐行验证pending→legacy、其它→enrolled；`:44` 检查旧表仍在、旧行hash相同、仅预期新表且为空。`member-release-deploy.py:28` 在所有writer停止时执行。独立执行两份真实迁移的SQL后PASS，注入旧成员字段变动即拒绝。 |
| 三API/七容器及三native的源码、挂载、队列、鉴权与公开产物验收 | ✅ `member-release-verify.py:20` 比镜像ID、各容器完整backend hash及挂载；`:34` 要求其它资源仍为原ID且运行；`:43` 验证native实际PID cwd和backend hash；`:70` 核迁移、队列并发、健康与Skill；`:104` 本机代理及匿名401/403；`:86` 校验前端全文件hash及公开index/入口资源字节。线上页面视觉与真实人员目录须在发布后执行，未在本地报告标完成。 |
| 失败全入口关闭，不降库、不回旧混入逻辑、不强停未知executor | ✅ `member-release-deploy.py:78` 捕获切换/开流量后任意失败时再次关闭edge并停止全部API；没有downgrade、旧源码切回或失败处理强停executor。17个阶段故障注入实际走controller异常路径，断言最终close+stop_apis、无回退/强停及无完成标记（`member-release-tests.py:70`）。 |
| 四条具体人员清理后置、重新audit/模拟/恢复包/逐条应用 | ✅ 发布controller不清理人员（`member-release-deploy.py:76` 明记historicalCleanup=False）；现有维护工具 `scripts/maintenance/member_reconcile.py:64` 锁内复核业务指纹、完整expected及引用，`:81` 先持久化恢复再删除，新引用跳过。调用编排见下方独立运行时范围；生产应用尚未执行。 |
| 引导真实性/UI一致性/Spec漂移 | ✅ 本增量无新页面、文案或交互，唯一前端差异为`package.json:3`。包含UI的114个旧feature文件摘要未变，继承旧报告`:104`的实际邻居/桌面/窄屏对比，不重复声称本轮打开生产页面。新增5个发布模块与打包维护闭包对应发布合同第2–6步，无额外产品功能或扩大人员删除授权。 |

部分实现、未实现：本次源码交付范围内未发现。生产部署、公开鉴权与目录验收、四条清理仍是待执行步骤，不是已经完成的效果。Stage 1无HIGH后进入Stage 2。

## Stage 2：Code Quality — PASS

| 维度 | 结论与证据 |
|---|---|
| 命名、结构、规模 | ✅ 新发布代码按runtime/drain/backup/verify/deploy拆分；7个文件107–228行，打包202行、测试文件均≤300。临时probe只执行仓库固定代码与固定队列参数（`member-release-drain.py:13`）。 |
| 测试真实性与边界 | ✅ 71项独立通过。controller故障测试模拟外部IO，不能证明真实系统命令成功，故本轮另执行真实PostgreSQL dump/restore/迁移行保护及真实维护CLI导入。没有假称Windows本地测试运行了生产systemd/nginx；相关成功必须由实际安装/切换证据补齐。 |
| 安全扫描 | ✅ 对新增发布/打包源码扫描无eval、innerHTML、前端secret变量、硬编码sk密钥或shell=True。命令使用参数数组；唯一逐表SQL的表名来自PG catalog且经`[a-z][a-z0-9_]*`校验（`member-release-backup.py:34`），业务值不来自用户输入。 |
| 隐私与备份权限 | ✅ `member-release-deploy.py:89` 强制umask077、拒绝Python -O与非root；`member-release-backup.py:62` 拒绝备份内symlink并统一目录0700/文件0600；运行异常诊断落私有文件（`member-release-drain.py:47`），未输出worker环境。包允许列表不包含个人名单/私有JSON/数据库转储（`package-overseas.py:60`、`:74`）。 |
| 错误路径和恢复边界 | ✅ 未确认空闲不会进入backup/migrate；备份restore不匹配不会写COMPLETE；已迁移标记阻止无审查重跑；开入口后失败只关intake、保留executor，避免打断已接工作（`member-release-deploy.py:18`、`:49`、`:78`）。 |
| 构建与依赖 | ✅ reviewer独立`pnpm build` exit0，包含vue-tsc和生产Vite，39.09秒。package diff只有版本、依赖/lock未变；已有audit证据critical0/high36/moderate34/low1，不表述为全部依赖零漏洞。本增量没有新增依赖安全问题；保留既有pnpm配置warning原文如下。 |
| 可疑平台语义核对 | ✅ Nginx `^~` 最长前缀阻止regex匹配已与官方说明核对，支持关闭国内SSE入口判断；pg_restore的no-owner/no-acl/exit-on-error与实际恢复一致。参考 [Nginx location](https://nginx.org/en/docs/http/ngx_http_core_module.html#location)、[PostgreSQL 17 pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html)。 |

### 独立执行原始输出

测试日志：`output/member-release-review-tests.log`。

```text
hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/member-release-tests.py scripts/release/member-release-topology-tests.py scripts/release/test_package_overseas.py -q --tb=short
.......................................................................  [100%]
71 passed in 2.24s
```

完整编译日志：`output/member-release-review-build.log`。下列为原始头尾，省略762行中的逐资源体积清单，exit0：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.

> hengxin-smart-image-frontend@0.2.29 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build

🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 4708 modules transformed.
rendering chunks...
computing gzip size...
✓ built in 39.09s
```

真实数据库实验日志：`output/member-release-review-real-backup.log`。仅在本机Docker创建新的PG17 fixture及两个无网恢复容器，数据为合成active/pending成员与业务JSON；执行真实迁移文件的offline SQL，调用未修改的备份/恢复/验证函数，最后删除本实验创建的容器/匿名卷。未触及既有本地数据库或生产。

```text
DOMESTIC_DUMP_UNNETWORKED_RESTORE_FINGERPRINT_PASS
OVERSEAS_DUMP_UNNETWORKED_RESTORE_FINGERPRINT_PASS
BOTH_ACTUAL_MIGRATIONS_FULL_ROW_INVARIANTS_PASS
EXISTING_ROW_MUTATION_REJECTED_PASS
```

其它独立原始结果：

```text
{"count": 114, "changed": []}
SOURCE_REQUIRED_MISSING []
SOURCE_COMPILE_PRIVACY_PASS 600
RELEASE_RUNTIME_CLOSURE_PASS
PRODUCTION_ASSET_PRIVACY_PASS 843
```

`git diff --check` exit0，只有既有CRLF/LF提示，无空白错误。上述成功不代替稍后的已提交release包、服务器镜像安装测试与生产实时证据。

## 追加运行时调用器审阅（不属于candidate快照）

主Agent后续派发两个忽略目录调用器。本节仅固定所读字节，不能由candidate凭据覆盖以后对这些文件的修改：

| 文件 | SHA256 |
|---|---|
| `output/member-release-control.py` | `096ee00d98426926b386296f8b2886496b4e79c032bdecc97f03458e3f440060` |
| `output/member-maintenance-control.py` | `4356fad905bb0e6ae986c2f4ca4bdf966b4b763e5791a36a9f383fab0fa75731` |
| `output/member-release-remote.py` | `98b3358341b9c6ac46b64b89aea27ed0605869d6ea29e4047a22507b1c33a590` |

- ✅ transport校验本地及传输后archive SHA，拒绝重复/非普通/绝对/越界tar项，核完整manifest文件集/摘要，只调用上述已审controller；SSH强制既有host key，日志/exit文件位于私有release目录（`member-release-control.py:9`、`:14`、`:37`）。审阅未启动上传或远程操作。
- ✅ 清理调用器先要求发布verification与两迁移版本，再读取已有四条固定目标；fresh audit核稳定identity和eligibility，审批文件独占创建；apply要求dry-run确为同四条且全部would_delete，交给已审CLI锁内再检查、恢复资料先落盘（`member-maintenance-control.py:15`、`:36`、`:50`）。无ad-hoc DELETE，不扩展到其它人员。
- ✅ 后验比较剩余海外成员完整证据并核四份恢复资料权限/hash（`:61`）；如果apply期间任何条目因新证据跳过，verify明确失败，主Agent必须按每条实际结果记录，不能说“四人已删”。国内完整性还需主Agent单独只读回查；该wrapper没有宣称自己验证了国内库。
- ✅ 已编译上述三个调用器，无语法错误。个人姓名/ID未复制入本报告；生产删除与恢复效果仍未执行。

## 交接

由主Agent对同一candidate运行`review-approve`并登记本报告及两阶段PASS，随后按授权提交和发布。实际镜像安装、关闭入口/排空/备份、生产迁移指纹、源码/挂载/公开鉴权/页面与目录、四条逐人处理及最终回读的原始证据必须在执行后补入发布记录。
