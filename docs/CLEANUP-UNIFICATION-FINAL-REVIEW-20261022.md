# 自动清理统一修复 · 第二候选独立审查

- candidateId：`a85a4734917133a5d5292e62dca4b9476e80c9281acd8fce26f29a7a57ef50f1`。
- **Stage 1：FAIL，2 项 HIGH。Stage 2：未执行。禁止为本候选登记两阶段 PASS。**
- 审查范围：相对已批准候选 `e40dcd0f8dd9823e4cbb5752a2a4ed376c19f61c6a2365f7ec39b7e42537be5d` 的 14 个 cleanup 增量代码/测试文件。下文 `backend/` 相对 `hengxin-smart-image/`；其余路径相对仓库根。
- 已读取 AGENTS、code-review skill、快照协议、Product-Spec/DEV-PLAN 顶部、本轮修复合同全文和首轮失败报告。从 Stage 1 重新核对，没有沿用旧候选通过结论。
- 开始及中途两次 `review-status` 均匹配本候选，changedFiles 恰好为上述 14 文件；旧 records/UI/发布脚本没有漂移。旧工作依据 `docs/RECORDS-SCOPE-REVIEW-20261022.md:1` 继承，不扩大本次 UI 验收。
- 报告收尾时主Agent已开始修复，currentId变为 `4c8b1b274cee53d55e603ae6411ec8da82b61f739ee77908811fa8a82cf60665`。本文行号、两项失败证据和结论均针对送审a85候选；不能覆盖或批准后续修改。后续修复须重新固定快照、fresh审查。
- reviewer 只写审查报告和忽略目录的合成验证日志，未修业务代码、未提交、未部署、未访问生产、未写 clean。

## Stage 1 · HIGH-1：真实 worker 入口初始化仍泄漏数据库异常

合同第 5 条要求扫描异常日志不得写凭据、私有路径、原始异常消息（`docs/CLEANUP-UNIFICATION-20261022.md:15`），追加验收要求一次性 worker 入口非零退出且脱敏（`:29`）。

`backend/app/retention/worker.py:132` 的新安全 report 和 `:134` 的 `SystemExit(1) from None` 修复了 **execute_loop 内** 的旧问题，但真实 `main()` 在 `:116` 先进入 `beating(session_factory())`。`backend/app/retention/service.py:38` 的首次 heartbeat 在 yield 前写数据库，异常发生时还没有进入 execute_loop 的 try。因此首次心跳数据库异常仍直接从模块入口冒出，终端输出 SQL、参数、DSN 和完整 traceback；`--loop` 启动同样经过该路径。

reviewer 在本地运行真实 `worker.main()`，设置 `argv=['retention.worker','--once']`、自动清理开启，替换 session_factory 为不联网的空工厂，替换 heartbeat 为抛出纯合成 SQLAlchemy OperationalError。未连接数据库、未删除任何目录。结果 exit 1；`output/cleanup-unification-20261022/reviewer-heartbeat-red.log:1` 原始输出：

```text
Traceback (most recent call last):
  File "<stdin>", line 11, in <module>
  File "D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\app\retention\worker.py", line 116, in main
    with beating(session_factory()):
         ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\82358\AppData\Local\Programs\Python\Python312\Lib\contextlib.py", line 137, in __enter__
    return next(self.gen)
           ^^^^^^^^^^^^^^
  File "D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\app\retention\service.py", line 38, in beating
    heartbeat(factory)
  File "<stdin>", line 8, in fail
sqlalchemy.exc.OperationalError: (builtins.RuntimeError) synthetic_private_DSN
[SQL: synthetic_private_SQL]
[parameters: {'token': 'synthetic_secret_token'}]
(Background on this error at: https://sqlalche.me/e/20/e3q8)
```

新增 `backend/tests/test_cleanup_diagnostics.py:66` 两个子进程测试都只调用 `execute_loop`（`:80`），绕过了上述真实入口初始化，故 15 项 diagnostics 测试通过不能证明 main 全链路脱敏。

修复验收：将 worker 启动/心跳上下文的异常纳入安全入口边界，保持失败非零退出；通过 main 的真实子进程断言 SQL、token、DSN、异常链及 Traceback 均不输出，并保留自动清理和显式删除 execute_loop 两条既有测试。不能只给已有函数再加同样的局部测试。此项属于本轮新增日志合同未完整实现，不因异常路径为既有代码而豁免。

## Stage 1 · HIGH-2：预检后子目录新增挂载仍删除外部文件

合同第2、3条（`docs/CLEANUP-UNIFICATION-20261022.md:12`、`:13`）要求挂载跳转失败关闭、外部资料不得改动。新mnt_id检查能够拒绝预检时已存在的bind mount，但 `backend/app/execution/cleanup_paths.py:107` 递归检查后在 `:109` 关闭了子目录FD；`:174` 复核的chain只包含根祖先/UUID/home/.codex，`:178/:180` 复核的candidate仅是UUID或cache/plugins顶层。`shutil.rmtree` 在 `:181` 重新遍历时不会调用本模块的逐层mnt_id检查。

