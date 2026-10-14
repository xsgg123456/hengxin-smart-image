# 0.2.33 上传发布容量审查

- candidateId：`013f660dda8355774d169bd7e625309130ba26acc2606cac1a3bf144d79602d0`
- 审查范围：本次七个受控文件差异（前端 package.json、package-overseas.py、test_package_overseas.py、新增三个 overseas-upload 发布模块及 test_overseas_upload.py），同时核对发布文档、变更记录和调用的既有发布保护。
- 基线：功能提交 `e700d87` 已独立审查；本次不重新批准整个历史产品或宣称生产验收完成。
- 依据：AGENTS.md、code-review SKILL.md、docs/HARNESS-REVIEW.md；Product-Spec.md:1129–1135、docs/UPLOAD-RELEASE-20261014.md:5–15。
- 结论：**Stage 1 PASS；Stage 2 PASS。没有发现本次范围内的 HIGH/MEDIUM 阻断项。** 允许主 Agent 为同一快照登记凭据；实际镜像测试、部署及线上验收仍需按门禁执行。

## Stage 1：Spec Compliance

| 条目 | 结论与证据 |
| --- | --- |
| 版本 0.2.33，国内 0028/海外 0015，无迁移 | 完整实现。`scripts/release/overseas-upload-deploy.py:25` 校验 manifest、前端版本和哈希，`:34` 校验两库版本；部署路径没有迁移调用。`scripts/release/package-overseas.py:21` 与 `hengxin-smart-image/frontend/package.json:3` 版本一致。 |
| 两层海外代理 500 MB + 64 KiB | 完整实现。`scripts/release/overseas-upload-proxy.py:4` 精确定位唯一海外 location，`:5` 固定 500065536、300 秒、HTTP/1.1 与关闭请求缓存；`:12` 保留 location 外全部文本及已有上游。重复/缺失 location 拒绝。对应独立通过的 `scripts/release/test_overseas_upload.py:84`。 |
| 国内与身份业务不变 | 完整实现。`scripts/release/overseas-upload-deploy.py:134` 比对国内/身份拓扑、原容器身份、原生进程 PID、挂载及配置摘要；`:208`、`:221` 只操作海外 api，`:66` 仅停止海外两项原生服务。继承测试覆盖国内重启、Redis 身份、挂载和原生配置漂移（`scripts/release/overseas-hotfix-tests.py:241`）。 |
| 单文件容量的运行资源 | 完整实现指定发布配置。`scripts/release/overseas-upload-resources.py:4` 明确 3221225472 bytes；`:12` 只归一 mem_limit 后交既有严格 settings 比对，无法顺带修改其他容器或环境/挂载。`scripts/release/overseas-upload-deploy.py:157` 检查实际 HostConfig.Memory。`output/upload-memory-config.json:1` 证明旧 402653184 bytes 低于文件上限；该问题已经修复为明确的资源变更。 |
| 实际镜像测试先于切换 | 完整实现门禁。`scripts/release/overseas-upload-deploy.py:277` 先调用既有 build；`scripts/release/overseas-deploy.py:29` 校验镜像内源码哈希并执行安装测试，通过才写 INSTALL_TEST_IMAGE_ID；`scripts/release/overseas-upload-resources.py:21` 在该镜像 ID、3GiB 限额、无网络容器中运行真实字节边界测试，成功后才写容量凭据。prepare `:87`、deploy `:181` 再次绑定该 ID。当前报告不把尚未执行的服务器构建描述成已通过。 |
| 停止接纳、双轮排空、备份后切换 | 完整实现。`scripts/release/overseas-upload-deploy.py:204` 关闭外层并确认 503，停止 API 后进入 `:66` 双轮 DB/active/reserved/scheduled/queue/unacked 检查，再停止 worker；`:214` 备份且要求 COMPLETE 后才切换。已有 `scripts/release/overseas-update-runtime.py:111` 使用 pg_restore --list 验证 dump。 |
| 内层 Nginx 安装顺序 | 完整修复。`scripts/release/overseas-upload-deploy.py:226` installed 验证完成后才 `:227` 安装内层配置，随后 nginx -t/reload；`scripts/release/test_overseas_upload.py:65` 断言 installed < install-inner < reload < proxy。不会再在正常路径停 API 时触发新配置上游 DNS 解析失败。 |
| 失败处理、禁止重放及覆盖数据库 | 完整实现。`scripts/release/overseas-upload-deploy.py:179` 拒绝重放；`:252` 异常路径关闭外层、恢复属于本次发布的内层内容、finally 停海外 API 并写 FAILURE；不自动停止可能存在新任务的执行器、不自动恢复数据库。`scripts/release/overseas-upload-proxy.py:53` 仅恢复内容仍精确等于本次 after 的配置。关闭/恢复本身失败仍会落入停 API 与故障记录路径，需人工检查恢复。 |
| 安装与公开验收 | 完整实现脚本检查。`scripts/release/overseas-upload-deploy.py:151` 校验源码/镜像/原生进程/健康/Skill；`:236`、`:244` 核对前端内容和公开入口资产哈希；代理 `:61` 检查两层配置与准入阈值。curl 只发 Content-Length 头，是代理准入/鉴权检查，不能证明真实生产 500MB 上传成功。 |
| 打包完整性与引导真实性 | 完整实现。`scripts/release/package-overseas.py:29` 纳入代理 include，`:42` 强制三个新模块存在，`:141` 缺项拒绝；测试独立通过。发布文档明确尚待部署，不将计划冒充线上结果（`docs/UPLOAD-RELEASE-20261014.md:25`）。 |
| UI 与 Spec 漂移 | 本次前端只改版本（`hengxin-smart-image/frontend/package.json:3`），无页面/组件/样式差异；不重新做历史功能邻居页面视觉验收。生产正式页面验证保留为发布完成条件（`docs/UPLOAD-RELEASE-20261014.md:15`）。没有新增业务 API、数据库表或超出授权范围的功能。 |

