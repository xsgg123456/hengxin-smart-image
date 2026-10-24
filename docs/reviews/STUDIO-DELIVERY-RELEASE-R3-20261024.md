# 海外收图可靠性发布审查 R3

- 最终送审 candidateId：`12a9780008a7c301e8fd684eebcc856bb34b85983a3aa01289c95a5a3bcb7f97`。
- 源合同：`docs/STUDIO-DELIVERY-RELIABILITY-20261024.md:3`；审查依据：`.agents/skills/code-review/SKILL.md:25`。
- 范围：新增的 4 个发布/打包/修复运行脚本及拆分后的 3 个测试文件；同时追踪继承的部署、打包、安装校验调用与 `delivery_repair` 接口。收图算法、前端展示由核心 reviewer 审查，本报告不替代其结论。
- Stage 1：**PASS（上述发布分区）**。没有发现 HIGH。
- Stage 2：**PASS（上述发布分区）**。原 1 项 MEDIUM 已在本次审查内修复并独立复核；最终快照没有剩余 HIGH/MEDIUM。
- 不批准、不提交、不修改产品代码或 Skill，也未连接或修改生产。本报告不是生产发布或原八图已补回的证明。

## 快照一致性

审查开始 `harness.py review-status` 的 `currentId` 为最初送审 `9cb2e67477d2caa74471b72a53e8e1b3b9ae57a89fd280cd56c8ee896a53ef2d`。期间变为 `cbc7917159e22c9d6349df9c1135dd5150dfefbb016ff0d34b5c9e6132289bcf`，当时 6 个 release 文件未改变，先发生变化的 Python 文件是：

- `hengxin-smart-image/backend/app/overseas/studio/native_images.py`
- `hengxin-smart-image/backend/tests/test_studio_delivery_recovery.py`
- `hengxin-smart-image/backend/tests/test_studio_native_images.py`

已即时通知主 Agent。随后主 Agent 将 348 行发布测试拆分为两文件，刷新为 `ee44d8a1ac47e54e2f77fbbe2139894c7f3f6543e149a1be44419dfb3b711c47`，再删除两条无用导入，最终刷新为本报告顶部的 `12a9780008a7c301e8fd684eebcc856bb34b85983a3aa01289c95a5a3bcb7f97`。本 reviewer 收到明确新范围后从 Stage 1 复核：4 个发布生产脚本未变；拆分后测试尾段接回原文件并恢复原无用 import，即精确复现原 SHA256 `65454f71cb316d49d2b6a6491880c1193a03bf61ed4fe43517834f382abb51cd`，所有测试函数及断言保持。最终 7 个文件摘要均与最终 candidate 一致，并对 3 个测试文件重新执行 37 项测试全过。核心 native history 变化及新增后端测试文件仍由另一 reviewer 复核，不在本报告跨范围批准。

## Stage 1：合同逐项映射