因此预检后将外部目录bind到target/nested（历史）或cache/nested（缓存），顶层inode和mnt_id都保持不变，所有顶层复核通过，rmtree进入新挂载，先删除外部sentinel、后在删除挂载点时抛EBUSY。最终状态失败不能挽回误删。

reviewer提出场景后，Linux验证agent在独立mount/network namespace、临时树运行真实bind复现。reviewer已读取 `output/cleanup-unification-20261022/linux-nested-race-red.py:20` 的注入逻辑、对应 `.sh:7` 的隔离启动及 `.log:1` 原始结果；没有使用模拟stat/设备号，也没有生产访问：

```json
[
  {
    "scope": "history",
    "exception": "OSError",
    "code": null,
    "errno": 16,
    "bind_injected_after_inspection": true,
    "sentinel_intact": false
  },
  {
    "scope": "cache",
    "exception": "OSError",
    "code": null,
    "errno": 16,
    "bind_injected_after_inspection": true,
    "sentinel_intact": false
  }
]
```

新增 `backend/tests/test_cleanup_mounts.py:93` 只在顶层UUID/cache自bind，恰好落在新的复核范围，未覆盖nested预检后的挂载变化。静态八类bind和顶层两类替换都通过，不能推导整个递归删除安全。

修复验收：实际删除遍历的每层都应沿不跟随链接的FD打开并校验挂载身份，再通过已校验FD处理子节点；不能仅重复一次全树预检后仍交给无挂载限制的递归函数。历史/缓存两例必须在删除外部sentinel前拒绝，并保持既有links、IPC、硬链接、静态mount和幂等回归；若调整实现约束需同步合同，再固定新候选。

## Stage 1 · 合同逐项对照

| 合同及检查项 | 结论、代码证据及验证 |
| --- | --- |
| 1. 自动缓存/历史与显式删除共用底层；参数保持 | 完整实现。`backend/app/retention/paths.py:5` 透传 cache_only；`backend/app/modules/api_image_edits/deletion_paths.py:8` 保持 api-edits 前缀，均调用 `execution/cleanup_paths.py:260`。`test_retention_paths.py:9` 和 `test_api_task_deletion_paths.py:66` 为真实入口测试。 |
| 1. 数据库/对象回收职责独立；海外不变 | 完整实现。`retention/api.py:120` 清目录后才在 `:123` 处理历史；`retention/objects.py:85` 独立回收；`modules/api_image_edits/deletion.py:127`、`:129`、`:130` 保持显式删除三个阶段。增量清单无海外文件、API/表或迁移新增。 |
| 2. UUID及根/祖先/目标、no-follow、身份 | 已实现。`cleanup_paths.py:264` UUID规范化、`:267` 拒绝父路径，`:62` no-follow stat、`:66` no-follow目录打开、`:68` inode/device/type比对，`:174` 重验祖先。`test_retention_paths.py:42/:53`、`test_cleanup_paths.py:53/:126` 验证非法标识、链接及目标替换。 |
| 2. 工具白名单与未知链接、类型、硬链接 | 已实现。`cleanup_paths.py:26` 精确6段路径/4名称/目标白名单，`:97` 仅readlink；`:110` 单硬链接及普通文件/IPC约束，`:79` O_PATH不读IPC内容。`test_cleanup_paths.py:30/:102`、`test_api_task_deletion_paths.py:38/:66/:77` 验证拒绝和真实IPC/工具链接。`linux-mount-final.log:1` 两入口真实可读 `/opt/codex` sentinel 哈希保持。 |
| 2. 挂载边界 | **部分实现，FAIL。** 静态挂载和顶层预检后替换已修复：`cleanup_paths.py:48` 从内核FD证据取mnt_id，`:70/:83` 对比父子挂载，缺失/非法证据失败关闭；`:129/:178` 重开验证顶层挂载身份。`test_cleanup_mounts.py:16/:85/:93` 12例真实Linux通过；`linux-bind-green.log:1` target/cache/nested均CROSS_DEVICE且外部sentinel完好。但HIGH-2历史/缓存的nested竞态实证仍误删外部sentinel。 |
| 2. Windows保守路径 | 已实现。`cleanup_paths.py:189/:207` 拒绝links/junction，`:247` 身份复核。`test_cleanup_paths.py:189` 三个真实junction用例在Windows实跑通过，未放宽Linux白名单。 |
| 3. 24h只cache/plugins，72h整UUID | 完整实现。`retention/state.py:7/:8/:63/:65` 阈值保持；`cleanup_paths.py:165` 只取cache/plugins，`:171` 历史才取整会话，`:172` 两个缓存均预检后才删。`test_cleanup_paths.py:42`、`test_retention_paths.py:80`、`test_cleanup_retention_safety.py:49/:53` 验证边界。 |
| 3. 原图/素材/成品/采用版本/归档/用量 | **业务保留实现，外部资料安全FAIL。** `retention/api.py:64` preserve汇总、`:77/:80` 只清历史；`retention/objects.py:27/:29/:35/:57` 引用与共享key保护。`test_cleanup_retention_safety.py:31/:47/:52/:55` 比较全部对象原始字节和业务元数据；`test_api_retention.py:64/:188` 与 `test_api_usage_facts.py:87` 覆盖采用、共享引用与用量。上述业务保留通过不能覆盖HIGH-2外部资料误删。 |
| 4. running/uncertain、父锁、pending屏障 | 完整实现。`retention/api.py:20/:39/:104/:106` 保留锁及持久pending，`retention/state.py:21/:41` 拦提交；`modules/api_image_edits/deletion.py:114` 保留持久删除fence。`test_retention_concurrency.py:87/:103/:122/:188/:222/:241` 真实PG专项通过。 |
| 4. 每小时重试、25条、两阶段、幂等 | 完整实现。`retention/api.py:136` 一小时、`retention/worker.py:80/:83` 25条和到期扫描；`retention/objects.py:85/:109` 独立对象回收重试。`test_cleanup_retry_pg.py:35/:42/:44/:47/:50` 经真实run_once复现旧pending→59分钟不动→1小时恢复→重复不重计、不刷新last_activity；`test_cleanup_retention_safety.py:98` DB修改后故障回滚、目录已删仍能重试。 |
| 5. 结构化分类、脱敏位置、无原始消息 | **部分实现，FAIL。** `cleanup_diagnostics.py:26/:45/:57/:69` 限定错误码、应用内位置、UUID及阶段；`retention/api.py:131`、`objects.py:107`、`worker.py:71/:95/:132`、`deletion.py:135` 接线。局部日志测试通过，但真实main初始化出现上述HIGH。 |
| 5. API原通用文案、无迁移 | 完整保持。`retention/api.py:135` 和 `modules/api_image_edits/deletion.py:139` 原安全文案保持，无响应合同/迁移/前端改动。 |
| 授权边界及发布依赖 | 匹配审查操作。`Product-Spec.md:1`、`DEV-PLAN.md:1`、合同`:3/:31` 要求测试审查后停，未来原生消费者另适配。未执行旧records发布脚本，未声称线上两条retry已恢复。 |
| UI/引导真实性/Spec漂移 | 本次14文件均为后台清理及测试，无新增UI、文案指引或未授权API/表。旧UI与已审快照无差异，无本轮新页面需比对。不会将本项“不适用”写成完成了新的视觉验证。 |

