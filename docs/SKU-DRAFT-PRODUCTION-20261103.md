# SKU 需求回填及个人草稿 · 发布准备与记录

已完成生产发布及正式页面验收：前端 `0.2.60`、数据库 `overseas_0026`。发布代码提交 `7cb3e0a`（功能提交 `18fd64c`）。下文保留发布前基线、首次中止与修复经过，最终结果以末节为准。

## 2026-11-03 真实只读基线

- API 镜像：`sha256:ad35f03ca9dbd3fa09d6932e5aa19ae60250d1e449cc57da265eab411fcb33c1`。
- API 容器 ID：`0a000b68c8493b65bfb39b77ff2a0082e69dd05b418e064530cd7de96c2d51d3`，运行中。
- 前端 `0.2.59`；数据库 `overseas_0025`；9 任务、0 归档，尚无三张草稿表。
- 国内、海外正式 ready 接口均 HTTP 200。上游 `https://design.qhhengxin.top/api/open/meta` 匿名直连 HTTP 401，耗时 0.275 秒，证明生产主机到上游的 TLS/网络可达。
- API 环境尚未配置 `OVERSEAS_DESIGN_API_KEY`；只检查是否存在，不输出值。
- 生产镜像已安装 `httpx 0.28.1`、`pytest 9.1.1`。本轮把 httpx 声明移入运行依赖，但不升级实际安装包。
- 已采集 24 个 API 增量路径、两原生服务各自的 `db.py` 原字节；另记录 22 个容器、7 个原生服务及 1,344 个 Skill 文件的保护快照。
- 本地证据：`output/sku-release/{initial.json,baseline.json,dependencies.txt,protected-baseline.json}`。这些私有工作证据不进入发布包。

## 发布边界

`sku-runtime.py` 固定 API 文件、测试模块、辅助脚本和基线镜像；`sku-baseline.py` 与之使用相同文件集合。原生 worker/outbox 只更新 `app/overseas/db.py` 的版本标记，保留其实际旧任务、附件及交付依赖。草稿 API、线程、来源查询和下载模块仅进入 API 镜像。

新增表为 `overseas_requirement_drafts`、`overseas_draft_materials`、`overseas_draft_imports`。迁移不得修改任何历史行；旧列、索引和约束均参与保护校验。隔离恢复后运行迁移两次，核对历史行、原有 schema、三张新表为空，以及新表的列、索引和约束；生成带哈希的恢复证明再允许生产迁移。

密钥由主 Agent 安全写入生产 root 所有、权限 `0600` 的单值文件。`prepare --secret-file` 读取它并生成 `0600` 的私有 API overlay，只增加该环境项。原 Compose、`.env`、原生配置不变；生成配置与原配置除镜像和该环境项外必须完全相同。密钥不得出现在命令参数、源码、Git、发布包或普通日志中。

## 发布前验证记录

- 发布工具本地单测：58 项通过，0 跳过，覆盖排空顺序、禁止强杀、恢复保护、独立原生基线、备份证据、隔离容器、密钥环境隔离和静态资源回退。
- 命令：`python -m unittest discover -s scripts/release -p 'test_sku_*.py' -q`。
- 首轮提交前候选 `139644dd1e44` 在实际 Linux 镜像 `/app` 与隔离 PostgreSQL 上执行 18 个安装回归模块：161 passed、0 skipped，123.33 秒。涵盖草稿、来源查询、并发/租约、增量迁移、多附件、历史任务及既有能力。记录见 `output/sku-release/candidate-tests.stdout`，运行后核对生产 API ID/image/运行状态保持不变。
- 候选 `0664de5d7258` 完成海外 93 模块：808 passed、3 failed、0 skipped；两处旧测试预期和一个缺失只读测试 fixture 已修正，三个相关模块复验 41 passed、0 skipped。候选证据不替代正式已审包的安装测试；见 `candidate-full.stdout`、`supplement-tests.stdout`。
- 上述为发布前准备阶段记录，实际停止、迁移、切换和恢复经过见文末。

## 正式执行顺序

1. 完成代码、需求及测试；固定审查快照，独立两阶段 PASS，登记同一 `candidateId`。中文 Git 提交后确认工作区干净，正式前端构建属于该提交。
2. 若生产期间有更新，重新运行只读 `sku-baseline.py` 并核对固定 image/版本。API 和 native 必须分别采集，不可拿 API 哈希代替 native。
3. 在仓库根目录执行：

