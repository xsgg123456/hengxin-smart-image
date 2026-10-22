# 记录筛选与安全清理联合发布 · 第一候选审查

- candidateId：`2bc3d2f2025f3328735d5a5eb84f2f44548ae8be52756d278aaf48cf62ff8a0e`。
- **Stage 1：FAIL。Stage 2：未执行。** 存在 1 项 HIGH，不能登记本候选两阶段 PASS。
- 审查范围：相对已批准业务快照 `e7065e207c2177764b4a71479c8fe44d5cbac22f7d59441dc34f39390e6ddced` 的七文件增量：`scripts/release/domestic-record-filters-{runtime,deploy,verify,native}.py`、`package-record-filters.py`、`test_record_filters_{release,native}.py`，并读取复用的原生、排空、备份恢复、镜像及打包接线。
- 源合同：`docs/RECORDS-CLEANUP-RELEASE-20261022.md:5`，以及 `Product-Spec.md:1`、`DEV-PLAN.md:1`。已读取 code-review skill 和 `docs/HARNESS-REVIEW.md`。业务和 UI 继承 `docs/CLEANUP-UNIFICATION-APPROVAL-20261022.md:1`、`docs/RECORDS-SCOPE-REVIEW-20261022.md:1`，不重新声称已完成本轮线上验收。
- reviewer 未改实现、未提交、未部署、未访问生产。主 Agent 收到 HIGH 后已确认将修复并重新固定快照；本报告不覆盖后续修订。

## Stage 1 · HIGH

### H1：早期失败不停止仍运行的清理器

合同要求切换失败后保持入口关闭、通道暂停及清理停止，禁止回滚已清理后的数据库（`docs/RECORDS-CLEANUP-RELEASE-20261022.md:10` 的失败关闭要求及本轮派发的明确恢复边界）。

实际：`scripts/release/domestic-record-filters-deploy.py:90` 只有 `CLEANUP_MAY_HAVE_DELETED` 存在才进入两清理器停止循环；该标记在 `:63`、即原生/API/前端切换与消费者恢复之后才创建。因此 `:35` 关闭入口、`:36` 停 API、`:37` 暂停或 `:39` 排空失败时，异常处理只尝试关入口/暂停，不停止清理器。

可达场景：`scripts/release/retention-management-drain.py:65` 顺序停止 retention、deletions；`:66` 对第二个服务的快照漂移检查失败，会在该服务的 `:67` 停止调用之前退出。其余恢复路径没有补停该服务，仍可修改文件/回执，恢复现场不满足清理停止边界。

独立复现使用已有 cutover fixture，恢复真实 `drain.stop`，仅模拟第二服务 PID 从准备快照 20 漂移至 21；真实排空控制流在快照断言处失败。结果如下，未操作任何生产进程：

```text
error=Cleanup process drift
drain_stop_attempts=["hengxin-retention"]
handler_stop_attempts=[]
cleanup_restart_marker=False
recovery={"phase": "drain", "error": "AssertionError", ...}
exit_code: 0
```

修复验收要求：对进入切换 try 后的失败均逐个尝试正常停止两个清理器，不依赖重启标记；一个停止失败仍尝试另一个并记录 `STOP_REQUIRED`，保持禁止强杀和禁止数据库自动回滚。补充早期失败及部分排空失败的断言，再重新固定候选独立审查。

## Stage 1 · 合同逐项核对

