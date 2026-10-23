# 海外图片发布覆盖文件顺序：增量独立复审

- candidateId：`f5fc48dc07e5ad03caee0559d16ae908e6b342144996e77d6085e56036502bb1`。
- Stage 1（Spec Compliance）：**PASS**。
- Stage 2（Code Quality）：**PASS**。
- 范围：相对已批准候选 `ad0ae03ab93121c235ac5cd119b0e792a338a799ba8b6217ea0fa09b4afaab8c` 的发布覆盖文件名增量；业务实现沿用已批准报告 `docs/STUDIO-DELIVERY-FINAL-REVIEW-20261023.md:23` 的逐条审查。审查前后 currentId 均匹配本候选，未发生代码漂移。未修改业务代码、未提交、未登记批准、未写 `.needs-review`。

## 快照与差异完整性

`review-status` 独立显示只有以下三个文件变化。将两个生产脚本的 9z 文件名还原为 6z，以及从测试文件移除新增测试函数（保留原末尾单换行），所得 SHA256 分别精确匹配批准快照中对应文件的摘要。因此没有凭主 Agent 的摘要推定差异。

| 文件 | 实际增量与证据 |
| --- | --- |
| `scripts/release/studio_delivery_runtime.py:15` | DROP 从 `zzzzzz-studio-delivery-20261023.conf` 改为 `zzzzzzzzz-studio-delivery-20261023.conf`，其余字节未变。 |
| `scripts/release/studio-delivery-deploy.py:52` | 生成恢复说明中的文件名同步为 9z，其余字节未变。 |
| `scripts/release/test_studio_delivery_deploy.py:250` | 仅追加真实九个历史配置名排序测试，以及 `/run` 的 10z 更晚配置拒绝断言。 |

`AGENTS.md` 的用户预存改动与已批准快照相同，本 reviewer 未改动。初次测试文本重建因多保留一个末尾换行未匹配，纠正审查脚本的切片后精确匹配；没有编辑送审文件来取得匹配。

## Stage 1：需求对照

依据 `Product-Spec.md:1322` 至 `:1330`、`docs/STUDIO-DELIVERY-FIX-20261023.md:1` 至 `:9`、既有完整报告及 `docs/HARNESS-REVIEW.md:5`。

