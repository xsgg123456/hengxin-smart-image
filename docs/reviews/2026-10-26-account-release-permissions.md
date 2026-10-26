# API 构建权限修复：两阶段增量审查

- 日期：2026-10-26；使用 `.agents/skills/code-review/SKILL.md`。
- candidateId：`23dba7c539f7d5908b440e08749f21f507ab412069003b3f9d38fc26124d77ee`。
- 基线：HEAD `c70c933`；范围仅 `scripts/release/account-deploy.py` 相对 HEAD 的权限修正（增加两行 chmod、替换一行 COPY）。AGENTS.md 既有用户修改及 output 手动测试素材不属于交付审查范围。
- 结论：**Stage 1 PASS；Stage 2 PASS**。无 HIGH/MEDIUM 问题。结论仅覆盖本次增量，不代表生产部署和业务冒烟完成。
- 先前完整功能及发布修复由 `docs/reviews/2026-10-26-codex-account-management-fixed.md:1`、`docs/reviews/2026-10-26-codex-account-package-fix.md:1`、`docs/reviews/2026-10-26-account-release-command.md:1` 各自限定。本轮不重复 UI 和全量产品验收。

## Stage 1：Spec Compliance

本轮逐项核对范围内合同：`Product-Spec.md:1351` 引用的 `docs/CODEX-ACCOUNT-MANAGEMENT-20261026.md:9` 发布可用与任务不中断要求，以及该合同 `:13` 私有凭据只留宿主机的边界。

| 条目 | 结论与证据 |
| --- | --- |
| 应用 UID 能读取新增代码、进入包目录 | 完整实现。`scripts/release/account-deploy.py:63` 对目录设置 0755、文件设置 0644；`:70` 去掉 COPY 统一 chmod，保留文件模式。主 Agent 提供实际 Linux 隔离镜像默认应用 UID 导入成功与 0755/0644 输出，见下。 |
| 精准复制既定 API 补丁 | 完整保持。`scripts/release/account-runtime.py:19` 固定六文件清单，`:62` 拒绝集合不同；`account-deploy.py:62` 逐文件 copyfile，`:70` 仍逐文件 COPY 至原目标。独立执行实际 AST 片段，国内/海外六文件字节完全一致、六条 COPY 目标精确匹配；`:74` 镜像内 SHA256 校验仍在。 |
| 保留生产不可变基础镜像与运行服务 | 完整保持。`account-deploy.py:56` 校验旧镜像源摘要，`:67` 标记当前不可变 Image、`:68` 复核一致；`:72` 仅构建独立新镜像。新增代码没有 compose up、服务切换或任务数据写入；切换仍由 `:283` 至 `:290` 的独立 action 分派。 |
| 私有数据没有被 chmod 或打入镜像 | 完整保持。`account-deploy.py:57` 新建业务 build 子目录，`:59` 仅复制清单中 API 源码；`:63` 遍历仅限该目录。`account-runtime.py:17` 私有凭据路径与构建目录不同，`:45` 私有输出仍设 0600；overlay 仍仅挂载业务 socket（`account-deploy.py:78`）。独立旁文件测试确认 context 外私有哨兵未触及。 |
| UI、引导、功能漂移 | 不适用 UI 与视觉验收：diff 仅构建权限处理（`account-deploy.py:63`、`:70`），未修改页面、提示、接口、表或账号行为；无新增产品功能和 Spec 漂移。 |

部分实现：无。未实现：无。Stage 1 无 HIGH，进入 Stage 2。

## Stage 2：质量、安全与测试真实性

