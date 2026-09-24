# 标注发布增量独立审查 · 2026-09-24

- candidateId：`febf4d2ea367357bd955d8f0d49f8ff1716d9364060861767f8ee3e10f65a03e`。
- 范围：相对功能提交 `f4e7bc6` 的 frontend/package.json、scripts/release/package-image-inputs.py、image-inputs-deploy.sh、image-inputs-frontend.py 及发布文档；worker helper 只作为调用依赖阅读。已提交标注功能不重复审查；无生产修改、无收费生成。
- 使用 `.agents/skills/code-review/SKILL.md`，依据 Product-Spec.md:3、DEV-PLAN.md:3 和 hengxin-smart-image/docs/INLINE-ANNOTATION-RELEASE-20260924.md:5–18。
- 结果：**Stage 1 FAIL（1 HIGH）；Stage 2 未执行**。不得登记双 PASS。
- 快照核对：审查末尾读取 review-state 的 candidateId，并将范围内四个代码文件规范化 CRLF 后的 SHA256 与 candidate.files 逐一比较，一致；未发现本轮范围内代码漂移。本报告不批准后续改动。

## Stage 1：逐项核对

| 条目 | 结论和证据 |
| --- | --- |
| 版本及打包范围 | 完整实现：frontend/package.json:3 为 0.2.5；package-image-inputs.py:14–16 要求已批准快照并使用 annotation 发布名；22–35 白名单后端、迁移、生产静态资源及发布脚本；39–49 过滤私密文件和敏感文本。此处为代码核对，最终产物扫描尚待实际打包。 |
| 完整旧 Compose 链 | 完整实现：image-inputs-deploy.sh:19–22 和 image-inputs-frontend.py:34–38 均包含三个现有 overlay；deploy.sh:40–53 对比运行状态、镜像名称、环境与命令。生产预检来自主 Agent 和发布文档:14，本 reviewer 未重新连接生产。 |
| 安装测试门槛及镜像绑定 | 完整实现门槛：deploy.sh:56–62 构建、安装镜像 compileall，并要求 INSTALL_TEST_IMAGE_ID 与当前镜像 ID 相等。专项测试结果仍需操作者在真实构建镜像上生成后才可填写标记；本次未宣称安装专项测试已经通过。 |
| 停止接纳、排空及备份 | 完整实现正常路径：deploy.sh:64–71 核对 0017、未暂停、API/CLI 非终态零及 native cwd；112–117 关闭入口/outbox、暂停 API、排空双 worker 后停止；118–130 备份旧镜像信息、可读 dump、前端/manifest/native。helper image-inputs-worker.py:48–71 核对 API active/reserved/scheduled 和数据库；85–87 调用 native 排空维护。 |
| 沿用 0017、不改模型/Skill/时限 | 完整实现：deploy.sh:35 仅覆盖镜像/build；133–145 不运行迁移，仅替换两份 native 提示词文件；API schema 再次验证为 0017。 |
| 前端原子切换、保留旧资源 | 完整实现正常路径：image-inputs-frontend.py:11–20 追加资源；21–30 清理旧 gzip 首页并原子替换新首页；31–48 更新发布 manifest。 |
| 服务验证及在线交付 | 脚本检查已实现，实际部署验收待执行：deploy.sh:148–159 检查 native、API worker、ready 和首页；helper:42–46 核对池 5，89–102 核对 native 队列/心跳。安装文件哈希、公网匿名登录页由 DEV-PLAN.md:8 的发布后步骤覆盖，发布文档:22 明确待执行，没有虚构已完成。 |
| 回退不恢复数据库、不强停未知任务 | 部分实现：deploy.sh:82–89 排空失败会阻断，100–105 不降级或恢复数据库；但恢复失败后仍可能开放入口，见 HIGH-1。 |
| UI 一致性、引导真实性 | 本增量只改版本和发布脚本，没有组件、页面、交互或提示文案变化；git diff 范围与上述四文件一致。本轮无新增可进行视觉比较的页面，不复用本结论覆盖已提交功能的视觉审查。 |
| Spec 漂移 | 未发现本增量增加页面/API/表/业务行为；发布名、overlay、schema 与 Product-Spec.md:5 授权相符。 |

### HIGH-1：恢复步骤失败后仍开放入口和任务派发

- 要求：发布文档 `hengxin-smart-image/docs/INLINE-ANNOTATION-RELEASE-20260924.md:18` 要求保持接纳关闭、排空、恢复旧镜像/前端/native/manifest；Product-Spec.md:5 要求受控备份切换。
- 证据：`scripts/release/image-inputs-deploy.sh:78` 在 recover 中执行 `set +e`；90、93–96 的 tar/systemctl/cp 及 102 的旧镜像启动没有返回值检查。103 无条件将通道设为 `paused=false`，104 再启动 API/web。恢复失败不会阻断后续开放操作。
- 可确定的故障路径：新版 worker 启动后发生部署错误 → recover 关闭入口并排空 → native.tar 或 application.tar 解包失败，或者旧 worker 启动失败 → 错误被 `set +e` 忽略 → 仍恢复 API/web 和派发。此时可能运行未恢复的提示词、混合前后端、或没有健康 worker 的服务。此次删除旧 migrated 分支后，原本迁移后保持 HTTP 关闭的路径也改为无条件开放，因此直接涉及本增量。
- 验证方式：逐行控制流审查；未在生产注入故障。该行为由显式 `set +e` 和无 guard 的顺序命令确定，不依赖未知第三方行为。
- 修复要求：恢复文件、重启旧服务、核对旧镜像及 native/API worker 健康均须成功，否则保留 HTTP/派发关闭并明确报告具体失败；所有恢复验证完成后才开放通道和入口。加入隔离故障注入覆盖 tar 恢复、旧服务 up 和 worker 健康失败三条路径，再重新固定候选快照审查。

## 编译证据及边界

读取主 Agent 生成的 `output/annotation-release-20260924/build.log` 原始末尾：

```text
dist/assets/index.vue_vue_type_style_index_0_lang-CJIHvokJ.js                         813.93 kB │ gzip: 275.57 kB
dist/assets/index-DAC2qLhQ.js                                                       1,623.37 kB │ gzip: 535.46 kB
✓ built in 30.53s
```

`typecheck.log` 为零字节，单靠该文件不能独立证明退出码；主 Agent 提供 typecheck、bash -n 和 py_compile 已通过，本 reviewer 未重复取得这些命令的成功退出证据。尝试本地 Python 验证的原始错误如下，未将其记为通过：

```text
python: The term 'python' is not recognized as a name of a cmdlet, function, script file, or executable program.
Unable to create process using '"C:\Users\82358\AppData\Local\Programs\Python\Python312\python.exe" .codex/hooks/harness.py review-status'
```

依赖审计文件 metadata 实读为 critical 0 / high 33 / moderate 30 / low 1。因 Stage 1 HIGH 阻断，未执行 Stage 2 安全、测试真实性、代码质量或视觉评估，不能把旧依赖审计数字解释成安全通过。
