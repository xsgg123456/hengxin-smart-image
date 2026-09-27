# CLI 成品整改发布脚本独立审查（2026-09-27）

- candidateId：`04acd36b4ce951ac8bb160b56f576a32ddecd5de92255cc53efc7f7d004a8631`。
- 范围：`scripts/release/delivery-deploy.sh`、`delivery-native.py`、`package-delivery.py`、`test_delivery_native.py`、`test_package_delivery.py`。产品实现以已审提交 `53e5586` 为基础，不重复扩大审查。
- 依据：Product-Spec.md:3–5、DEV-PLAN.md:3–8；已读取 AGENTS.md、code-review SKILL.md 和快照协议。
- 结论：**Stage 1 PASS；Stage 2 PASS**。没有 HIGH/MEDIUM 阻断。仅批准上述脚本快照；不表示生产已经部署或安装验证已完成。
- 实际 `review-status` 返回 currentId 与送审编号一致，changedFiles 正好为以上五文件；approved=false 是尚待主 Agent 登记的正常状态。审查未修改实现、未接触生产、未提交代码。

## Stage 1 · Spec Compliance

| 条目 | 结论及证据 |
|---|---|
| 固定已审 Git 快照、唯一版本、后端白名单包 | 完整实现。package-delivery.py:37、64、73、104，要求批准快照、已提交且工作树一致，归档前复核；提交短号构成版本。test_package_delivery.py:48 验证真实临时 Git 仓库归档与脏文件拒绝。 |
| 隐私检查 | 完整实现。package-delivery.py:14–26、49，排除环境文件、凭据文件、运行目录、前端；扫描选中的源码及测试，只允许明确的既有负例。独立扫描当前已跟踪的269项选中源码通过；新增测试与脚本的构造负例没有完整凭据。test_package_delivery.py:18–46覆盖白名单、密钥、个人路径及精确例外。 |
| 生产旧版本、完整覆盖链和配置核对 | 完整实现。delivery-deploy.sh:19–58 复用指定覆盖链，核对四个在运行后端容器的镜像、环境和命令；只接受既定 materials-20260924-2cdb4ff。 |
| build-only 与隔离安装测试门槛 | 完整实现脚本职责。delivery-deploy.sh:60–79 构建镜像、按锁文件哈希下载两个新增纯Python依赖、无网络编译；deploy必须匹配外部安装测试记录的镜像ID。**完整隔离测试由主流程执行并生成 INSTALL_TEST_IMAGE_ID，本报告未把compileall当成功能测试。** |
| 停止接纳、排空、备份 | 完整实现。delivery-deploy.sh:80–87 先拒绝非空任务与意外schema/暂停状态；131–146关闭入口、暂停通道、调用既有两类Worker排空、备份配置、镜像身份、数据库、native源码和venv；pg_restore仅列目录核验，不回写业务库。既有image-inputs-worker.py:32、81及backend/app/worker/maintenance.py:32提供排空语义。 |
| native更新文件是否足够 | 完整实现。delivery-native.py:12–17列16项，独立比较 `git diff --name-only 2cdb4ff 53e5586 -- hengxin-smart-image/backend`，去除测试后与白名单集合完全相等。新模块、原流程、查询展示、恢复工具以及两份依赖文件均覆盖，没有遗漏或额外产品文件。 |
| 源码、venv权限及回退 | 完整实现。delivery-native.py:20–69 拒绝路径链接并保留原uid/gid/mode，新文件继承已有codex_runner权限；109–137保存源码存在性和venv离线归档；153–210校验归档摘要、安全成员后恢复，新增源码被删除，失败依赖保留在failed-venv。测试实际覆盖新增/旧文件、依赖、硬链接、元数据、损坏归档及越界，Windows创建真实symlink一例跳过。 |
| 回退失败保持入口关闭，恢复验证后再开放 | 完整实现。delivery-deploy.sh:89–128。恢复先关入口，排空已启动的新worker，恢复native，旧镜像启动并通过配置/队列/native心跳/健康核验后才解除暂停并开web。失败调用blocked再次关入口。独立执行实际recover函数的10项shell stub演练全部通过，见下方输出。 |
| 保留模型/Skill/并发/超时/凭据，无迁移/前端发布/收费生成/历史批量补收 | 匹配。delivery-deploy.sh:19–26、38、150–164继承既有配置，仅替换后端镜像及native白名单；无迁移、repair_delivery批量运行或生成命令。队列检查沿用image-inputs-worker.py:46的并发5断言。 |
| 安装哈希、CLI/队列、schema、公网健康及匿名鉴权 | 脚本内执行入口包哈希、依赖检查、codex身份import、两类worker、0017和本机健康验证（delivery-deploy.sh:29–41、149–164）；**实际安装文件哈希、公网健康与匿名鉴权须在主发布流程继续验证并记录，当前审查没有这些生产运行证据**。DEV-PLAN.md:8是整个发布验收要求，不能仅凭本报告宣称完成。 |
| UI / Spec漂移 | 本范围无UI、页面、API或表结构新增，不适用设计稿/邻居页面视觉比对。新增脚本皆属于已授权打包、部署、回退与验证。 |

