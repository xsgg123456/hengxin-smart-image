# 历史发布台账校正与部署重试独立审查

结论：Stage 1 PASS；Stage 2 PASS。未发现本次限定执行范围的阻断项。未执行两份维护脚本、未连接生产写入、未复跑应用测试。

## 快照与范围

- 主 Agent 提供应用 candidateId：`c7e1e372b5f4c3ba2873cb5951b714f3ba10b1842774268cf8089058d41311d5`。本报告不重新批准应用代码，也不声称 ignored 维护脚本属于该 candidate。
- 单独绑定 `output/studio-sessions-release/reconcile-member-ledger.py` SHA256：`9f42c2d3c1ed20f6a7b80e248071b1e28fefcd0f0e3ee89328e3a9ffcab68dc1`。
- 单独绑定 `output/studio-sessions-release/retry-deploy.py` SHA256：`b06d8b7039a44b91a618e5a4199a71b5f86b4e9de6b4baea607fe9b11667ad36`。
- 依据：主 Agent 的狭窄维护交接、`Product-Spec.md:1320` 的历史授权补丁与 `Product-Spec.md:1334` 的当前正式发布授权；历史证据见 `docs/OVERSEAS-MEMBER-GRANT-20261023.md:26`、`:27`、`:28`、`:30`；已有生产只读审计见 `output/studio-sessions-release/retention-audit.json:1`。
- 审查前后两脚本 SHA256 一致；工作树另有 `AGENTS.md` 修改及 package-final 审查报告，均不属于本次范围。实现未修改。

## Stage 1：完整实现

1. 使用原 Store/Docker 和全局锁：校正脚本第 9–13 行；实际锁实现 `scripts/release/release-retention-state.py:91`，Linux 使用非阻塞排他 flock。Docker 快照仅接受唯一运行且健康的服务，见 `scripts/release/release-retention-docker.py:37`。
2. 校正仅接受本次尚未进入发布事务：校正脚本第 14–18 行检查无 receipt、无 DEPLOY_STARTED/PHASE、exitCode 1、pending prepared 且无 before。真实审计对应字段一致。原漂移检查在记录 before、写 deploy 阶段和调用 main 之前，见 `scripts/release/release-retention.py:82`、`:90`、`:91`、`:94`、`:96`。
3. 历史凭据键兼容：校正脚本第 20–27 行使用原 Docker inspect 的 `Image`/`Id`、prepared 的 `beforeId`/`image`；写出来源见 `scripts/release/overseas-member-grant.py:106`、`:107`。最终 probe 的 equal、paused、migration、toggle 字段见 `scripts/release/overseas-member-grant-probe.py:34`、`:47`、`:48`；allTaskActionsVerified 是动作数量，见 `:62`，历史一任务九动作的 truthy 判断兼容。最终恢复后凭据语义见历史发布文档第 27–28 行。
4. 精确旧、新镜像及国内、身份服务不漂移：校正脚本第 23–30 行，镜像存在检查使用 inspect 返回的 Id。与真实审计中的 f208→a49ced、国内/身份 current==live 完全一致。
5. 备份先于写台账；仅更新海外 current/previous 并登记历史 completed：校正脚本第 31–38 行。completed 保存三组完整镜像快照，匹配 `release-retention-state.py:58` 的 schema 及 `release-retention.py:53` 的既有格式。全量 pending 和 successCounters 保持，避免把早于失败的历史成功算作新增 GC 年龄；代码第 36 行校验，内存验证亦通过。其余组 history 不变。
6. 校正不执行服务、数据库或清理命令：校正脚本第 6–45 行全部远端代码仅调用 Docker snapshot/inspect、Store load/write/report；没有调用 managed、advance 或 cleanup。receipt 记录历史最终凭据 SHA256，并复读台账/快照，见第 39–43 行。
7. 重试严格限制首次预检失败：重试脚本第 9–13 行检查精确 release/action/exitCode、drift 错误、无发布/迁移/失败标记、无备份目录、有校正凭据；第 14 行 exclusive marker 防止重复启动；第 15–16 行保留首次日志和结果。
8. 重试调用原入口，不绕门禁：重试脚本第 18 行。原入口 `scripts/release/overseas-studio-sessions-deploy.py:289` 仍经 optimize 检查与 release-retention.managed，全局锁、版本漂移、安装凭据与应用发布门禁保持。

部分实现、未实现、Spec 漂移：本次限定维护交接内均无。UI、设计稿、邻居视觉对比不适用：两份脚本均无页面、组件或用户流程修改。

## Stage 2：质量、安全与故障边界

- PASS：两文件分别 52、29 行，职责分别为单次校正和单次重试，未引入依赖。SSH/SCP 使用参数数组、StrictHostKeyChecking=yes、BatchMode=yes；私钥仅引用既有路径，无硬编码密钥正文。远端 shell 命令中的主机/路径为固定常量，无外部输入拼接，见校正脚本第 46–50 行、重试脚本第 21–28 行。
- PASS：台账和校正证据采用既有临时文件、fsync、原子 replace，见 `scripts/release/release-retention-state.py:115`、`:119`。备份在台账变化前持久化。
- PASS（需按已给操作约束处理）：校正的台账和 receipt 不是一个原子事务。若第 38 行写入后、第 42 行前中断，下一次执行将因旧 current 或 completed 条件失败而安全停止；不得盲重跑，应先检查台账、备份和 receipt。receipt 已写但本地 SSH 超时也须先读服务器凭据。此行为符合主 Agent 明确承诺的先检查再处理，不表示自动恢复。
- PASS（同上）：重试 marker 第 14 行先于日志重命名/启动；在后续任意点中断都不能直接重跑。原日志可能已迁移，子进程也可能仍在运行；检查 marker、两个日志/result 和原发布状态后处理。重试启动返回 PID 仅代表启动 launcher，不代表部署成功；最终结果以第 19 行 result 和正式发布凭据为准。
- 测试边界：独立审查执行外层及内嵌远端代码 compile，审计断言和内存 schema 校验；未执行远端真实写入、未测试故障注入，不把这些称作已验证。审计没有 successCounters 完整数值，内存校验使用失败基线 2 的代表值，只验证结构和变换；实际脚本直接保留真实字段。

## 编译与只读验证原始输出

以下均 exit code 0。使用 `compile(source, ..., 'exec')` 及 AST 提取内嵌字符串，未运行维护脚本：

```text
reconcile-member-ledger.py: outer + remote compile PASS; SHA256=9f42c2d3c1ed20f6a7b80e248071b1e28fefcd0f0e3ee89328e3a9ffcab68dc1
retry-deploy.py: outer + remote compile PASS; SHA256=b06d8b7039a44b91a618e5a4199a71b5f86b4e9de6b4baea607fe9b11667ad36
Audit identity, field names, prepared state and no-start assertions: PASS
Ledger transformation + real Store.validate (in-memory; representative counter baseline): PASS
```

本结论仅覆盖上述 SHA256 的两份维护脚本及所述单次人工监控执行方式；如脚本改变，需重新绑定并审查。未写 `.needs-review`，未登记应用 candidate 的新批准。
