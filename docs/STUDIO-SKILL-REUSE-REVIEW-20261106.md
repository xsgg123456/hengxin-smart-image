# 同会话 Skill 复用独立审查 · 2026-11-06

审查结论：**Stage 1 FAIL，Stage 2 未执行。** 发现 1 项 HIGH、1 项 MEDIUM。当前快照不适合直接进入安装验证流程；修复后应重新固定快照，从 Stage 1 复审。没有执行生产变更、修改业务代码、提交或登记批准。

## 快照、范围与依据

- candidateId：`04df81b5439075f37d5a0675d36cb70ab301525f0660abe7f6ef7879b3735ec8`。开始时 `review-status.currentId` 与派发一致，`approved=false`。
- 结束时主 Agent 已解除冻结并派修复，`review-status.currentId` 变为 `26d647a0efa63c8298f2e7905848ab801e07b623dd3abdb063a94a098fcadcf0`，仍未批准。观察到 test helper 新增 target/vendor chmod，deploy 新增无 GATE_STARTED 的恢复分支。本报告绑定原 candidate，行号、反例与结论均针对原版本；不覆盖或批准修复后的新快照，后续必须重新 prepare 和独立复审。
- 范围：海外 persistent materials 接线、skill_content/skill_cache、新增三份缓存测试及 persistent_mounts fixture、九个 skill-reuse 发布 helper 和发布测试、AGENTS.md 最近部署记录规则。未扩大到历史产品全部功能。
- 原文已读：AGENTS.md、code-review/SKILL.md、HARNESS-REVIEW.md、STUDIO-SKILL-REUSE-20261106.md、STUDIO-SKILL-REUSE-RELEASE-PLAN-20261106.md 全文，以及 Product-Spec.md、DEV-PLAN.md 顶部新增条款。派发中 RELEASE-PLAN 的实际路径为上述完整文件名。
- 无 UI、DB schema、模型或技能正文改动。UI 一致性不适用，不能据此声称完成视觉验收。
- 验证目标是源码与发布工具是否满足合同；Linux 正式安装、真实目录 catalog 探针和生产发布尚未执行，不认定上线通过。

## Stage 1：发现

### HIGH / P1：测试根及 vendor 根被 umask 截成 0700，真实服务身份无法运行安装测试

合同要求真实服务 UID 使用隔离测试根、指定 vendor 和原生解释器运行套件（发布计划第 4、6 步）。

证据：

- `scripts/release/skill-reuse-deploy.py:186` 执行 `os.umask(0o077)`。
- `scripts/release/skill-reuse-test.py:65` 用 `target.mkdir(mode=0o755)` 创建 root 所有的测试根；第 71 行仅遍历 `target.rglob('*')` chmod 子项，没有修正 target 本身。
- 同文件第 42 行创建 vendor 根，第 54 行同样只 chmod 后代，vendor 根仍为 0700。
- 同文件第 26 行通过 runuser 切换服务身份，第 24 行要求 pytest 来源位于 vendor，第 33 行从测试根运行。真实 UID 不能遍历上述根，候选测试会在导入前失败。仅修 target 仍会留下 vendor 不可读问题。

