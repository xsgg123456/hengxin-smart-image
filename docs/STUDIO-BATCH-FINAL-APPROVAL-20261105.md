# 批量标注最终发布审查与业务快照关联

日期：2026-11-05。独立 code-reviewer，使用 `.agents/skills/code-review/SKILL.md` 两阶段审查。

**candidateId：`6b97aef93e64853191bd2afab7fe8679667e3500f24309d6b35a29cfe13ec387`。Stage 1：PASS；Stage 2：PASS。**

本结论批准该快照的实现与本地验证，不代表生产部署已经完成。无 HIGH / MEDIUM 阻断项。此前 `STUDIO-BATCH-APPROVAL-20261105.md` 针对旧 candidate 的 R4 本次已关闭。

## 范围、依据与快照

- 直接审查 `scripts/release/studio-batch-*.py`（9 文件）、`scripts/release/test_studio_batch*.py`（6 文件），以及实际调用的 sku-native、sku-deploy、polling-database、package-delivery、package-overseas、sku-package、polling-runtime 等相关路径。
- 版本文件 `hengxin-smart-image/frontend/package.json:3` 的唯一差异为 `0.2.63` → `0.2.64`，匹配发布目标。
- 业务 33 文件按本报告后述摘要关联原独立两阶段结论；没有用发布审查覆盖未核对的业务差异。
- 依据：`Product-Spec.md:1`、`Design-Brief.md:1`、`DEV-PLAN.md:1`，本轮正式合同 `docs/STUDIO-BATCH-ANNOTATION-20261105.md:1`，发布合同 `docs/STUDIO-BATCH-RELEASE-PLAN-20261105.md:1`，以及 `docs/HARNESS-REVIEW.md:7`。
- 审查起始及结束读取 harness currentId，均与上述 candidate 一致。只写本 Markdown 报告，未修改实现、写 clean、登记批准、commit 或操作生产。批准凭据由主 Agent 使用同一 candidate 登记。

## Stage 1：发布合同逐条对照

以下“完整实现”均指工具及对应本地证据；实际生产步骤尚未执行，另列于交付边界。