```powershell
python scripts/release/sku-package.py --baseline output/sku-release/baseline.json
```

4. 校验归档 SHA256，将正式包解压到新的 `/opt/hengxin-releases/sku-20261103-<commit>/src`，按严格 host-key 的已有 SSH 连接操作。不要把候选测试目录当正式发布目录。
5. 以下命令在服务器执行；`WORK`、`SRC` 和私有凭据路径替换为该次真实路径：

```sh
python3 -B "$SRC/scripts/release/sku-deploy.py" prepare --source "$SRC" --work "$WORK" --secret-file /root/private/sku-upstream-key
python3 -B "$SRC/scripts/release/sku-deploy.py" test --work "$WORK"
python3 -B "$SRC/scripts/release/sku-deploy.py" gate --work "$WORK"
python3 -B "$SRC/scripts/release/sku-deploy.py" backup --work "$WORK"
python3 -B "$SRC/scripts/release/sku-deploy.py" migrate --work "$WORK"
python3 -B "$SRC/scripts/release/sku-deploy.py" native --work "$WORK"
python3 -B "$SRC/scripts/release/sku-deploy.py" api --work "$WORK"
python3 -B "$SRC/scripts/release/sku-frontend.py" deploy --source "$SRC" --backup "$WORK/frontend-backup"
python3 -B "$SRC/scripts/release/sku-deploy.py" verify --work "$WORK"
python3 -B "$SRC/scripts/release/sku-deploy.py" resume --work "$WORK"
```

每步失败即停止依赖步骤并检查私有证据。`test` 使用隔离 PostgreSQL 容器和候选镜像的实际 `/app`，无生产卷、无生产环境、无外网连接，失败或跳过均不生成通过凭据。`gate` 先确认队列空闲，再停止 API 接纳并复查竞争提交；随后暂停原消费者、正常停止原生 outbox/worker。Docker 使用无限温和停机，systemd 明确禁止 SIGKILL；超过统一等待期限保留保护与恢复信息，不强停。

`backup/overseas.dump`、`restore-proof.json`、`draft-schema.json`、`native-backup.json`、`frontend-backup/` 必须保留。`prepare`、`test`、迁移和切换各自保存证据；正式版本、commit、candidateId、归档 SHA、镜像和生产 UI 结果在完成后追加。

## 恢复路径及验收边界

- 在 `MIGRATION_STARTED`、`API_SWITCH_STARTED` 均不存在时，可执行 `sku-deploy.py recover-before-switch --work "$WORK"`，恢复旧 API 和消费者。正在退出的原生服务不得强杀或提前移除保护。
- 数据库迁移开始后只向前修复；不把旧 dump 直接覆盖运行中的业务库，不降级或丢弃草稿表。部分 native 替换有逐文件原字节备份，应保持服务停止并核验后修复，不盲目重复安装覆盖证据。
- 前端可执行 `sku-frontend.py rollback --backup "$WORK/frontend-backup"`。只恢复入口与版本文件，保留两代哈希资源，防止既有标签页缺文件；这不等于后端或数据库回退。
- 生产最终核验需要正式入口页面目视验证、当前与历史图需可读、草稿恢复/来源查询，以及国内、海外健康与保护哈希。不得创建演示任务或触发生图。
- 未实际执行生产附件导入/进程重启恢复时，只能报告隔离测试证据；不能以 readiness 200 代替导入线程、持久队列或页面视觉验收。

## 首次正式发布尝试与恢复

