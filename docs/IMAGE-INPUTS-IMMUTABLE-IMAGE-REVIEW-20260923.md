# 已测试镜像复用增量审查

日期：2026-09-23。使用 code-review skill。candidateId：`cbc80b7f376037f554e12fdfc1521c66fe9b76387ce0d015fa9907578f64d9fd`。

范围仅为 `scripts/release/image-inputs-deploy.sh:55`–`:57` 的条件构建补丁；既有脚本和产品功能继承 `docs/IMAGE-INPUTS-RELEASE-REVIEW-20260923.md:3` 的审查。本报告不表示生产部署完成。未修改代码、提交或操作生产。

## Stage 1：PASS

| 验收项 | 结论及证据 |
|---|---|
| 构建模式仍生成镜像 | 完整实现。`:55`–`:57` 仅在 build-only 模式执行原 docker build；`:58` 随后执行原 compileall；`:59` 成功返回 BUILD_COMPLETE。参数合法性限制仍在 `:7`。静态控制流逐分支核对。 |
| 部署复用已测试镜像 | 完整实现。deploy 跳过 `:56` 构建，`:58` 使用既有 release 镜像，`:61` 原 INSTALL_TEST_IMAGE_ID 比对保持。未删除或放宽安装测试凭据。 |
| 校验先于服务中断 | 完整实现。`:2` 的失败即退出和 `:61` 镜像 ID 校验先于 `:116` 第一次服务 stop；模式分支未改变后续排空、备份、迁移和恢复流程。 |
| 需求范围 | 匹配 `Product-Spec.md:5` 的受控生产切换及 `DEV-PLAN.md:6` 的固定快照发布。补丁只修正重复构建，不增加产品功能。 |

本范围无部分实现、未实现、Spec 漂移或 HIGH 问题。UI/引导/设计稿比对不适用：变更只有发布 shell 条件块，无页面变更。

## Stage 2：PASS

- 代码质量：`:55`–`:57` 使用既有 mode、双括号条件和成对 if/fi；docker 命令参数及引号未改变。脚本 166 行，小于 300 行；没有重复构建分支。
- 安全：新增两行不包含密钥、eval、用户输入拼接或扩大权限；保留 `:6` release 格式校验、`:58` 无网络编译检查及 `:61` 镜像测试凭据校验。未发现本增量新增安全问题。
- 测试真实性：独立核对实际 diff 和两个模式的控制流；没有执行实际构建或部署。主 Agent 报告镜像安装专项测试 153 PASS / 12 skip，属于交接证据，本 reviewer 未重跑，不据此声称本轮实测服务切换。
- 视觉对比不适用：`:55`–`:57` 无渲染代码，不需打开邻居页面。

验证原始输出：

```text
candidate=cbc80b7f376037f554e12fdfc1521c66fe9b76387ce0d015fa9907578f64d9fd
expected=100644:666c9d9ad85a9e2ae84863e54a3d9d5e7d28e692137bf84a40d1f9a0f10b3fc4
actual=100644:666c9d9ad85a9e2ae84863e54a3d9d5e7d28e692137bf84a40d1f9a0f10b3fc4
SCOPED_SNAPSHOT_MATCH
DIFF_CHECK_PASS
```

本地 `bash -n scripts/release/image-inputs-deploy.sh` 退出 1，WSL 返回 `Bash/Service/CreateInstance/E_ACCESSDENIED`（原输出有编码乱码），因此不记为本地语法通过。主 Agent 独立在生产服务器通过 stdin 执行纯 `bash -n`，返回 exit 0、stdout 空；该语法结果为主 Agent 提供，本 reviewer 未连接生产。此 shell 增量无新的应用编译；`:58` 的 compileall 保持且将在执行时运行。

审查结束时范围文件归一化 SHA256 与 candidate.files 一致，未发现审查期间代码变化。报告 Markdown 不纳入代码快照。由主 Agent 使用相同 candidateId、此报告路径及两阶段 PASS 执行 review-approve；不写 clean。
