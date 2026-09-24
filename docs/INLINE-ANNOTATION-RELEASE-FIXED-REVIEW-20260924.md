# 标注发布修复后独立复审 · 2026-09-24

- candidateId：`312505702d844770bf7f57abb5572d60bee033837a214ff5ef07f9951a9dd414`。
- 结论：**Stage 1 PASS；Stage 2 PASS**。无新增阻断问题，上轮 HIGH-1 已修复。此结论批准发布增量代码，不代表生产部署或最终产物验收已完成。
- 范围：相对已审功能提交 `f4e7bc6` 的 `hengxin-smart-image/frontend/package.json`、`scripts/release/package-image-inputs.py`、`image-inputs-deploy.sh`、`image-inputs-frontend.py`、新增 `test_release_recovery.py`。发布文档与 worker helper 作为依据和调用依赖阅读；不重新批准已提交标注功能。
- 依据：`.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、`Product-Spec.md:3`、`DEV-PLAN.md:3`、`hengxin-smart-image/docs/INLINE-ANNOTATION-RELEASE-20260924.md:5`。
- 独立读取当前代码、前次失败报告、构建和测试日志；未修改代码、未连接生产、未生成收费任务。范围内五文件均以 CRLF→LF 归一 SHA256 对照 review-state candidate.files，全部一致，candidateId 一致。报告不批准后续代码变化，登记由主 Agent 执行。

## Stage 1：Spec Compliance

| 发布要求 | 结论与证据 |
| --- | --- |
| 发布已审功能、前端 0.2.5 | 完整实现。`frontend/package.json:3` 为 0.2.5；`package-image-inputs.py:13` 取得提交，14–16 要求已批准快照并使用 annotation 发布名，55–57 保存 candidate、版本和 schema。 |
| 白名单包及隐私 | 完整实现打包规则。`package-image-inputs.py:20` 仅列已跟踪项目文件，22–35 限定后端源码/迁移、明确配置、非 Demo 静态构建和三个发布脚本；39–49 拒绝符号链接、数据库/密钥/源码映射/凭据及敏感文本，54–70 记录文件和归档哈希。最终归档尚待主 Agent 在批准后生成并验收，未称已扫描尚不存在的包。 |
| 保持生产完整 Compose 链 | 完整实现。`image-inputs-deploy.sh:19` 至 23 包含三个既有 overlay，41–57 核对实际容器运行状态、镜像名称、配置环境和命令；`image-inputs-frontend.py:34` 至 38 同步链记录。 |
| 固定安装镜像验证后切换 | 完整实现门槛。`image-inputs-deploy.sh:59` 至 65 构建/镜像内编译，并将 INSTALL_TEST_IMAGE_ID 与实际镜像 ID 比较。真实安装专项测试仍属部署执行阶段，不将标记文件当作测试本身。 |
| 停止接纳、排空双通道 | 完整实现。`image-inputs-deploy.sh:67` 至 74 核对 0017、未暂停、API/CLI 非终态零、native cwd；130–136 关闭 web/API/outbox、暂停并排空 API、排空停止 native。`image-inputs-worker.py:48` 至 71 检查队列、active/reserved/scheduled 与数据库；85–87 调用 native 排空维护。 |
| 备份后切换、保留业务数据 | 完整实现。`image-inputs-deploy.sh:137` 至 150 备份容器信息、可读 dump、前端/manifest/native；153 核对 0017，155–165 仅替换两个提示词文件。无迁移命令、数据库还原或降级；35 仅覆盖镜像/build，不改模型、Skill、并发或时限。 |
| 原子前端入口与旧资源保留 | 完整实现。`image-inputs-frontend.py:11` 至 20 追加静态资源，21–30 处理 gzip 首页并原子替换入口，31–48 更新 manifest。无旧资源整目录删除。 |
| 回退安全、原 HIGH-1 | 完整实现修复。`image-inputs-deploy.sh:89` 至 124 每项恢复/核对均有失败 guard；94、101 排空失败即中止恢复，不强停未知生成。116–121 恢复旧服务并核对配置、API 队列/池、native 心跳、ready 后，122–124 才开放。82–86 失败处理再次尝试关闭入口/派发和暂停，非零退出。未恢复数据库。 |
| 服务与在线交付验证 | 检查脚本完整，生产验收待执行。`image-inputs-deploy.sh:166` 至 178 核对 native、API worker、ready 和本地首页；`DEV-PLAN.md:8` 要求部署后安装哈希、镜像、schema、队列心跳及公网登录页验收。发布文档明确待执行，本报告不替代该步骤。 |
| UI 一致性、引导真实性 | 本增量无页面、组件、样式、占位或交互文案变化；唯一 frontend 变化是 `package.json:3` 版本值。无新增视觉对象；不以本报告覆盖已提交功能的视觉验收。 |
| Spec 漂移 | 未发现新增页面、API、数据表或业务范围；发布命名和无迁移路径符合 `Product-Spec.md:5`。 |

本轮范围内无部分实现或未实现的代码要求；发布执行步骤尚未完成，需继续执行并记录真实证据。

## Stage 2：Code Quality

- **代码质量通过**：`image-inputs-deploy.sh:41` 提取可重复调用的旧服务验证，77–128 将回退成功与失败分支明确分开；恢复错误不再穿透至开放步骤。范围内脚本分别 180、72、48、75 行，均小于 300 行；没有引入 TypeScript `any`。`test_release_recovery.py:11` 直接提取实际函数，避免复制一份修复逻辑造成测试失真。
- **测试真实性通过，边界明确**：`test_release_recovery.py:49` 至 70 覆盖成功、API 排空、两类 tar 恢复、旧服务启动/配置、API 恢复/验证、native 验证、health、web 启动共 11 案例。58–70 断言失败不开放、web 开启失败后再关闭，并验证成功开放前置顺序。读取原始日志全 PASS。所有系统命令是桩，证明 Shell 控制流，不证明真实 Docker/systemd/数据库故障恢复；SQL 失败、manifest 恢复失败、native-stop 失败等 guard 尚无各自独立注入用例，属测试覆盖边界，代码均显式 guard。
- **安全扫描通过本次增量**：对五文件扫描 eval、HTML 注入、VITE 密钥、明文 password 和典型私钥前缀，没有命中危险实现。`image-inputs-deploy.sh:6` 限制发布标识，3 使用 umask 077，31–34 检查 manifest 路径与文件哈希；Shell 路径引用、Compose 数组和 Python subprocess 参数均未新增字符串求值。`package-image-inputs.py:49` 的敏感模式用于拒绝打包，不是内置密钥。固定 `/opt/` 路径对应部署目标，不是开发者私有目录泄漏。
- **恢复失败的能力边界**：`image-inputs-deploy.sh:82` 至 86 是尽力再次关闭；若 Docker 和数据库本身不可用，脚本无法保证外部状态确实关闭。代码不继续执行正常开放，并明确 `ROLLBACK_BLOCKED_NO_AUTOMATIC_REOPEN` 非零退出。运维应据此人工核实，不把该提示解释为关闭操作已被外部系统确认。
- **依赖风险未增加**：实读 `output/annotation-release-20260924/dependency-audit.json` 为 critical 0 / high 33 / moderate 30 / low 1。范围没有依赖或锁文件变更；本轮 PASS 不表示历史依赖告警已解决。
- **视觉比较不适用本增量**：`frontend/package.json:3` 仅版本变化，发布脚本没有 UI 渲染逻辑；无需打开新页面与邻居页面进行不存在的增量比较。生产公开登录页仍需按发布计划验收。

## 原始验证输出

读取 `output/annotation-release-20260924/recovery-tests.log`：

```text
PASS success
PASS api-drain
PASS native_restore
PASS app_restore
PASS old_start
PASS old_verify
PASS api-resume
PASS api-verify
PASS native_verify
PASS health
PASS web_start
```

读取 `output/annotation-release-20260924/build.log` 末尾：

```text
dist/assets/index.vue_vue_type_style_index_0_lang-CJIHvokJ.js                         813.93 kB │ gzip: 275.57 kB
dist/assets/index-DAC2qLhQ.js                                                       1,623.37 kB │ gzip: 535.46 kB
✓ built in 30.53s
```

主 Agent 提供 typecheck、bash -n、py_compile 成功证据；`typecheck.log` 零字节不能单独证明退出码。本 reviewer 尝试直接运行 Python 的原始结果如下，未冒充为独立编译通过：

```text
python: The term 'python' is not recognized as a name of a cmdlet, function, script file, or executable program.
```

随后使用项目 `backend/.venv/Scripts/python.exe` 对三个 Python 文件调用内置 compile 独立验证，退出码 0，原始输出：

```text
PYTHON_COMPILE_OK 3
```

11 案例执行与 bash -n 的退出码 0 由主 Agent 提供；本 reviewer 独立审查测试实现并实读日志，没有重复连接服务器。主 Agent 明确测试在远端临时目录执行实际 recover 的 Shell 桩，未调用生产 Docker/systemd 操作。

快照核对实测输出：

```text
312505702d844770bf7f57abb5572d60bee033837a214ff5ef07f9951a9dd414
True hengxin-smart-image/frontend/package.json
True scripts/release/image-inputs-deploy.sh
True scripts/release/image-inputs-frontend.py
True scripts/release/package-image-inputs.py
True scripts/release/test_release_recovery.py
```
