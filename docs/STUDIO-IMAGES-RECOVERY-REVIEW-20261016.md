# 工作台图片发布恢复独立审查

- candidateId：`0f5a24f086d4694deffdb4aea0648258101579448786e3bfcd4fdce6605f3db2`
- 基线：已批准业务提交 `106d07d`。
- 审查范围：`scripts/release/overseas-images-deploy.py`、`overseas-images-recover.py`、`test_overseas_images.py`、`test_overseas_images_recovery.py`；对应 Product-Spec、DEV-PLAN、CHANGELOG 发布恢复条目及事故记录。继承脚本仅检查恢复实际调用链。
- Stage 1：**PASS**。Stage 2：**PASS**。未发现本次增量的 HIGH / MEDIUM 问题。
- 未连接生产、未执行部署、未改业务代码、未提交；本报告不代表生产恢复已经成功。既有业务 UI、真实发送及业务全量回归不重复验收。

## Stage 1：Spec Compliance

需求来源：`Product-Spec.md:1197`、`Product-Spec.md:1199`、`DEV-PLAN.md:1446`；事故证据来源：`docs/STUDIO-IMAGES-VALIDATION-20261016.md:37`。生产 PID、队列、备份的现状属于主 Agent 提供的事故实查证据，本 reviewer 未冒充再次生产实查。

| 条目 | 结论与证据 |
| --- | --- |
| 仅移除 ExecStart 动态显示信息 | 完整实现。`overseas-images-deploy.py:51` 仅匹配完整运行统计尾部，保留 path、argv、ignore_errors；未知格式保留。`test_overseas_images.py:236`、`test_overseas_images_recovery.py:29` 验证统计重置、静态字段变化和未知格式。 |
| 独立 MainPID、真实 cwd、配置摘要保持保护 | 完整实现。`overseas-images-deploy.py:63` 仍读取 MainPID、`/proc/<pid>/cwd`、配置摘要及 User；`overseas-images-recover.py:78` 对归一化后的完整结构严格比较。PID/cwd/argv/hash/User 漂移阻止 API 重启，见 `test_overseas_images_recovery.py:128`。 |
| 只恢复指定事故和失败阶段 | 完整实现。`overseas-images-recover.py:18` 固定 release，`:49` 校验 release、DEPLOY_STARTED、verify-installed/AssertionError、无成功凭据、未重复恢复；`:172` 限定 CLI 和原始 source 真实路径。 |
| 原完整备份和原基线仍存在 | 完整实现。`overseas-images-recover.py:57` 校验 COMPLETE、完整拓扑、非空 dump、排空停止标记、旧 manifests 字节及前端入口字节。COMPLETE 的原写入链在 `overseas-update-runtime.py:107`，先完成 pg_dump 与 pg_restore --list。恢复不重新生成或恢复数据库。 |
| 镜像、源码、schema、Compose 设置不漂移 | 完整实现。`overseas-images-recover.py:73` 复核安装/容量/PREPARED 同 image ID、所有 manifest hash、schema、prepared settings 和 native 文件 hash。继承 `overseas-upload-deploy.py:91` 比对 Compose 原配置及 overlay 允许差异。 |
| 国内、身份及共享资源不被切换 | 完整实现。`overseas-images-recover.py:83` 检查 native 指针优先级，`:90` 检查停止中的候选 API、容量/挂载及其余容器身份/配置；`:148` 调用完整资源复核。继承 `overseas-upload-resources.py:31` 比较国内/身份完整拓扑、海外其他容器、配置、native 和挂载。 |
| 入口关闭、健康执行器和稳定排空后才启动 API | 完整实现。`overseas-images-recover.py:104` 比对关闭入口和原代理配置，`:112` 实际 closed/readiness/wait_empty；`overseas-upload-deploy.py:69` 需要两次连续 DB/broker idle。`:126` 才执行 API up。顺序测试 `test_overseas_images_recovery.py:112`。 |
| 不重放 deploy，不迁移/恢复数据库，不停止 native | 完整实现。`overseas-images-recover.py:118` 仅接续 API→installed→代理→前端→开放验证，无 deploy/migrate/restore/stop native 调用。`:158` 失败路径仅关闭接纳并停止 API。故障路径测试 `test_overseas_images_recovery.py:166`。 |
| 原 source/证据不可变，恢复脚本独立加载 | 完整实现。`overseas-images-recover.py:37` 从显式原 source 导入依赖，仅包装其 domestic_native；`:30` deepcopy 归一化历史状态；不覆盖旧 domestic-native.json/FAILURE.json。`:183` 调用原 validate。另独立加载 git 106d07d 原版 deploy，验证归一化生效且原文件字节未变，输出见下文。 |
| installed、Skill、公共入口及前端校验后写凭据 | 完整实现。`overseas-images-recover.py:130` 先调用 `overseas-upload-deploy.py:156` 的完整 installed：schema、容器/native 源 hash、readiness、idle、资源、Skills、health/auth；`:145` 完成 public/proxy/frontend/resources 后才写 manifests 和 verification。 |
| 恢复失败保持关闭，不污染原失败证据 | 完整实现。`overseas-images-recover.py:158` 捕获 BaseException，关闭入口/还原代理并停止 API，另写 RECOVERY_FAILURE；RECOVERY_STARTED 防止重放。测试覆盖 API 启动、installed、public 和边界校验失败。 |
| 成功沿用原失败发布台账 | 完整实现。`overseas-images-recover.py:185` 调用原 `release-retention.managed` 的 recover。`release-retention.py:55` 要求原 pending.before、持锁执行，main 返回后才创建成功 receipt；`:35` 复核拓扑并 finalize，清理错误不进入部署失败 handler。 |