| 合同条目 | 发布范围核查与证据 | 结论 |
|---|---|---|
| 最终回复实际图片；无需固定标题、措辞或 JSON | 发布脚本不增加模型输出格式门禁；请求的 JSON 是运维侧私有证据，非模型交付格式。运行时直接调用统一 `repair`，后者用 `enumerate_delivery/collect_reference` 验证最后回复。`scripts/release/studio-delivery-repair-runtime.py:98`；`backend/app/overseas/studio/delivery_repair.py:24`。 | 完整实现发布接口；算法细节由核心审查覆盖 |
| 1. 精确最终消息与历史 JPG | 请求以最终事件 SHA256 和逐路径字节摘要绑定选图。格式无新增门槛，准确八图是本次已授权运维请求的数量。`scripts/release/studio-delivery-release-repair.py:30`、`:108`；`backend/app/overseas/studio/delivery_repair.py:24`。 | 完整实现发布接口；真实 JPG/事件解析由核心审查及上线证据覆盖 |
| 2. 私有保全、失败保持恢复依据、不重启模型 | request/work 限 owner-only、拒绝 symlink、prepare pin 摘要；在 pause 前 fsync baseline 与 STARTED；失败不删证据、不重放。`studio-delivery-release-repair.py:30`、`:53`、`:68`、`:120`；主入口禁止 Python 优化关闭断言，`studio-delivery-reliability-20261024.py:165`。 | 完整实现 |
| 3. 复用原 Job/Turn、逐图可恢复、幂等 | 实际调用同一 `delivery_repair.repair`；验证 8 个 Picture 与 ExecutionObject 归属和原字节，核对原执行次数/起止时间/outbox 完成时间，再重复补收并比较结果、版本、审计和对象。`studio-delivery-repair-runtime.py:12`、`:36`、`:98`；`studio-delivery-release-repair.py:125`。实际八图夹具及损坏对象测试通过。 | 完整实现发布接口；核心事务/租约由核心 reviewer 覆盖 |
| 4. 保存中/立即显示/完成状态、退避、不重生 | 发布端要求 `deliveryStatus={state:complete,expected:8,saved:8}` 和无 delivery_error 后才恢复 gate；无模型启动调用。`studio-delivery-repair-runtime.py:47`、`:98`；`studio-delivery-release-repair.py:131`。用户界面、退避逻辑不在本分区。 | 完整实现发布完成门禁；UI/调度交由核心 reviewer |
| 5. 故障测试与独立审查 | 独立重跑新增 37 测试、继承 129 测试及 48 subtests；另执行新进程导入、Linux 真 UID/GID 传输/权限、继承 deploy 晚期失败对抗。证据见下。`test_studio_delivery_release_repair.py:58`、`:134`、`:178`；`test_studio_delivery_repair_runtime.py:69`、`:87`。 | 已执行本分区独立验证 |
| 6. 只读生产基线与 Skill 不变 | 固定 API image、前端 release、worker/outbox 路径、schema 0032/overseas_0021、Compose grant + release 尾链；Skill 启停记录前后逐字比较；继承核验 15 包/227 文件、同目录及 sandbox 只读。`studio-delivery-reliability-20261024.py:20`、`:55`、`:82`、`:103`、`:130`；`overseas-studio-sessions-skills.py:10`、`:14`。 | 完整实现；本轮未重查生产 |
| 6. 备份、关闭接纳、排空、安装验证 | 实际继承链先 close edge、停 API、两次稳定排空后停 outbox/worker、隔离恢复验证备份，再 before_switch 与切换。无迁移的 hook 替换了旧 migration hook。`overseas-upload-deploy.py:183`、`:211`；`studio-delivery-reliability-20261024.py:103`、`:157`。实际 installed 产物只读挂载至无网络容器运行专项，receipt 绑定 image/manifest/target；`studio-delivery-reliability-20261024.py:113`；`overseas-studio-sessions-deploy.py:267`。 | 完整实现 |
| 6. installed 后补八图、恢复原 gate、再发布前端/开入口 | `_installed` 完成后确认 Skill 状态，检查 edge closed + drained，读取实际 installed worker 的 uid/gid/groups/env，用 installed `.venv/bin/python` 执行修复；dry/apply/verify/repeat/verify-repeat 后恢复原 paused 值。继承 deploy 其后才 publish/open。`studio-delivery-reliability-20261024.py:130`；`studio-delivery-release-repair.py:77`、`:108`；`overseas-upload-deploy.py:236`、`:242`。已实际执行该继承函数的晚期失败分支，确认恢复 gate 后失败仍 hold。 | 完整实现发布顺序 |
| 6. 预览/下载与原哈希、提交推送 | 运行时通过服务预览/下载使用的 `files.read` 读取实际对象并验字节；`studio-delivery-repair-runtime.py:57`；`backend/app/overseas/studio/files.py:61`。浏览器展示与下载仍需部署后的真实核验；Git 提交推送由主 Agent 执行。 | 代码验证已实现；生产/浏览器/提交属于后续执行证据，不声称完成 |
| 运行边界：非零/取消/缺成功回执、缺文件不伪成功、不重生 | `delivery_repair` 对原 exit/event/final/hash 验证，`_locked` 限原成功/已退出/无取消/无删除/无在途 job；发布端保留失败 baseline，不做回滚、数据库 restore 或迁移。`backend/app/overseas/studio/delivery_repair.py:24`、`:50`；`backend/app/overseas/studio/image_recovery.py:33`；`studio-delivery-reliability-20261024.py:42`、`:137`。 | 完整实现发布接口 |

表中无目录前缀的发布文件均位于 `scripts/release/`；`backend/` 为 `hengxin-smart-image/backend/`。

## Stage 2：发现与质量

### MEDIUM R3-01：已解决——发布测试文件原 348 行

规范原文：“文件不超 300 行”（`.agents/skills/code-review/SKILL.md:35`）。原 `test_studio_delivery_reliability_release.py` 为 348 行，现拆为 `scripts/release/test_studio_delivery_reliability_release.py:1`（150 行）与 `scripts/release/test_studio_delivery_release_repair.py:1`（203 行）。前者保留打包/基线/安装测试；后者承载补收、权限传输和部署故障测试，导入共享的 `save` 与 pytest `release` fixture。原文件的 `SimpleNamespace` 与新文件的 `load` 无用导入已删除。精确内容重构哈希与 37 项重跑证明没有删测试或改变断言。

其余新增生产文件为 168/34/154/117 行，运行时测试为 119 行；最终全部新增文件均小于 300 行，没有发现其它需要阻止本分区的缺陷。

### 已核查安全与测试真实性