| 合同条目 | 结论与证据 |
| --- | --- |
| 基线：0.2.63 → 0.2.64，固定 API 镜像、0026 不迁移 | 完整实现。`scripts/release/studio-batch-runtime.py:11` 固定版本/镜像，`:13` 限五个 API 模块、`:15` 限一个 native 模块；`studio-batch-deploy.py:23` 检查 revision；`polling-runtime.py:11` 新旧 revision 均为0026；`test_studio_batch_release.py:44` 实测范围与无迁移 helper。 |
| 基线采集不输出环境密钥，保留实际 native 来源 | 完整实现。`studio-batch-baseline.py:20` 读取真实容器/进程；`:33` 取实际 cwd，`:43` 只保存指定源码、挂载、Compose 路径及 Skill 摘要。`studio-batch-deploy.py:35` 重新采集全部实际 Compose 并记录文件摘要。 |
| 步骤1：干净固定 commit、正式包必须批准 | 完整实现。`studio-batch-package.py:20` 拒绝脏代码/未跟踪文件，`:24` 正式模式调用 `package-delivery.py:70` 校验 approved，`:26` 固定 commit，`:68` 构建后重验 clean/HEAD/candidate。`test_studio_batch_recovery.py` 的 dirty-source 用例本轮通过。提交属于主 Agent 后续动作。 |
| 步骤2：allowlist、全部文件 hash、递归测试依赖、隐私审计 | 完整实现。`studio-batch-package.py:31` 来源与隐私逐文件验证，`:49` 收集测试依赖；`sku-package.py:15` AST 递归本地导入；`studio-batch-runtime.py:61` 校验所有必需文件、路径/符号链接和摘要，`:71` 拒绝未登记文件，`:74` 限 API 集合，`:76` 限 helper 集合。`test_studio_batch_release.py:59` 包篡改拒绝通过。 |
| 步骤2：固定 commit 隔离前端 build，不读旧 dist | 完整实现。`studio-batch-build.py:47` Git archive 固定提交，`:57` 全新目录，`:75` 拒绝 tracked dist，`:86` 校验 Node/pnpm 版本，`:91` frozen lock 安装，`:92` 实际 build，`:93` 至 `:104` 复核来源与产物并记录 SHA。`:48` 环境白名单不继承 VITE/NODE_OPTIONS。`test_studio_batch_build.py:106` 至 `:116` 覆盖旧dist、失败、源码/产物篡改；真实旧HEAD build 日志另见下文。 |
| 步骤3：prepare 仅构建候选镜像、资源不变、只改 API image | 完整实现。`studio-batch-deploy.py:29` 核验基线，`:36` 原 Compose，`:54` 固定五模块 COPY，`:59` image-only overlay，`:62` 全配置相等，`:64` 复查资源。`test_studio_batch_release.py:90` 验证既有私密 overlay 路径保留且明文不落 prepared。 |
| 步骤3：镜像真实 /app、默认身份、只读测试、独立 PG、无生产配置注入 | 完整实现。`sku-deploy.py:110` 清除旧测试凭据，`:116` 独立 network none PG，`:132` 只读测试挂载 `/app/tests`、PYTHONPATH=/app、镜像默认用户，无生产 env-file；`:106` 要求退出0且有passed、无failed/skipped；`:138` 凭据绑定 manifest/image。`test_studio_batch_release.py:202` 核对候选镜像及隔离参数。实际正式镜像执行为生产前门禁。 |
| 步骤4：检查任务/草稿导入、停 API 后重查、暂停 consumer | 完整实现。`studio-batch-deploy.py:74` 草稿导入检测，`:83` worker idle，`:87` Docker 无限优雅停止但调用有60秒期限，`:89` 再查导入，`:91` 再查 worker 后暂停。`test_studio_batch_release.py:123`、`:135`、`:152`、`:166` 分别覆盖预检失败、入队竞态、超时、成功次序。 |
| 步骤4：outbox 先停、禁 SIGKILL、统一60秒、超时保留保护 | 完整实现。`sku-native.py:96` 正向停止；`studio-batch-recovery-state.py:68` 恢复停止复用同字节 drop-in，`:84` 确认 SendSIGKILL=no 与 infinity，`:86` 同一截止时间，`:87` 反序停止；`test_studio_batch_reentry.py:17` 及本轮独立22项 native 回归通过。 |
| 步骤4：私有备份、0026独立恢复、全表/schema 比较 | 完整实现。`polling-database.py:19` 关闭入口并确认停止，`:30` 独立PG恢复，`:52` fingerprints/schema/revision 比对，`:65` 私有目录，`:85` 安装前再次绑定 dump/schema/image/manifest 并比对生产数据；独立4项备份回归通过。 |
| 步骤5：native 原始备份、原子安装、真实身份/实际路径探针 | 完整实现。`studio-batch-native.py:18` 首次原备份，`:32` 重试复用，`:39` 排他临时文件、`:44` replace；`:48` runuser 实际路径编译；`:113` 自定义用途及旧payload语义探针。`sku-native.py:180` UID999/cwd核查；本轮native4项及复用22项通过。 |
| 步骤6：native验收后切API、保留Compose、网关刷新 | 完整实现。`studio-batch-deploy.py:109` 要求旧API停止、备份与native verified；`:116` 先记录切换阶段，`:118` 仅image overlay，`:119` 刷新固定网关。`test_studio_batch_release.py:182` 验证native→API→网关顺序；网关既有10项结论沿用上一轮，未冒称本轮重跑。 |
| 步骤6：前端哈希资源、公网实际字节、国内/环境/Skill/其他资源不变 | 完整实现。`studio-batch-deploy.py:123` 核对新API配置/环境/native/国内海外ready；`:141` 复用sku-frontend备份部署；`:148` installed前端及公网HTML/JS/CSS实际SHA核查。`sku-deploy.py:29` native/Skill/其他容器保护；`studio-batch-recovery.py:95` 恢复后Skill复核。 |
| 步骤7：生产浏览器正式入口、1920/1440/390、不收费生成 | 验收责任明确保留。`studio-batch-deploy.py:163` 返回 REQUIRES_BROWSER_VISUAL_ACCEPTANCE；本地业务视觉证据关联原独立报告`:53`。不能以脚本成功代替上线后正式入口验证。 |
| 恢复：切换前/后分流，不回灌数据库，不停Skill publisher | 完整实现。`studio-batch-recovery.py:46` 校验阶段，`:79` 先恢复native，`:88` 旧image/配置/环境，`:91` 仅恢复前端备份；无数据库回灌路径。`test_studio_batch_recovery.py` 的阶段拒绝、恢复顺序及候选拒绝本轮通过。 |
| 恢复：consumer已暂停、gate未写、outbox已停、pending job、入队竞态 | 完整实现，R1关闭。`studio-batch-worker.py:12` 实际PID/pool/queue识别暂停态；`studio-batch-recovery.py:48` 补 gate，`:14` 按暂停状态检测空闲，`:7` pending拒绝，`:68` 竞态先恢复consumer/native再开放API。`test_studio_batch_partial_gate.py:17` 经真实worker CLI校验，各场景本轮通过。 |
| 恢复：恢复阶段持久化、PID/源码检查、停止与凭据退场重入 | 完整实现，R3关闭。`studio-batch-recovery-state.py:9` 保存manifest/phase/PID/目标hash；`:21` 严格guard；`studio-batch-native.py:84` 旧安装凭据逐个退场，`:89` finish后启动。`test_studio_batch_reentry.py:175` 停机中断、`:181` 凭据部分退场真实state重入通过。 |
| 恢复：半写临时文件、replace前中断，不污染app树 | 完整实现，R4关闭，详见下一节。`studio-batch-native.py:68` 至 `:82` 原子恢复；`test_studio_batch_reentry.py:184`、`:187` 真实故障回归通过。 |
| 候选包限制、命令/引导真实性、Spec漂移 | 匹配。`studio-batch-deploy.py:19` release gate，`:175` CLI动作与文档一致，`:193` repair-native映射；`studio-batch-recovery.py:45` 恢复也须release。没有额外业务页面/API/表或迁移；仅发布合同要求的工具。 |