部分实现：无。未实现：无。Spec 漂移：无新增业务接口、表、页面或无关功能；新增入口专用于 Spec 明确授权的本次恢复（`overseas-images-recover.py:18`、`:178`）。UI 一致性和邻居页面视觉比较不适用：此快照只有发布脚本/测试增量，无 UI 改动。

## Stage 2：Code Quality

- 代码结构通过：两个运行脚本分别 150 / 190 行，两个测试分别 254 / 201 行，均少于 300 行；恢复按 load/preflight/recover/main 分层，见 `overseas-images-recover.py:37`、`:47`、`:118`、`:172`。归一化函数有意独立复制以避免导入新 sibling 依赖，并以 `test_overseas_images_recovery.py:29` 验证等价。
- 安全扫描通过：四个文件未匹配硬编码密钥、eval/exec、shell=True、前端 SECRET/TOKEN/KEY 和用户个人路径模式。恢复运行路径是明确固定的生产 allowlist（`overseas-images-recover.py:18`、`:182`），命令通过继承工具的参数列表执行。断言依赖由 `:173` 禁止优化模式；`test_overseas_images_recovery.py:198` 验证 -O 拒绝执行。
- 测试真实性通过：`test_overseas_images_recovery.py:128` 将实际门禁状态改变并断言 compose/publish 未调用；`:166` 注入执行过程故障并断言关停 API、不停止 native、无成功凭据；`:112` 验证真实 recover 调用顺序。它们是隔离的编排测试，未声称证明真实 Docker/systemd/HTTP 可用。
- 额外核验旧依赖链：临时复制继承脚本，将 deploy 替换为 `git show 106d07d:scripts/release/overseas-images-deploy.py` 原始字节，实际调用恢复模块 load；确认原模块没有 normalize_exec_start，统计重置仍正确通过、独立 PID/argv 漂移不相等、源码字节保持。系统调用替换为可控输入，无生产连接。
- 本次未发现需修复安全问题或质量缺陷；生产前置条件仍由恢复脚本运行时逐项验证，不得跳过或删除门禁文件后重放。

## 独立验证原始输出

默认系统 Python 无 pytest，首次尝试原始输出：

```text
C:\Users\82358\AppData\Local\Programs\Python\Python312\python.exe: No module named pytest
```

切换到项目既有 `hengxin-smart-image/backend/.venv/Scripts/python.exe` 后执行：

```text
python -m pytest scripts/release/test_overseas_images.py scripts/release/test_overseas_images_recovery.py -q
................................................ [ 57%]
...................................                                      [100%]
83 passed, 24 subtests passed in 4.59s

python -m pytest scripts/release/test_overseas_upload.py scripts/release/test_overseas_attachments.py scripts/release/test_release_retention_cli.py -q
............................ [ 45%]
..................................                                   [100%]
62 passed, 48 subtests passed in 4.23s

python -m pytest scripts/release/test_release_retention.py scripts/release/test_release_retention_docker.py -q
...............................                                          [100%]
31 passed in 0.81s

ORIGINAL_106D07D_CHAIN_PASS: original loader, statistics reset accepted, PID/argv drift rejected, source bytes unchanged
```

编译命令：

```text
python -m py_compile scripts/release/overseas-images-deploy.py scripts/release/overseas-images-recover.py scripts/release/test_overseas_images.py scripts/release/test_overseas_images_recovery.py
```

原始 stdout/stderr 均为空，退出码 0。

## 快照结论

审查开始与结束的 `review-status.currentId` 均为本报告 candidateId；未发现受控代码漂移。`approved:false` 表示主 Agent 尚未为本候选登记凭据，不是审查失败。由主 Agent 以同一 candidateId、本报告路径及两阶段 PASS 调用 review-approve；本 reviewer 未修改 `.needs-review` 或批准状态。
