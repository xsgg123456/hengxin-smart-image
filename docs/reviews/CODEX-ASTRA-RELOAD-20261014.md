# Codex 发布入口 reload 等待增量审查

- 最终 candidateId：`a6e3b62078a2c7213f931f50c7f03585a54ef8540bcf2347ae87b0a14d65c551`
- 已审基线：`d2ac7d1`；基线报告：`docs/reviews/CODEX-ASTRA-20261014.md`。
- 范围：相对基线的 `scripts/release/overseas-codex-deploy.py`、`scripts/release/test_overseas_codex_deploy.py`、`docs/OVERSEAS-CODEX-ASTRA-20261014.md`。不重审未变更历史功能。
- 使用 `.agents/skills/code-review/SKILL.md`。仅本地审查与隔离测试，未执行生产写入、修改实现、提交或登记批准。
- 最终结论：**Stage 1 PASS；Stage 2 PASS**。无 HIGH / MEDIUM 阻断问题；不代表生产切换已完成。
- 快照变更记录：初始 `25904023153ec4caff96f24ec727ad32ed8b895e40023f7e19e269140bddd509` 存在超时后仍成功的问题；已反馈主 Agent。主 Agent 修复后提供上述最终候选，本 reviewer 重新从 Stage 1 复核完整增量，未将旧结论覆盖新版本。最终复核 review-status 的 currentId 与最终候选一致。

## Stage 1：Spec Compliance — PASS

| 条目 | 判定与证据 |
|---|---|
| 兼容 graceful reload 延迟 | 完整实现。`scripts/release/overseas-codex-deploy.py:49` 循环取双路状态，`:63` 每轮至多等待 1 秒；`scripts/release/test_overseas_codex_deploy.py:33` 覆盖第一轮部分关闭、第二轮全闭后成功。独立复跑通过。 |
| 两路同一轮均为 503 才继续 | 完整实现。deploy `:52` 每轮重建状态数组，`:61` 必须精确匹配两项 503；`:171` 关闭检查成功后才停止 API。测试 `:33` 证明部分关闭需要继续等待，不能提前返回。 |
| 20 秒预算，超时中止 | 完整实现。发布文档 `docs/OVERSEAS-CODEX-ASTRA-20261014.md:16`；deploy `:54` 每请求前计算剩余预算，`:44` 同时传递 curl max-time 与 Python 子进程 timeout，`:58` 在成功判断之前再次拒绝超时，`:63` sleep 不超过剩余预算。测试 `:49` 验证两路 503 但超过截止时间也抛错；`:62` 验证预算传入实际子进程调用且 TimeoutExpired 向上传播；`:42` 验证预算为零拒绝调用。操作系统调度/进程清理开销不属于硬实时保证，但超预算结果不会获得切换授权。 |
| 超时/异常不停止尚未排空的执行器 | 完整实现。deploy `:171` 在任何 stop 前检查；`:209` 异常路径写关闭配置并抛出；worker stop 仍在两次排空后。既有排空失败测试 `scripts/release/test_overseas_codex_deploy.py:122` 本次复跑通过。 |
| 双端 CLI 0.162.1、国内模型保持原样 | `Product-Spec.md:1102` 沿用已审基线；完整增量只修改入口等待与测试，版本安装及模型设置未变。deploy `:164` 仍仅生成版本与 binary 环境，`:186` 起保留实际 CLI 验证。 |
| 海外新建/续接 Astra high、图片工具及会话隔离不变 | `Product-Spec.md:1103` 沿用已审基线；增量没有产品 execution 或图片/会话代码变更，deploy `:190` 仍验证两种模式的模型与 high 参数。 |
| 验证、关闭接纳并排空、切换及恢复；不修改数据库、前端、身份服务 | `Product-Spec.md:1104` 的流程顺序未变，deploy `:171` 仅加固既有接纳检查；`:173` 至 `:205` 保留排空、切换、运行检查、schema/topology 和入口恢复验证。 |
| UI、引导真实性、设计稿一致性 | 不适用。完整 diff 无 UI、用户引导或静态资产变更；发布范围见 `docs/OVERSEAS-CODEX-ASTRA-20261014.md:3`。 |

部分实现 / 未实现：无。Spec 漂移：无；新增探测函数仅服务于关闭入口的截止预算。

## Stage 2：Code Quality — PASS

- 结构与错误处理：deploy 221 行、测试 154 行，均小于 300 行。探测与轮询分离（deploy `:44`、`:49`）；使用 monotonic 不受系统时钟校正影响。子进程异常传播至发布失败分支（`:209`），没有把探测错误当作关闭成功。
- 测试真实性：`test_overseas_codex_deploy.py:33` 的部分关闭后成功与 graceful reload 延迟一致；`:49` 虚拟时钟覆盖原先实际复现的越过 deadline 后成功缺陷；`:62` 截获 check_output 验证 curl 和 Python timeout 双重约束。原故障测试 `:122`、`:136`、`:151` 继续证明排空失败不终止执行器、启动失败保持入口关闭、禁止盲目重放。13 例独立通过。
- 测试边界：`:42` 在 timeout=0 时会直接抛错，不实际消费预设的部分关闭状态；部分关闭行为由 `:33` 覆盖。mock 测试不证明真实 Nginx reload 已生效，本报告不宣称生产部署成功。
- 安全扫描：完整增量及针对 eval、shell=True、密钥前缀和 password 赋值的扫描未发现新增危险项。deploy `:45` 使用参数数组调用 curl，无 shell 展开、无新增凭据或用户 SQL。URL 来自既有固定 ORIGIN 与固定探测路径（`:53`、`:57`）。
- 视觉对比：不适用，无页面或组件变更，依据本轮完整 git diff；未伪称打开页面完成视觉验收。

## 原始验证输出

```text
hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_overseas_codex_deploy.py -q
.............                                                            [100%]
13 passed in 0.11s
```

编译器成功时无文本；退出码原始回显：

```text
hengxin-smart-image/backend/.venv/Scripts/python.exe -m py_compile scripts/release/overseas-codex-deploy.py scripts/release/test_overseas_codex_deploy.py
py_compile exit=0
```

`git diff --check`：退出码 0，无输出。

初始候选独立只读复现：导入 deploy 模块，以虚拟时钟模拟每路 15 秒返回 503，调用 `closed(timeout=20)`，无网络或生产动作：

```text
closed(timeout=20) returned success at simulated elapsed=30.0s
```

该问题已由最终候选的请求预算与成功前截止检查修复，最终 `test_late_success_cannot_pass_deadline` 验证通过。

由主 Agent 以最终 candidateId 与本报告登记两阶段 PASS；后续代码变化需重新固定快照复核，不向 .needs-review 写 clean。
