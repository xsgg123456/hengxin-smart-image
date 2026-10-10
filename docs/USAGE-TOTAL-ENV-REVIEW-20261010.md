# Env 顺序误报修正独立审查

- 日期：2026-10-10；执行者：独立 code-reviewer；技能：`.agents/skills/code-review/SKILL.md`。
- candidateId：`e52f51083556f5bac585cac726e9ce75e69934645192ec8b8867a73893df0ed7`。
- 范围：相对 HEAD `9b8985a` 的 `scripts/release/usage-total-runtime.py`、`scripts/release/test_usage_total_deploy.py` 及发布说明 `docs/USAGE-TOTAL-RELEASE-20261010.md`。预存 `.agents/skills/dev-builder/SKILL.md` 不属于本次审查、未修改；不重新批准其内容。
- 功能基线为 `16a79f6`，发布工具基线为 `9b8985a`，此前报告 `docs/USAGE-TOTAL-RELEASE-REVIEW-20261010.md:1`。本报告仅批准 Env 比较修正增量，不将以前报告冒充本次全产品重新验收。
- 独立执行 `review-status`，currentId 与提供候选一致；changedFiles 恰为上述两个 Python 文件。未执行生产操作、Git 提交、review-approve 或写 clean。

## Stage 1 · Spec Compliance：PASS

逐项核对 `Product-Spec.md:938`、`:940`、`:942` 及 `docs/USAGE-TOTAL-RELEASE-20261010.md:7` 的发布步骤和 `:19` 的修正边界。

| 条目 | 结论与证据 |
| --- | --- |
| Env 仅排列变化不得阻断 | 完整实现。`scripts/release/usage-total-runtime.py:47` 对完整条目排序；`scripts/release/test_usage_total_deploy.py:126` 用真实 api_settings 对反转数组断言相等，独立测试通过。 |
| 增加、删除、值变化必须阻断 | 完整实现。排序不丢弃条目、不拆分或重写值；`scripts/release/test_usage_total_deploy.py:133` 三种真实变更均断言不等；`scripts/release/usage-total-deploy.py:71` 继续据比较结果阻断，`:84` 进入回退。 |
| 其余 API 运行配置保留 | 完整实现。`scripts/release/usage-total-runtime.py:46` 保留 Cmd、Entrypoint、User、WorkingDir，`:48` 保留挂载与端口比较，diff 仅改变 Env 比较方法。 |
| 仅更新 Web API 与前端，执行器/队列不重启 | 完整实现。`scripts/release/usage-total-deploy.py:68` 仍只 up api 且 --no-deps；`:64`、`:73`、`:82`、`:102` 的身份检查未变；`scripts/release/usage-total-runtime.py:14`、`:25` 保留后台容器及原生 PID/启动时间检查。回归测试覆盖只切 API、执行器漂移阻断。 |
| 不迁移、不改清理开关；累计统计/默认全量/20、50、100 分页业务契约保持 | 无实现漂移。相对 `9b8985a` 的业务目录 diff 为空；本次没有数据库或前后端业务代码变化。当前作用为解除发布工具误报，统计与分页仍以既有功能报告及后续生产只读校验为验收证据。`scripts/release/usage-total-runtime.py:60` 仍只读 schema；`usage-total-deploy.py:76`、`:79` 仍执行发布校验。 |
| 已提交白名单打包、安装凭据、备份、原子切前端及失败回退 | 无实现漂移。`scripts/release/usage-total-deploy.py:58` 安装凭据、`:63` 备份、`:78` 发布、`:84` 回退链路不变；专项测试通过。`scripts/release/usage-total-runtime.py:89` 拒绝复用备份目录，符合保留失败证据要求。新的发布目录与提交属于主 Agent 后续执行步骤。 |
| 不付费生图、不删除业务数据、不部署原生代码、不推远端、不虚报登录 UI | 无新增行为。两个 Python 文件的完整 diff 只含 Env 排序和隔离回归测试；没有新增命令、网络调用或业务写入。边界见 `docs/USAGE-TOTAL-RELEASE-20261010.md:21`。 |