本发布实现范围没有部分实现或未实现条目。提交、正式包、镜像安装测试和生产验收是尚待主 Agent 执行的部署步骤，不被本报告标记为已执行。

## R4 实际故障证据

- `studio-batch-native.py:70` 临时路径位于实际 native 根目录，固定为 `.studio-batch-restore-` 加 allowlist 模块名，位于受 guard 扫描的 `app/` 树之外。`:70` 经真实 `sku-native.safe` 拒绝目标及父目录符号链接；`:71` 仅删除该确定路径的普通文件残留；不会批量清理 app 或其他文件。
- `:66` 原备份摘要、`:67` live旧/新摘要仍严格校验；`:75` copy2只写临时文件，`:76` 验证完整旧hash，`:77`/`:78` 从实际live stat保留uid/gid/mode，`:80` fsync，`:81` os.replace 后核对旧hash。没有放宽原live guard以容忍半文件。
- `test_studio_batch_reentry.py:100` partial分支实际仅写 `b'old'` 后抛 OSError；`:110` atomic分支在目标replace前抛错；`:117` retire分支在旧字节已落地、凭据仅退场一部分时抛错。`:148` 首次异常，`:151` 明确检查partial/copy/atomic的live仍为new，`:154` 真实sku.state，`:161` 非法PID拒绝，`:166` 无关app源码拒绝，`:169` 真实recover再次调用，最终检查old、API恢复、阶段退场与专用临时文件清空。
- 这些用例真实执行本地临时文件I/O、backup、restore、state/guard、停止/启动编排；systemd/docker/worker传输和Windows不可用的chown为替身。测试未声称已经在生产实际回滚。进程/I/O中断窗口已覆盖；未把它扩展为整机断电恢复验证。

## Stage 2：质量、安全与测试真实性

- **结构/错误处理 PASS。** 15个本轮Python文件最大225行，职责分别为基线、构建、打包、适配、部署、native、恢复阶段、恢复入口、worker识别和对应测试。`studio-batch-build.py:19` 清理有根目录约束及有界重试；`:79` 子进程失败不回退旧dist；`studio-batch-recovery.py:68` 异常只在确认native可安全恢复时重开API。编译结果见下文。
- **安全 PASS（本次范围）。** 定向扫描eval、HTML注入、前端密钥前缀、私钥/API key前缀、个人绝对路径和shell=True无命中。绝对路径均为合同固定生产资源或/proc身份读取（`studio-batch-baseline.py:33`、`:37`、`:46`，`studio-batch-runtime.py:30`），不是个人路径泄漏；进程环境仅用于对应worker实际运行，不打印/写入manifest。子进程使用参数数组（`studio-batch-build.py:79`、`studio-batch-package.py:19`），未引入动态SQL。根目录临时清理仅针对自身mkdtemp结果（`studio-batch-build.py:20`、`:24`），真实>260字符路径测试通过。
- **来源/环境门禁 PASS。** 包内源码逐项与固定commit一致，hash/路径/allowlist闭合；正式模式检查review批准。隔离build清除外部前端环境覆盖，版本锁定且不读取工作区dist。镜像安装测试不注入生产配置、只挂测试且使用实际镜像默认身份；生产API/native环境有前后摘要比较（`studio-batch-package.py:31`、`studio-batch-runtime.py:61`、`sku-deploy.py:132`、`studio-batch-deploy.py:127`、`studio-batch-native.py:109`）。
- **测试真实性 PASS。** R4不再以“完整copy后抛错”替代半写；partial和atomic实际检查live字节、真实guard及重试结果。R1队列测试实际进入worker CLI的identify/idle逻辑（`test_studio_batch_partial_gate.py:34`）；R2测试使用真实隔离子进程生成产物，但pnpm传输为替身（`test_studio_batch_build.py:54`、`:73`），真实生产构建证据独立列示，不混淆。22项native及4项DB为本次独立复跑。
- **视觉/引导 PASS关联。** 发布脚本没有新增UI；业务33文件与原报告一致，因此关联 `docs/STUDIO-BATCH-FINAL-FEATURE-REVIEW-20261105.md:53` 的实际邻居基准/批准预览/正式渲染比较和1920/1440/390证据。本次未重复打开浏览器，不宣称新增视觉实测；生产正式入口仍待部署后验证。