- 私有请求仅 `actor_id/turn_id/expected_sha256/expected_checksums`，拒绝重复 JSON key、非规范 UUID、无效摘要、不足八图、控制字符路径；通过 stdin 传递，不放命令行或 archive。`studio-delivery-release-repair.py:21`、`:30`、`:94`；精确 helper allowlist 为 `package-studio-delivery-reliability.py:14`、`:26`。继承打包仅取 committed/reviewed 源，重新核验工作树及 archive 成员与字节，`package-overseas.py:92`、`:179`、`:192`。
- native worker 身份、实际 cwd、WorkingDirectory、四个 UID、GID 和 supplementary groups 都核对；复用实际 worker 环境，仅设置目标 PYTHONPATH、禁写 pycache、禁优化。`studio-delivery-release-repair.py:77`。Linux 临时夹具真实以非 root 子进程写 owner-only 控制目录成功，并验证宽权限与 symlink 拒绝；没有冒充真实生产 systemd 用户检查。
- runtime `main()` 验证 `app` 导入来自 installed cwd；新进程单独走 runtime 导入链后 34 个表全部 FK 解析成功，排除 pytest 全 app 预加载掩盖的问题。`studio-delivery-repair-runtime.py:70`、`:106`。
- 权限检查复用 `settings.manage`，gate 操作有锁，pause/restore 需要 drained；失败 hold 可在 collection 活动时关闭接纳。`studio-delivery-repair-runtime.py:21`、`:29`、`:79`。测试实际使用后端 SQLite 与内存对象存储：校验补回八图、重复幂等、实际对象字节损坏、无权限、未排空。`test_studio_delivery_repair_runtime.py:69`。
- 原始 `test_later_release_failure…` 用替身 `s.deploy`；为补足调用层证据，本 reviewer 另调用真实继承 `d.deploy`，在成功 repair/restore 后向 `r.publish` 注入异常，验证 `publish-frontend` 故障记录、close edge、停 API、hold gate 且不 open。
- 对 4 个新增生产脚本搜索 `eval(`/`exec(`/`shell=True`/硬编码密码/API key/token 前缀，无匹配。所有 subprocess 参数为列表；固定绝对路径用于已授权发布目录或 `/proc` 只读核查，无新外部接口。证据主要位于 `studio-delivery-release-repair.py:79`、`:100` 和 `studio-delivery-reliability-20261024.py:121`。
- 保留全权限 Compose 环境：只覆盖 image/build/memory，完整环境比对不归一化、不覆盖 owner/full access bindings。`overseas-studio-sessions-deploy.py:197`；`overseas-upload-resources.py:7`、`:12`。
- Spec 漂移：未发现新增页面、API、表或 Skill 安装行为；4 个新脚本均服务于合同第 6 项。无 UI 组件变更，因此本发布分区视觉比较不适用；不能据此声称前端视觉验收通过。

## 独立验证与原始输出

最终 candidate 上命令：`hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest -q scripts/release/test_studio_delivery_reliability_release.py scripts/release/test_studio_delivery_release_repair.py scripts/release/test_studio_delivery_repair_runtime.py`

```text
.....................................                                    [100%]
============================== warnings summary ===============================
hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1
  StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53
  DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
37 passed, 2 warnings in 7.89s
```

命令：相同解释器 `-m pytest -q scripts/release/test_studio_sessions_release.py scripts/release/test_studio_sessions_skills.py scripts/release/test_archive_deletion_release.py scripts/release/test_overseas_upload.py scripts/release/test_package_overseas.py`

```text
.................................................... [ 40%]
.............................................................................                                        [100%]
129 passed, 48 subtests passed in 7.97s
```

编译：逐文件 `compile(path.read_text(encoding='utf-8'), str(path), 'exec')`，未生成/改写受审代码。

```text
12a9780008a7c301e8fd684eebcc856bb34b85983a3aa01289c95a5a3bcb7f97
scripts/release/studio-delivery-reliability-20261024.py: compile PASS, 168 lines; candidate MATCH
scripts/release/package-studio-delivery-reliability.py: compile PASS, 34 lines; candidate MATCH
scripts/release/studio-delivery-release-repair.py: compile PASS, 154 lines; candidate MATCH
scripts/release/studio-delivery-repair-runtime.py: compile PASS, 117 lines; candidate MATCH
scripts/release/test_studio_delivery_reliability_release.py: compile PASS, 150 lines; candidate MATCH
scripts/release/test_studio_delivery_release_repair.py: compile PASS, 203 lines; candidate MATCH
scripts/release/test_studio_delivery_repair_runtime.py: compile PASS, 119 lines; candidate MATCH
FINAL_SPLIT_EQUIVALENCE_PASS; exact old hash after restoring only removed unused import; all test bodies preserved
```

额外独立对抗输出：

```text
FRESH_RUNTIME_IMPORT_PASS 34 registered tables; all FK targets resolved
LINUX_TRANSPORT_PASS: owner-only request/work; symlink rejection; real non-root UID/GID; inherited env; control write 0600; private receipt 0600
REAL_INHERITED_DEPLOY_LATE_FAILURE_PASS: verify-repeat -> restore -> publish failure -> close-edge -> stop-api -> failure-hold; no open
```

执行环境限制：Windows Docker daemon 未运行（`open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.`）；WSL 未安装本项目 Python 依赖。因此本轮实际后端测试使用 Windows venv，Linux 实测仅为 stdlib 的权限/传输夹具；未运行新 production image 中的 `native_install_test`，也未将其 mock 命令断言当成实际安装测试通过。安装专项和真实原八图的浏览器预览/下载必须由主 Agent 在发布时保留证据。
