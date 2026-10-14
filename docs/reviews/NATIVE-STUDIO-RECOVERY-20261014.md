# 原生工作台发布前进恢复独立审查

- candidateId：`537f0df11334b8d5c1b47a625e0a8c542231bdbb64e3d7e4591ef76e08effced`
- 基线：HEAD `7479264`；范围：`scripts/release/native-studio-deploy.py`、`native-studio-runtime.py` 的增量及新增 `test_native_studio_recovery.py`。源合同：`Product-Spec.md:1108`、`DEV-PLAN.md:1376`、`docs/NATIVE-STUDIO-RELEASE-20261014.md:45`。
- 审查开始及结束的 `review-status` 均显示上述 currentId；没有审查中代码漂移。未批准、未提交、未修改生产或应用代码。
- 结论：**Stage 1 PASS；Stage 2 PASS**。无 HIGH/MEDIUM 阻断。此结论仅批准范围内代码的审查结果，不代表生产恢复已完成。

## Stage 1：Spec Compliance — PASS

| 本轮合同条目 | 结论与证据 |
| --- | --- |
| 修正不存在的鉴权探针 | 完整实现。`native-studio-runtime.py:13` 定义真实任务 studio 与 transcript；`:115` 用于安装验证，`native-studio-deploy.py:101` 用于公开入口验证。实际注册位置 `hengxin-smart-image/backend/app/overseas/studio/router.py:13`、`:17`、`:37`；新增 AST 对照测试 `test_native_studio_recovery.py:96` 独立通过。主 Agent 的同镜像隔离证据 `output/native-studio-probe-check.log:3` 起确认旧路径404、新路径均401。 |
| 仅从已迁移、未发布前端的失败阶段继续 | 完整实现。`native-studio-deploy.py:120` 起拒绝恢复重放，限定 PHASE/FAILURE 为 verify-installed、AssertionError、已关入口及停 API、迁移完成标记；拒绝已有 INSTALLED_VERIFIED/verification.json；`:128` 实查新 schema，`:129` 检查旧前端/发布版本。`test_native_studio_recovery.py:55`、`:63` 通过。此路径限定状态而不是仅凭错误文字猜测，后续全部 installed 检查仍必须重新通过。 |
| 备份、镜像、源与 overlay 校验 | 完整实现。`native-studio-deploy.py:126` 检查已验证备份 COMPLETE；`:130` 经 `member-release-runtime.py:99` 比较实际镜像与 INSTALL_TEST_IMAGE_ID，再比 PREPARED；`:137` 校验精确 overlay；`:154` 校验原生后端哈希。CLI 始终先执行 `native-studio-deploy.py:175` 的 validate，`native-studio-runtime.py:17` 校验原 src 的 manifest/版本/全文件哈希。 |
| API 已停止、其它资源及原配置保持 | 完整实现。`native-studio-deploy.py:138` 实查停止 API 的镜像及挂载；`:142` 保持国内原生进程；`:143` 逐个检查其余容器 ID、Running、挂载及原配置文件哈希；`:153` 对照 prepare 时的 Compose 原配置，并限制 overlay 只改 image/build。`member-release-runtime.py:72` 使用 docker ps 仅列运行容器，因此恢复预检不调用完整 topology 是必要适配。启动后完整 resources_unchanged 仍在 `native-studio-runtime.py:110` 和 `native-studio-deploy.py:103` 执行，包含完整资源集合与 nativeFiles。 |
| 入口关闭与空队列 | 完整实现。`native-studio-deploy.py:155` 实查503、`:156` 复用双轮空队列检查、`:158` 核对闭合配置精确等于原边缘配置的海外503变体。底层 `overseas-hotfix-deploy.py:56` 检查 worker/broker/DB/deletion。 |
| 同一镜像继续；不重迁移、不还原旧库、不停未知执行器 | 完整实现。`native-studio-deploy.py:160` 只对海外 API 执行 up，固定 overlay，禁止 build/pull/dependencies；`:165` 进入共用 finish。recover 无 migration/backup/restore/systemctl stop。正向用例 `test_native_studio_recovery.py:39` 验证调用顺序及禁止行为。 |
| 全安装核验、前端发布和失败关闭 | 完整实现。`native-studio-deploy.py:77` 抽取原流程，`:83` 完整 installed 后再发布前端、重新开放与公开验证；`:114` 失败复用 `native-studio-runtime.py:120` 关闭海外入口/停 API 并记录结果，不停止 worker、不恢复数据库。恢复启动失败另由 `native-studio-deploy.py:162` 同样处理。三个失败阶段测试 `test_native_studio_recovery.py:72` 通过。 |
| 原应用、镜像及源包不变；独立 recovery 目录运行 | 匹配代码边界。与 HEAD diff 只有两份发布脚本和新增测试；`native-studio-deploy.py:13`、`native-studio-runtime.py:7`、`member-release-runtime.py:11` 均从脚本相邻目录加载辅助模块，复制完整 scripts/release 目录可保持依赖；validate 仍指向 work/src。复制后的清单哈希校验及实际运行结果属于主 Agent 后续部署验收，未冒称已执行。 |