## Stage 2 · Code Quality

- 命名、职责、规模通过：deployment / native文件操作 / packaging分离；五文件均小于300行（delivery-deploy.sh:1、delivery-native.py:1、package-delivery.py:1、两测试文件:1）。
- 安全检查通过：未见真实硬编码密钥或动态执行输入。部署shell参数白名单、默认umask077、包哈希检查见delivery-deploy.sh:2–18、29–41；归档边界、禁止目录穿越/硬链接/符号链接父节点写入见delivery-native.py:80–106。native隔离root权限操作保留既有所有权，不把安装文件留为root私有。
- 测试真实性通过：独立复跑16例，15通过、1因Windows创建symlink权限跳过；未把跳过算通过。另从既有test_release_recovery.py内存适配函数名与当前阻断文案，直接抽取本候选recover函数执行10例；它证明分支顺序与失败关闭，不证明真实Docker/systemd或Linux权限运行。
- LOW增强建议：delivery-native.py:117–125源码备份仅保存metadata和字节，venv才有SHA256（:135、:158）。可后续给每份源码备份增加摘要，以便主动发现备份介质损坏；当前正常离线回退及归档边界已有测试，不构成本次阻断。
- LOW增强建议：将本次恢复函数故障演练固化为delivery专用测试文件，避免未来依赖临时适配既有harness（test_release_recovery.py:9–95）。当前候选已经实际运行演练，不属于未经测试的回退声明。

## 原始验证输出

Python unittest 命令：`python -m unittest discover -s scripts/release -p 'test*delivery*.py' -v`。

```text
Ran 16 tests in 2.334s

OK (skipped=1)
```

跳过原因：Windows WinError 1314，当前token无创建symlink权限。临时Git测试有读取用户global ignore的Permission denied warning，但命令及测试均成功。

`D:/Apps/Git/bin/bash.exe -n scripts/release/delivery-deploy.sh`：exit_code=0，stdout/stderr为空。

源码原生compile检查、独立故障演练及白名单/隐私检查原始输出：

```text
PASS success
PASS api-drain
PASS native_restore
PASS old_start
PASS old_verify
PASS api-resume
PASS api-verify
PASS native_verify
PASS health
PASS web_start
NATIVE_WHITELIST_EXACT_MATCH 16
TRACKED_SELECTED_PRIVACY_PASS 269
PYTHON_COMPILE_PASS
```

本次未运行生产部署、付费生成、历史补收。Linux容器安装测试、完整产物隐私审计及真实部署验收由主流程继续执行。主 Agent 可登记本candidate两阶段PASS；如代码变化须重新固定候选并复核。