| 条目 | 结论与证据 |
| --- | --- |
| 1. 生产版本、数据库、在途和保护对象实查 | 属于主 Agent 已执行现场工作，原始材料位于忽略证据目录；reviewer 未重新连接生产，不能独立确认 22 对象/45 facts。运行时会重新要求生产0.2.48、国内0032、海外0020（`domestic-record-filters-runtime.py:28`、`:33`），准备与切换前比较拓扑（`:57`、`:68`；`domestic-record-filters-deploy.py:21`）。 |
| 2. API/前端及三个国内原生均使用新代码 | 实现匹配。`domestic-record-filters-deploy.py:46`、`:48`、`:54` 分别切原生/API/前端；`domestic-record-filters-native.py:17`、`:72` 验证共享 cleanup 必需文件及所有 manifest 后端哈希；`:66` 专用路径正则，`:123` 仅写三服务受控 drop-in。 |
| 2. 保留执行环境、凭据、资源、argv，海外及其他容器保持 | 实现匹配。`member-release-runtime.py:152` 比较依赖锁并复用旧 venv；`domestic-record-filters-native.py:133` 调旧 verify，后者 `retention-management-native.py:125` 逐项核对 cwd/PID/policy/env/argv；新增 `:138` 仅允许受控配置文件变化。`domestic-record-filters-runtime.py:72`、`:95` 检查容器身份、镜像、挂载、配置、原生非目标进程及资源限制。 |
| 2. controlled drop-in 备份、白名单及漂移阻断 | 实现匹配。`domestic-record-filters-native.py:51` 定义精确三路径白名单，`:100` 备份原始字节与 SHA256；`:113`、`:120`、`:121` 切换前验证备份路径集合、策略文件和预生成配置。专项覆盖缺标记、活动PID、配置漂移、环境/策略/argv漂移（`test_record_filters_native.py:86`、`:104`、`:115`、`:140`）。 |
| 2. uid1001 正向工具链接与负向未知链接 smoke | 代码实现匹配，真实生产执行尚待 prepare。`domestic-record-filters-native.py:19` smoke 限制 UID、导入路径，临时目录中清合法四工具链接，并拒未知链接、验证 sentinel；`:94` 使用 runuser codex，成功才写 `NATIVE_PREPARED`。本地 `test_record_filters_native.py:185` 验证接线，未冒充已实际运行 Linux uid1001 smoke。 |
| 3. 中文提交、不可变0.2.49包、隐私/哈希/隔离安装 | 接线匹配，真正提交/包/镜像属后续执行。`package-record-filters.py:11` 强制共享 cleanup 和专项测试；`:34` 固定版本及0032/0020；`package-overseas.py:180` 从已审干净提交取文件、隐私扫描、逐文件哈希及复验归档。`overseas-deploy.py:29` 校验实际镜像源码哈希，隔离网络运行安装测试，成功才写镜像凭据。 |
| 4. gate关闭、暂停、无强杀排空、cleanup先停 | 正常路径匹配。`domestic-record-filters-deploy.py:35` 先关入口/停API/暂停再排空；`retention-management-drain.py:65` 先停止清理扫描器，`:71`、`:74` 验证CLI/variants及API持久交接，`:80` 验证所有原生PID为0。`retention-management-native.py:90` 仅SIGTERM并等待，超时拒绝强杀。异常路径不匹配，见 H1。 |
| 4. 完整备份、隔离restore、切换前全表指纹 | 实现匹配。`domestic-record-filters-verify.py:26` 枚举所有public表的全部行列及schema；`:37` 要求排空与清理停止标记；`:54` 完整pg_dump，`:60` 隔离恢复比对，`:63` 再查源库未变；`:65` 最后才写COMPLETE。`member-release-backup.py:114` 复用生产PG镜像在network none临时容器恢复。部署 `:44`、`:52` 切换前后且恢复消费者前验证指纹；本轮无迁移命令。 |
| 4. 失败保持关闭，禁止恢复已清后DB | 部分实现。`domestic-record-filters-deploy.py:77` 记录阶段并尝试关入口、暂停，不含回滚DB路径；`:90` 清理停止被过晚标记限制，H1 阻断。 |
| 5. 首扫、两失败会话重试、保护对象、正式页及窄屏验收 | 首扫门禁已有接线：`domestic-record-filters-deploy.py:64`、`:66`，`retention-management-verify.py:40` 用DB时间、`:53` 要求持久完成回执/心跳、`:83` 保证服务未重启。`domestic-record-filters-verify.py:73` 检查记录路由与默认mine，`:88` 检查首页发布字节。两失败会话/保护文件及正式登录UI/窄屏属部署后验收，当前未完成，不以单测替代。 |
| UI、引导真实性与Spec漂移 | 七文件全部为发布脚本及测试，无页面/文案/API/表增量；继承已审UI范围。本轮不存在新的视觉比较对象；未宣称打开正式页面完成复验。 |

## 本候选独立测试原始输出

```text
命令：.\hengxin-smart-image\backend\.venv\Scripts\python.exe -m pytest -q scripts/release/test_record_filters_native.py scripts/release/test_record_filters_release.py
......................................................................   [100%]
70 passed in 1.14s
exit_code: 0
```

70项通过不能关闭 H1：`test_record_filters_release.py:182` 本身仅在同一标记存在时断言停止，因此没有约束早期失败的清理停止行为。上面的额外复现补足此盲区。

审查初始与报告前 `review-status` 均显示 currentId 为本候选、reviewedId 为 e7065e20 开头的旧业务快照，changedFiles 精确为上述七文件，approved=false。未发现审查中代码漂移。

Stage 2 按规则停止，未执行本轮质量/安全扫描、编译或视觉阶段，也不将主 Agent 先前编译声明写成 reviewer 独立结果。后续修复必须新 candidateId，从 Stage 1 重新开始；本报告不得用于 review-approve PASS。