本轮未新增/修改页面、组件、业务 API 或数据库迁移，UI/引导真实性/设计视觉对比不适用本增量；既有应用全量及视觉结论不在本轮重新认证。无部分实现、未实现或 Spec 漂移发现。

## Stage 2：Code Quality — PASS

- 结构和规模：`native-studio-deploy.py:77` 将共同尾段集中到 finish，避免正常发布和恢复流程分叉；两份生产脚本189/141行，测试107行，均小于300行。
- 错误处理：`native-studio-deploy.py:160` 的 API 启动及 `:81` 的安装/发布各自进入失败关闭路径。恢复门禁失败发生于启动之前，保持已经关闭的状态；RECOVERY_STARTED 防止未知结果直接重放。
- 安全扫描：对三份受审文件扫描 eval、innerHTML、危险前端密钥前缀、硬编码密码/密钥及用户绝对路径，零命中。`native-studio-deploy.py:169` 拒绝优化 Python 关闭 assert；`:174` 限定 release 字符；`:161` 复用参数化命令调用，未引入 shell 字符串执行、SQL 或秘密输出。
- 测试真实性：新增恢复测试 `test_native_studio_recovery.py:12` 对外围生产操作采用 Mock，不能当作真实生产验收。其非 API 资源基线为空；reviewer 额外在忽略目录 `output/native-studio-review-boundaries.py:11` 构造非空资源基线，实走新增检查分支，验证 ID、挂载、运行状态、配置哈希、镜像、overlay、三个失败布尔及错误类型漂移均在 API 启动前拒绝；正常基线可到 complete。11项全部通过。既有原配置/资源/排空测试一并重跑。
- 视觉：本轮未改应用及前端，无新的视觉结论；按派发范围不在维护关闭状态下等待浏览器。恢复完成后的真实入口验证仍由主 Agent 执行。
- 建议（LOW，非阻断）：可将 reviewer 的非空资源拒绝矩阵纳入后续正式回归；本轮已独立验证，不要求为当前恢复扩大修改范围。

## 独立验证原始输出

使用已有 backend venv：

```text
& hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest -q scripts/release/test_native_studio_deploy.py scripts/release/test_native_studio_runtime.py scripts/release/test_native_studio_recovery.py scripts/release/overseas-hotfix-tests.py
............................................................                                                           [100%]
60 passed, 26 subtests passed in 1.61s

& hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest -q output/native-studio-review-boundaries.py
...........                                                              [100%]
11 passed in 0.82s

python -m py_compile scripts/release/native-studio-deploy.py scripts/release/native-studio-runtime.py scripts/release/test_native_studio_recovery.py
stdout: （空）
stderr: （空）
exit_code: 0
```

日志：`output/native-studio-recovery-review-tests.log`、`output/native-studio-recovery-review-boundaries.log`。最初使用系统 Python 的命令失败，原始输出为 `C:\Users\82358\AppData\Local\Programs\Python\Python312\python.exe: No module named pytest`；已改用现有项目 venv 完成，不把首次失败算通过。

主 Agent 的同镜像隔离探针原始输出（审查者读取日志，未自行连接生产）：

```text
/app/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
/api/overseas/v1/studio/sessions 404
/api/overseas/v1/tasks/00000000-0000-0000-0000-000000000000/studio 401
/api/overseas/v1/tasks/00000000-0000-0000-0000-000000000000/studio/transcript 401
```

主 Agent 提供的85项/26子测试、镜像2174通过/187跳过/1排除及572文件哈希是其部署证据，本报告不将其计作 reviewer 独立重跑。当前只认同上述 candidate 两阶段 PASS；由主 Agent 核对快照并登记 review-approve。