## 业务33文件关联

实际读取 `docs/STUDIO-BATCH-FINAL-FEATURE-REVIEW-20261105.md:119` 起逐文件清单，使用文件字节CRLF→LF归一SHA-256逐项比较，再按路径排序聚合，全部一致。其 `:6` 的 Stage 1 PASS / Stage 2 PASS、`:17` 的合同全条目矩阵、`:47` 的质量/安全/视觉结论可关联本 candidate 的同一33文件。

```text
BUSINESS_HASH_MATCH 33 9c7f2ddeb4f3a8df9fbda78caab8893f5355bea1896c63d29a61f2171d8c00d9
```

本候选变更集合为业务33文件、版本文件1个、发布Python15个，均已有对应审查。源文档不改变上述代码摘要。原业务报告保留的全后端Windows基线9失败、依赖审计既有39 high等限制继续有效，不把范围内PASS说成整个项目无失败/无漏洞。

## 编译与测试原始输出

审查者独立执行本轮命令：

```text
> python -m unittest discover -s scripts/release -p 'test_studio_batch*.py' -v
----------------------------------------------------------------------
Ran 40 tests in 1.921s

OK
exit_code: 0

> python -m unittest discover -s scripts/release -p 'test_sku_native*.py' -v
----------------------------------------------------------------------
Ran 22 tests in 0.415s

OK
exit_code: 0

> python -m unittest discover -s scripts/release -p 'test_polling_database.py' -v
----------------------------------------------------------------------
Ran 4 tests in 0.021s

OK
exit_code: 0
```

逐个 `compile(path.read_bytes(), str(path), 'exec')`，不写pyc：

```text
COMPILE_OK 15 files; max lines 225
```

`git diff --check` 未报空白错误；原始输出仅为工作副本CRLF将归一LF的Git提示。无编译警告或错误。上面66项均为本次独立执行；没有把此前网关10项算作本次执行。

本次只读取并核对主 Agent 原始日志的证据（非本次重新执行）：

```text
# output/release/studio-batch-build-01b7f86ab9844cb595855d52e0eb6e38.log:878
✓ built in 40.43s
# output/batch-annotation-preview/production-regression.log:850
ℹ tests 527
ℹ pass 527
ℹ fail 0
# output/batch-annotation-preview/production-build.log:599
✓ built in 31.27s
# output/batch-annotation-preview/backend-linux-postgres.log:13
127 passed, 2 warnings in 105.04s (0:01:45)
# output/batch-annotation-preview/backend-linux-postgres.log:16
TEST_EXIT 0
```

40.43秒记录是旧HEAD隔离构建，不能冒充0.2.64正式包；其Windows长路径清理问题已由本轮真实长路径用例覆盖。业务前端527、浏览器26、类型/build、Linux/PG127证据与限制见 `docs/STUDIO-BATCH-FINAL-FEATURE-REVIEW-20261105.md:64` 和 `docs/STUDIO-BATCH-VALIDATION-20261105.md:5`。

## 交付边界与结论

**Stage 1 PASS；Stage 2 PASS，可由主 Agent 对本 candidate 登记两阶段批准。** 尚须完成中文提交后的固定commit正式构建/资产审计、目标生产镜像安装测试、排空与真实备份恢复校验、发布切换、公网和正式浏览器验收。源码已有这些门禁；本报告没有提前签署其生产执行结果，也没有操作生产或批准其他快照。