部分实现：无。未实现：无。Spec 漂移：无。本次无 UI/文案变化，设计、引导和视觉一致性不适用；没有把未打开的页面标为已验证。

## Stage 2 · Code Quality：PASS

- 质量：`scripts/release/usage-total-runtime.py:45` 保持单一配置投影职责；排序返回新列表，不修改 inspect 原对象；运行文件147行、测试197行，均低于300行。
- 安全：`:47` 未引入命令执行、日志输出或凭据落盘，不泄漏 Env 值；对变更两文件扫描 eval、shell=True、innerHTML、前端 KEY/SECRET/TOKEN 和密钥前缀无命中。完整 diff 无新增依赖、SQL、远端命令或权限变更。
- 测试真实性：`scripts/release/test_usage_total_deploy.py:126` 直接调用真实 api_settings，输入结构对应 Docker inspect 的 Config.Env；反转、值变化、增加、删除分别证明契约。`:88` 既有编排测试验证运行配置漂移会回退，`:94` 验证执行器漂移禁止切换。编排采用 mock，不冒充生产实测。
- 视觉：相对 `9b8985a` 业务目录 diff 为空，本次没有新页面或邻居页面渲染差异需要比较；未重跑浏览器。
- 本增量没有 HIGH/MEDIUM 缺陷。扩大测试发现一项已提交基线的无关失败，详见下节；两阶段 PASS 仅适用于本次范围，不能写成全部发布历史测试通过。

## 独立验证原始输出

语法解析（ast.parse，两文件完整读取）：

```text
COMPILE PASS scripts/release/usage-total-runtime.py: 147 lines
COMPILE PASS scripts/release/test_usage_total_deploy.py: 197 lines
```

命令：`hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_package_usage_total.py scripts/release/test_usage_total_deploy.py scripts/release/test_package_management.py scripts/release/test_package_delivery.py -q`

```text
..................................                             [100%]
34 passed, 10 subtests passed in 1.60s
```

追加管理工具回归（同一命令增加 `test_management_deploy.py`、`test_management_runtime.py`、`test_management_verify.py`）：

```text
.................................................................                       [100%]
65 passed, 57 subtests passed in 2.50s
```

扩大检查命令：`hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release -q`

```text
>       self.assertTrue(manifest['composeBaseOverlays'][-1].endswith('annotation-20260924-6b43b3c/api-override.yaml'))
E       AssertionError: False is not true

scripts\release\test_release_native.py:100: AssertionError
=========================== short test summary info ===========================
FAILED scripts/release/test_release_native.py::NativeReleaseTests::test_frontend_manifest_matches_seven_native_files
1 failed, 167 passed, 1 skipped, 117 subtests passed in 6.18s
```

该失败为既有测试过期：`scripts/release/image-inputs-frontend.py:39` 的最后一个 overlay 是 materials，而 `scripts/release/test_release_native.py:100` 仍断言 annotation。两者及 image-inputs-native.py 相对 `9b8985a` 无差异。为排除当前工作区影响，独立将这三个文件用 `git show 9b8985a:scripts/release/<文件>` 提取到系统临时目录，以项目虚拟环境 pytest 仅运行上述用例（禁用缓存），未访问生产；输出：

```text
>       self.assertTrue(manifest['composeBaseOverlays'][-1].endswith('annotation-20260924-6b43b3c/api-override.yaml'))
E       AssertionError: False is not true
=========================== short test summary info ===========================
FAILED ::NativeReleaseTests::test_frontend_manifest_matches_seven_native_files
1 failed in 2.03s
HEAD_9b8985a_REPRO_EXIT=1
```

首次生产回退、健康状态及业务 fingerprint 属于主 Agent 的生产证据，本 reviewer 未独立连接生产，因此不将其计入独立测试通过数。本报告不代表重新部署已成功。