依据：Python 官方 [Path.mkdir 文档](https://docs.python.org/3.12/library/pathlib.html#pathlib.Path.mkdir) 明确 mode 受进程 umask 限制；0755 & ~0077 = 0700。

独立复现：本地 WSL Ubuntu，root 设置相同 umask，执行相同 mkdir 与 rglob chmod 序列，再使用真实 nobody UID 访问；未连接生产。原始核心输出：

```text
target=0o700 vendor=0o700
real_uid_exit=1
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import os; os.chdir('/tmp/skill-review-28zh98ai/target')
PermissionError: [Errno 13] Permission denied: '/tmp/skill-review-28zh98ai/target'
evidence=/tmp/skill-review-28zh98ai
```

这是实际 POSIX 权限复现，不是生产安装套件通过证据。发布的 10 个 mock/文件测试没有覆盖该路径。修复应显式设定两个根的预期权限，并在保留 0077 的入口条件下验证真实非 root UID 能导入 app 和 vendor pytest。

### MEDIUM / P2：首次 idle 失败后 owner 已持久化，recover 无法撤销此次未变更生产的尝试

合同要求跨 CLI 互斥及可恢复失败；不能手动删除 owner 来绕过。

证据：`scripts/release/skill-reuse-deploy.py:198` 在调用 gate 前写 owner；第 99 行先调用 idle，第 100 行才写 GATE_STARTED。若现有任务尚在运行，idle 抛错，owner 保留而 GATE_STARTED 缺失。recover 第 150 行无条件读取该文件，无法走到第 205 行释放 owner。此路径尚未关闭代理或停止服务，恢复逻辑应能够核实没有变更后安全结束尝试。

独立隔离调用原始 main/gate/recover，仅替换生产 I/O 与 idle，输出：

```text
gate: RuntimeError: Overseas work remains
recover: FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\82358\\AppData\\Local\\Temp\\review-skill-owner-nc1bx9qz\\work\\GATE_STARTED'
owner_retained=True
gate_started_exists=False
```

影响限定：同一 work 可等任务空闲后重试 gate，因此不是永久死锁；但当前 recover 不能取消这一失败尝试，其他 work 的该 runner 被 owner 阻断。应补未进入关闭入口阶段的恢复分支及其故障测试。

## Stage 1：逐条合同覆盖

下表“实现匹配”指已读代码并核对对应测试；Linux 专项标为待验证，不用 Windows 跳过代替验收。

| 条款 | 结论与证据 |
|---|---|
| 仅海外 Studio persistent；国内/legacy 不变 | 实现匹配。`backend/app/overseas/execution/materials.py:22` 提前分支；`backend/tests/test_studio_skill_cache.py:149` 验证非 persistent 仍每轮独立副本。本表 backend 均指 `hengxin-smart-image/backend`。 |
| 名称、全部路径、字节、执行权限规则共同识别内容 | 实现匹配。`backend/app/overseas/execution/skill_content.py:12` 生成 checksum/size/mode；`skill_cache.py:60` 对名称与完整 entries 规范序列化后 SHA256。 |
| A/A、A/B/A、相同内容重发、新内容保留旧版 | 实现匹配。`skill_cache.py:66` 命中分支不写旧版；`backend/tests/test_studio_skill_cache.py:69`、`:89` 覆盖两个来源、发布标识变化和六种内容变化，校验 inode/mtime/字节。 |
| 会话私有、不跨会话共享 | 实现匹配。`skill_cache.py:15` 检查 UUID、round/control/persistent 所属关系；`:63` 缓存落会话根；`backend/tests/test_studio_skill_cache.py:120` 及 safety 测试 `:150` 验证隔离。 |
| 只暴露当前版本，只读挂载；取消选择隐藏历史 | 源码匹配，Linux 实测待补。`backend/app/execution/persistent_mounts.py:42` 空 tmpfs；`workspace.py:103` 当前 skill 双 ro-bind 和后续 remount-ro；`backend/tests/test_studio_skill_cache.py:168` 检查参数，`test_studio_skill_cache_linux.py:15` 有真实 bwrap 测试但本次 Windows 跳过。 |
| 安装技能和冻结资源两来源 | 实现匹配。`skill_content.py:20` 调已有 frozen_package；`:24` 校验 legacy 文本/资源；`test_studio_skill_cache.py:37` 参数化两来源。真实 catalog 探针 `scripts/release/skill-reuse-catalog-probe.py:11` 尚未运行。 |
| 命中完整校验、上传资源不重复下载、异常不换版 | 实现匹配。`skill_cache.py:27` 精确路径/大小/digest/mode 校验；`:69` 命中仅 verify，`:77` 仅新版本 read；`test_studio_skill_cache.py:69` 检查 reads，safety `:13` 强制命中不得下载。 |
| 互斥、暂存、校验、原子发布、失败重试 | 实现匹配。`skill_cache.py:62` 使用已有 context_fs.lock，`:72` 暂存，`:83` 校验后 rename；safety `:74` 并发只有一份，`:95` 注入写失败，`:122` 下载损坏/关闭与重试。 |
| 拒绝链接、特殊文件、越界、额外文件和损坏 | 源码匹配；Linux 权限与链接完整验证待补。`backend/app/overseas/studio/context_fs.py:24`、`:63` 原有无链接 reader；`skill_cache.py:27` 精确清单；safety `:13`、`:37`、`:66`、`:141` 覆盖篡改/链接/路径/权限。 |
| 不修改历史 session、附件、工作、图片、旧副本 | 实现匹配。`skill_cache.py:88` 清理只针对自身 .stage 临时目录；`test_studio_skill_cache.py:130` 多轮验证全部原字节不变；`:149` 保留旧非 persistent 路径。没有旧副本批量迁移/清理代码。 |
| 既有显式删除兼容 | 实现匹配。safety `:159` 走现有 cleanup_files.erase，验证仅目标会话及其缓存删除、另一个会话保持且没有对象存储删除调用。 |
| 打包白名单、已审提交、依赖及真实安装来源 | 打包源码匹配，运行部分失败。`scripts/release/skill-reuse-package.py:16` 固定提交、审查凭据、隐私检查；runtime `:45` 验包；test `:19` 断言 app/pytest/UID，`:40` 从 API 镜像提取六模块。但 HIGH 权限问题使当前真实身份验证不可执行。 |
| 双代理关闭、旧 worker 退出、任务排空、温和停机 | 源码匹配、实际待验证。gate helper `:68` 保存并等待旧 nginx worker、统一期限；deploy `:96` 排空、pause 后 stop；沿用 `scripts/release/sku-native.py:108` no-SIGKILL 停机。不调用生产验证。 |
| 互斥与失败恢复，新增源文件 absent 回滚 | 部分实现。deploy `:190` host lock/持久 owner 存在 MEDIUM 缺口；native `:16` 验证备份范围，`:96` 恢复阶段及新增文件移出 app；runtime `:78` 支持 absent/阶段 PID；deploy `:155` pending stop 拒绝重新开放。已有发布用例验证 absent guard、漂移和 pending stop，但没有真实完整系统恢复演练。 |
| 保留会话、原路径源码验证、API及其他服务保持 | 源码匹配，运行证据待补。preserve `:21` 不读文件内容而记录元数据，`:35` 表摘要；deploy `:21` API ID/image/StartedAt、环境、无关容器/前端/Skill 校验；native `:74` 最终安装路径测试通过才 start；恢复不回灌数据库。 |
| 上游文档同步、不新增 UI/数据库/模型/技能内容 | 匹配。Product-Spec.md:1、DEV-PLAN.md:1 指向本合同；materials 之外只新增缓存模块、测试及运维工具。`AGENTS.md:36` 为获准的先查最近部署记录规则。无本轮范围漂移。 |

## 独立验证原始结果与边界

在仓库执行发布 unittest，原始末尾输出：

```text
----------------------------------------------------------------------
Ran 10 tests in 0.097s

OK
```

在 backend 执行五文件 pytest：test_studio_skill_cache.py、test_studio_skill_cache_safety.py、test_studio_skill_cache_linux.py、test_studio_skill_trigger.py、test_studio_persistent_mounts.py。退出 0，原始末尾：

```text
...ss....ss............ [ 97%]
.s                                                                       [100%]
63 passed, 11 skipped in 11.48s
```

11 个跳过来自 Windows 的链接权限/POSIX/Linux 限制；不作为 Linux/bwrap 通过证据。

对九个 skill-reuse helper、发布测试、skill_content/skill_cache/materials 和现有 skill_copy 使用 Python `compile(bytes, filename, 'exec')`，退出 0，原始输出：

```text
COMPILE_PASS files=14
```

主 Agent 提供的全量后端 2725 pass/430 skip/10 fail、HEAD 对照 9 fail/43 pass、前端类型/527 测试/构建属于交接证据，本 reviewer 未重复执行这些全量命令。本次独立 63 项通过覆盖已修改 persistent_mounts fixture。Docker 本地 daemon 不可连接，故没有把本地 Docker 视为可用 Linux 安装验证环境；WSL 仅执行了上述权限反例。

## Stage 2

**未执行。** Stage 1 存在 HIGH，按 code-review skill 停在 Stage 1。不能登记任何两阶段 PASS 或用本报告批准提交/上线。