## 验证原始证据及限制

reviewer 已读取以下原始输出，而非只引用主Agent汇总：

```text
# output/cleanup-unification-20261022/linux-target.log
165 passed, 3 skipped, 2 warnings in 33.02s
# output/cleanup-unification-20261022/windows-target.log
59 passed, 38 skipped, 2 warnings in 11.55s
```

Linux专项3 skip均为本轮Windows junction，Windows已实跑。Windows38 skip为POSIX工具链接/FD/UID/内核挂载等条件，Linux专项包含其相应运行场景。真实Linux环境日志为Python3.12.13、PostgreSQL18.6 UTC、独立临时数据目录和网络namespace；不能等同于生产PG16.15安装验证。

独立编译命令及原始结果：

```text
cwd: D:/Work_Project/hengxin-smart-image/hengxin-smart-image/backend
.venv/Scripts/python.exe -m compileall -q app
exit_code: 0
output: （空）
```

旧 `linux-full-pre-bind-fix.log` 的2436通过/27跳过属于上一候选，不是本候选全量结果。本报告初稿时新的linux-full.log仍运行；收尾日志已出现pytest teardown的StashKey/KeyError，未获得本候选完整成功结论，不能读取尚未更新的旧linux-full.xml冒充新结果。旧前端355项及typecheck/build结果仅用于说明继承工作，未覆盖新后端缺口。已知范围外Asia/Shanghai极端Retry-After溢出没有被本次修复；本轮不是全产品无缺陷声明。

官方资料已独立打开核查：[Linux proc fdinfo](https://www.kernel.org/doc/html/v6.8/filesystems/proc.html) 将mnt_id定义为已打开文件所属挂载的身份；[Python 3.12 shutil.rmtree](https://docs.python.org/3.12/library/shutil.html#shutil.rmtree) 的avoids_symlink_attacks只说明符号链接攻击防护，不提供挂载变化隔离保证。

## Stage 2

**未执行**。Stage 1已出现两项可复现HIGH，依skill停止，不将代码行数、编译或现有测试通过写成质量审查PASS。主Agent应先补齐入口异常边界和递归删除的挂载边界，再固定新candidate，从Stage 1重新派发。