## Stage 2：Code Quality

- 结构通过：新增 deploy 290 行、proxy 72 行、resources 26 行，职责分别为切换编排、代理配置和资源门禁；没有为本次修改既有通用 settings 比较器来放松全部发布。证据：`scripts/release/overseas-upload-resources.py:12`、`scripts/release/member-release-runtime.py:116`。
- 断言安全通过：入口先拒绝 Python 优化模式，避免 -O 移除安全断言。测试明确调用本次 upload 脚本，分别覆盖 -O 与 PYTHONOPTIMIZE=1（`scripts/release/overseas-upload-deploy.py:267`、`scripts/release/test_overseas_upload.py:56`）。
- 安全扫描通过：对本次三个发布模块及测试扫描 eval、shell=True、硬编码密码/令牌、前端秘密变量，无命中。命令采用参数列表，生产固定目录及已有 Docker/systemd 资源名属于发布所需配置；无新增任意 shell 输入或数据库写入拼接。证据：`scripts/release/overseas-upload-resources.py:23`、`scripts/release/overseas-upload-proxy.py:68`。
- 测试真实性通过：继承故障矩阵运行在本次模块上，类名替换确保矩阵创建的也是新 UploadReleaseTests；独立用例覆盖代理安装顺序、公开验证失败恢复、资源漂移。证据：`scripts/release/test_overseas_upload.py:23`、`:48`、`:117`、`:120`；`scripts/release/overseas-hotfix-tests.py:124`。
- **证据边界（非新增阻断）：** 容量测试使用真实 500000000 bytes、实际 multipart 解析和超限校验（`hengxin-smart-image/backend/tests/test_overseas_upload_limits.py:13`、`:43`），但没有覆盖 500MB TXT/CSV 解码加真实存储的端到端峰值，也没有证明并发上传容量。3GiB 是本次配置与受限测试门禁，不是任意格式/并发的容量保证。保留格式/解析限制；不得将该测试或 header-only curl 写成生产完整大文件上传验收。
- 视觉对比不适用于本次七文件发布基础设施差异；历史 UI 的浏览器证据见 `docs/UPLOAD-LIMITS-VALIDATION-20261014.md:8`，不以该历史记录代替部署后的正式页面检查。

## 独立验证原始输出

命令：`hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest -q scripts/release/test_overseas_upload.py scripts/release/test_package_overseas.py`

```text
...........................................      [100%]
43 passed, 24 subtests passed in 2.13s
```

对六个本次 Python 文件执行 `python -m py_compile`，退出码 0，stdout/stderr 均为空。

前端构建使用已有本次版本原始日志，未重复构建。`output/upload-release-build.log:4`、`:769`：

```text
> vue-tsc --noEmit && vite build
✓ built in 36.92s
```

审查结束前运行 review-status，原始关键输出：

```json
{"currentId":"013f660dda8355774d169bd7e625309130ba26acc2606cac1a3bf144d79602d0","reviewedId":"916a6f8d790924cce7a188975791c5f9d14a53add81d8bc200abb8e96dda8e58","approved":false}
```

审查期间受控代码未漂移。报告仅新增 Markdown，不写 clean、不登记批准、不修改实现、不提交、不执行生产写入。主 Agent 可登记本报告对应快照，随后严格执行实际镜像安装测试/3GiB 边界测试与生产部署验证。