- 已审代码提交 `18fd64c`；快照 `6e41fbc941835d635ee0541fbe6d95eca5d82839524590b298a1c923276b52f1` 两阶段 PASS，报告 `output/sku-release/REVIEW-FINAL.md`。
- 包 `sku-20261103-18fd64c`：5036086 字节，SHA256 `caa0c4f737046cd7b809c8f540acb3663c85586b39a6691b0e41c27d4757be56`，隐私与上传校验通过。
- 正式已审镜像安装测试：164 passed、0 skipped，123.44 秒；`output/sku-release/attempt-18fd64c/test.stdout`。
- 首次 gate 排空并正常停机通过。备份恢复后行数据指纹一致，但 schema 保护检查失败，因此未开始生产迁移或 API 切换。
- 诊断：394 列、113 索引一致；143 条约束中 10 个 CHECK 在 pg_restore 重解析后改变了 varchar 数组到 text 数组的类型转换表示。不能因此取消约束校验，修复须保留真实约束差异检测。
- 自动恢复还发现 systemd 无 Job 返回空串而脚本只接受 `0`；实际两服务 inactive/dead、MainPID=0。核对无待执行 Job、原代码与数据库版本后，通过有界原服务启动、恢复消费、工作身份与 readiness 检查完成操作恢复。
- `output/sku-release/recover_operational.stdout` 确认 `OLD_API_AND_NATIVE_RECOVERED; SCHEMA_0025_UNCHANGED`。旧 API 容器 ID 未变；原生服务正常恢复。失败发布目录及备份保留，不重用失败的 gate 记录。

修复验证：局部规范化完整匹配的 CHECK 数组 cast 表示，未知表达式保持逐字比较；空/0 Job 允许恢复，非空 Job 仍阻断。发布单测 62 passed；旧 dump 隔离恢复及两次迁移均通过，旧行/列/索引/约束保持一致，新表为空且结构稳定，SQL 等价验证通过。证据 `output/sku-release/restore-fix-validation.json`。

## 最终生产交付

- 已审代码：`7cb3e0acac46e6abce218326f7fed493341fd8f8`；增量修复候选 `2cc57f92d4082cc0cd45bc153469a9a38906d914659f6e82cfde17fa53e1e493` 两阶段 PASS，报告 `output/sku-release/REVIEW-RELEASE-FIX.md`。原功能快照的完整审查保持有效。
- 发布目录：`/opt/hengxin-releases/sku-20261103-7cb3e0a`；包 5036641 字节，SHA256 `9801418b75d688c1d38f73f73833e4e8130334b1b0ef67641491dec99c9130e3`，隐私与上传哈希检查通过。
- 新正式包安装测试：164 passed、0 skipped，118.15 秒。发布工具修复后 62 单测通过。
- prepare → test → gate → backup → migrate → native → api → frontend → verify → resume 全部完成。正式备份恢复及两次迁移验证通过，dump SHA256 `c6a83fb303f34e4ce36c60226a2000fae7fcca0dfad191339998742beeae29e6`；备份与恢复证明保留在发布目录。
- API 镜像 `sha256:82c9bda8995c2fc65b270b12b37056e4404cd14f05ab8cbd56fcd5eae09fa248`；容器 `77df61657114b52f5b0b6bcc82b2a87b55a8f358487944ee754395f5f607a18c`。两原生服务正常，API 24 个增量路径、native 各仅 db.py；其余容器/原生源码与 Skill 保护检查通过，前端安装字节全部匹配发布清单。
- 正式海外与国内 readiness 均 HTTP 200；生产 9 任务、0 归档，数据库 `overseas_0026`。证据 `output/sku-release/final_health.stdout`。
- 正式 Chrome 页面验证：单 SKU 输入和获取按钮、两类多附件区域显示正确；`SP-XLLHBC01-BT` 实际回填 BELEEV、V1老品副图优化 共12张、周仁平；上游平台值 BELEEV 不属于有效平台，品名和语言为空，页面明确提示并保留待补充。
- 真实后台导入一份 `V1副图A+需求优化.pptx` 到图片需求区域，状态已就绪；生产持久队列 ready=1。正式页面下载文件 988361 字节，SHA256 `49bcc8571ef7295b0a211ceae2fac45a033e9193d4b581813e63803facffc9b7`，与上游原件一致。
- 刷新及离开表单再进入，SKU、回填字段、已导入附件均恢复。历史“IT演示版”详情、原有会话和 3 份素材可正常读取；未编辑或发送历史会话内容。
- 为用户保留本次 SP SKU 验收草稿（此前草稿为空），未创建正式任务、未触发生图。生产未人为重启导入中的服务；租约超时/恢复由隔离 PostgreSQL 与故障测试证明，不能当作生产重启实测。
- 正式截图：`output/sku-release/production-sku-draft.png`、`production-sku-attachment.png`。隔离 4 后台附件加 2 手动附件、多记录选择、异常/冲突/幂等用例证据见验收文档。