- 质量通过：`account-deploy.py:63` 的局部遍历职责明确，无新增依赖或重复框架；文件共 299 行。chmod 失败向上传播，现有 `:292` 捕获后写失败证据并重抛，没有静默忽略。
- 权限通过：0755 目录允许应用遍历，0644 代码允许读取且没有给组/其他用户写权限；未递归 chmod 生产 `/app` 或宿主机私有目录。Dockerfile 创建发生在 chmod 之后（`:69`），它只由构建进程读取，不是六个 COPY 输入，也不需要应用 UID 访问。
- 安全通过：新增行没有令牌、shell 执行或输入拼接；COPY 名称来自固定清单。构建仍 `--network=none --pull=false`（`:72`）；原 subprocess 参数序列调用 `account-runtime.py:29` 保持。文件扫描 eval、shell=True、dangerouslySetInnerHTML、典型密钥前缀与 API 密钥变量未命中。
- Docker 语义已查官方文档：[COPY 从构建上下文复制](https://docs.docker.com/reference/dockerfile/#copying-from-the-build-context) 明确文件元数据与权限保留。既有父目录最终模式以实际镜像证据判断，不仅凭文档推断。
- 测试真实性：6 项原发布回归独立执行通过，但这些用例本身不覆盖新 Linux 目录权限。另直接提取当前 prepare 的 AST 原语句执行，验证两个业务的复制字节、chmod 参数及边界；Windows 上记录 chmod 调用，未把它表述为 Linux 模式实测。Linux 模式和应用导入由主 Agent 的真实隔离镜像测试补充，来源列明如下。
- 视觉对比不适用于该脚本 diff，无 UI 代码修改，未打开浏览器，也不把旧 UI 截图作为本次证据。

## 独立验证原始输出

`python scripts/release/account-tests.py -v`：

```text
test_command_uses_image_default_only_for_null_or_absent (__main__.ReleaseTests.test_command_uses_image_default_only_for_null_or_absent) ... ok
test_frontend_backup_and_rollback_keep_both_generations (__main__.ReleaseTests.test_frontend_backup_and_rollback_keep_both_generations) ... ok
test_frontend_rejects_shared_asset_collision_before_backup (__main__.ReleaseTests.test_frontend_rejects_shared_asset_collision_before_backup) ... ok
test_no_private_root_in_api_overlay (__main__.ReleaseTests.test_no_private_root_in_api_overlay) ... ok
test_patch_preserves_production_only_code (__main__.ReleaseTests.test_patch_preserves_production_only_code) ... ok
test_worker_rollback_refuses_after_account_change (__main__.ReleaseTests.test_worker_rollback_refuses_after_account_change) ... ok

----------------------------------------------------------------------
Ran 6 tests in 0.094s

OK
```

`python -m py_compile scripts/release/account-deploy.py` stdout/stderr 为空，退出码独立打印：

```text
PY_COMPILE_EXIT=0
```

临时内存测试直接执行 `account-deploy.py:57` 至 `:64` 和 `:69` 的原 AST；未修改交付代码：

```text
PASS domestic exact six source files; four directories 0755; six files 0644; private sibling untouched; exact COPY directives
PASS overseas exact six source files; four directories 0755; six files 0644; private sibling untouched; exact COPY directives
LINES=299
SECURITY_SCAN_PASS
```

## 主 Agent 提供的 Linux 实际安装证据

本 reviewer 读取 `output/account-management/image-permissions-check.txt:1` 并收到主 Agent 的原始 SSH 输出。临时镜像 `hengxin-smart-image-backend:account-permissions-check-20261026` 从国内当前生产不可变基础镜像构建；无生产环境变量、挂载或网络，默认应用 UID 运行。导入断言包含账号管理 router 共 8 条路由及 Settings 新增字段；未切换生产容器。本 reviewer 未再次访问服务器，该证据由主 Agent 执行，不冒充独立远程复测。

```text
API_IMPORT_PASS
[('/app/app', '0o700'), ('/app/app/account_management', '0o755'), ('/app/app/account_management/client.py', '0o644')]
```

这验证了实际 Docker 行为：既有 `/app/app` 模式仍为 0700，新目录可遍历、新文件可读，默认应用身份成功导入。海外新镜像的完整 prepare/test 仍由主 Agent 在继续发布时执行，本报告不声称已完成海外生产安装验证。

## 快照边界

审查开始的 `review-status`：

```json
{"currentId":"23dba7c539f7d5908b440e08749f21f507ab412069003b3f9d38fc26124d77ee","reviewedId":"18b88494187a7f43465ea61a670c0d8e94da23bde4333c02643fd827d21af70e","changedFiles":["scripts/release/account-deploy.py"],"approved":false}
```

本 reviewer 仅新增报告，不修复、不 commit、不登记批准、不写 clean。主 Agent 应对相同 candidateId 登记 Stage 1/2 PASS；代码如再变化须重新固定快照复核。