| 要求 | 结论与证据 |
| --- | --- |
| 原生首轮、同会话成功轮双证据、最终清单优先、排除草稿与失败 | 无代码变化；保留已批准实现。对应完整报告 `:25` 起逐条证据，相关后台文件摘要未变。 |
| 历史补交、来源与字节校验、去重、普通 work 门禁、失败提示、不扫目录猜交付 | 无代码变化；对应完整报告 `:32` 起逐条证据，相关后台文件摘要未变。 |
| 受限维护入口、原事件/原图校验、台账、事务与删除竞态、审计、保留次数时间、不重跑与不归档 | 无代码变化；对应完整报告 `:40` 起逐条证据，相关后台文件摘要未变。 |
| 从真实生产基线增量发布 | 完整实现。runtime `:15` 的 9z 文件名排在已列出的 8z 配置后；测试 `:250` 创建全部九个旧配置并经真实 `last_override` 函数验证。排序符合 [systemd 官方文档](https://www.freedesktop.org/software/systemd/man/257/systemd.unit.html)：不同名称 drop-in 按文件名词典序应用，不受所在目录影响。 |
| 保留权限、Skill、国内、模型、原配置 | 完整实现。runtime `:141` 至 `:146` 只输出 WorkingDirectory 和重置后的 ExecStart，保留实际 worker 参数；deploy `:113` 使用独占新建，不覆写已有文件；`:75`、`:156` 保留无关拓扑校验。专项 `test_dropin_preserves_all_actual_parameters_and_only_changes_paths`（测试 `:87`）通过。 |
| 更晚覆盖仍需拒绝，失败不误暂停或重启 | 完整实现。runtime `:167` 至 `:172` 仍检查 systemctl cat 和本地目录，严格要求全部旧文件名小于新文件名；测试 `:242`、`:260` 验证 `/run`、vendor 更晚配置拒绝。另经真实 switch 控制流验证，10z 拒绝时 gate 和服务调用均不可达，phase 保持 prepared、未写新配置。deploy `:87` 位于首次 gate `:88` 之前。 |
| 安装测试、备份、排空、实际切换、验收后恢复接纳 | 门禁未改。deploy `:65` 安装回执绑定、`:92` 至 `:108` 排空和备份、`:130` 至 `:145` 核验实际启动、`:165` 验收回执、`:169` 恢复原 gate。专项覆盖通过；本报告不声称生产切换已经完成。 |
| 原 PNG 补回、页面预览下载与可归档 | 业务代码未改；仍是生产操作验收项，见完整报告 `:50` 与修复计划 `:9`。本 reviewer 未操作生产页面，未将之前回放等同于实际补收入库。 |
| UI 一致性、引导真实性、Spec 漂移 | 本次仅发布路径常量、恢复说明和测试，无页面、样式、用户引导、API、数据库或模型行为变化，视觉邻居比较不适用。未发现新增范围外功能。 |

完整实现：本次发布顺序修正及原门禁保留。部分实现/未实现：本增量未发现。HIGH/MEDIUM/LOW 缺陷：无。

## Stage 2：质量与安全

- 文件分别为 211、206、262 行，均低于 skill 的 300 行标准；未增加新生产函数、动态类型或执行入口。证据：runtime `:15`、deploy `:52`、测试 `:250`。
- 安全扫描未命中 eval、HTML 注入、前端密钥前缀、OpenAI/Anthropic 密钥模式或 `shell=True`。runtime `:33` 参数数组执行、`:145` systemd 参数白名单、`:167` 后序覆盖门禁均未变；本次没有新增秘密或动态命令插值。
- 新测试使用实际 DROP 常量和现场配置名，创建真实临时文件并通过同一生产排序函数；10z 输入确实比 9z 更晚，非不可达前提。测试 `:250` 至 `:262`。Windows 用例不宣称验证了真实 Linux systemd 启动。
- 恢复说明静态文件名和 DROP 一致（deploy `:52`、runtime `:15`）。**操作交接：生产目录已 prepared，`prepare` 的防重入检查（deploy `:16`）意味着更新脚本不会自动重写已生成的 RECOVERY.md。切换前须由主 Agent 核对并同步私有恢复说明中的 9z 文件名；只删除本次文件的限制继续保持（deploy `:51` 至 `:54`）。** 已将此事项发给主 Agent，不要求重跑 prepare。

## reviewer 独立验证原始输出

```text
hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_studio_delivery_deploy.py -q
.........s...........................                                    [100%]
36 passed, 1 skipped in 0.44s
exit_code: 0
```

跳过项为 Windows 无法创建目录符号链接，测试 `:66` 至 `:73`，不计通过。

```text
临时 Python 审查脚本：调用实际 switch；gate/run 替身如被调用立即失败；注入 10z 配置。
SWITCH_LATER_OVERRIDE: rejected before gate/service; phase=prepared; no file written
scripts/release/studio_delivery_runtime.py RECONSTRUCTED_PRIOR_MATCH True current_lines 211
scripts/release/studio-delivery-deploy.py RECONSTRUCTED_PRIOR_MATCH True current_lines 206
scripts/release/test_studio_delivery_deploy.py RECONSTRUCTED_PRIOR_MATCH True current_lines 262
exit_code: 0

hengxin-smart-image/backend/.venv/Scripts/python.exe -m compileall -q scripts/release/studio-delivery-deploy.py scripts/release/studio_delivery_runtime.py scripts/release/test_studio_delivery_deploy.py
stdout: <empty>
stderr: <empty>
exit_code: 0

git diff --check
warning: in the working copy of 'AGENTS.md', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'Product-Spec-CHANGELOG.md', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'Product-Spec.md', CRLF will be replaced by LF the next time Git touches it
exit_code: 0
```

主 Agent 另提供 Linux 隔离执行实际发布脚本测试 `37 passed, 0 skipped (0.17s)`，以及原 worker PID 388215、cwd 仍为 `overseas-20261022-6897b6e/backend` 的只读证据。本 reviewer 未亲自执行这些服务器命令，故与上述独立验证分开记录。此前 1226 passed / 79 skipped 的安装业务回归和真实 PNG/rollout 回放同属主 Agent 证据，本增量没有重复全套业务回归。

批准范围为本候选的两阶段代码复审；主 Agent 需用同一 candidateId 登记 `review-approve`，并继续完成实际发布、原图补收与正式页面验收。
