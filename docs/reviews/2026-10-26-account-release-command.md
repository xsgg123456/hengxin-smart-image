# 发布预检默认命令修复：两阶段增量审查

- 日期：2026-10-26；reviewer 使用 `.agents/skills/code-review/SKILL.md`。
- candidateId：`18b88494187a7f43465ea61a670c0d8e94da23bde4333c02643fd827d21af70e`。
- 基线：`3f93b4048aab6bf8384da7c48953562c083f8531`；范围仅 `scripts/release/account-runtime.py`、`scripts/release/account-tests.py` 相对 HEAD 的差异。用户既有 AGENTS.md 修改不属于本次审查，不改动。
- 结论：Stage 1 PASS；Stage 2 PASS。没有 HIGH/MEDIUM 问题。此结论仅批准本次预检修复，不代表生产部署或生产冒烟完成。
- 原完整功能和打包审查分别见 `docs/reviews/2026-10-26-codex-account-management-fixed.md:1`、`docs/reviews/2026-10-26-codex-account-package-fix.md:1`。本次读取实施合同与调用路径，限定增量复核，不重新声明完整历史功能已测试。

## Stage 1：Spec Compliance

发布边界来自 `docs/CODEX-ACCOUNT-MANAGEMENT-20261026.md:9` 的构建部署与任务不中断要求；此次修复恢复合法 Compose 配置的预检，并继续拒绝真实命令漂移。

| 审查条目 | 结论及证据 |
| --- | --- |
| command 缺失或 null 使用镜像默认值 | 完整实现。`account-runtime.py:118` 仅在 None 时读取镜像 Config.Cmd；`:121` 使用运行容器的不可变 Image ID；`:122` 与运行 Cmd 严格比较。`account-tests.py:24` 覆盖缺失/null/显式列表，独立生产形状六参数用例也通过。 |
| 不把运行命令自身当作默认预期而漏报漂移 | 完整实现。`account-runtime.py:121` 从 image inspect 取值，`:122` 拒绝不等；`account-tests.py:33` 让镜像默认返回 other、运行命令保持 uvicorn，实际抛出 command drift。 |
| 显式空命令与显式命令不回落 | 完整实现。`account-runtime.py:119` 使用 is None；`account-tests.py:29` 覆盖 []、空字符串和不同列表均拒绝当前非空运行命令，`:27` 核对显式匹配列表只做一次镜像身份检查。 |
| 显式 entrypoint 与默认 command 不错误放行 | 完整实现。`account-runtime.py:120` 拒绝非 None entrypoint；`account-tests.py:36` 覆盖列表，独立补查空列表、空字符串、非空列表均在默认查询前拒绝。该限制保守且明确。 |
| 预检调用与已有保护保持 | 完整保持。`account-deploy.py:53` 读取真实 Compose JSON，`:54` 在准备阶段调用检查，`:204` 在切换后调用检查。`account-runtime.py:116` 环境检查、`:117` 镜像身份检查、`:123` 起挂载检查无变化；差异没有停止服务、写凭据或任务数据操作。 |
| UI、引导真实性、既有任务/账号布局 | 无 UI 或引导变更，两个脚本不包含页面组件。完整 diff 仅增加预期命令解析和对应测试；没有新增产品功能、路由、接口、表或状态，无 Spec 漂移。 |

部分实现：无。未实现：无。Stage 1 无 HIGH，进入 Stage 2。

语义核对：[Docker 官方 Compose services 文档](https://docs.docker.com/reference/compose-file/services/#command) 明确 null 继承镜像命令、空列表/空字符串覆盖为空；[entrypoint 说明](https://docs.docker.com/reference/compose-file/services/#entrypoint) 明确非 null entrypoint 不使用镜像默认 command。审查已联网读取这些条目。

## Stage 2：质量、安全和测试真实性

- 质量通过：runtime 160 行、tests 113 行，均低于 300 行；变更复用原 require/run，无重复执行框架。`account-runtime.py:118` 的 command 名称与 Compose 字段一致；`:121` JSON 解码或 inspect 失败均向上传播，不吞掉错误。
- 安全通过：`account-runtime.py:121` 使用固定 docker/image/inspect 参数及 live Image，沿用 `:29` 参数序列 subprocess，无 shell=True；不打印命令、环境、凭据。两个文件扫描 eval、innerHTML、前端秘密变量、典型密钥、shell=True 无匹配（rg exit 1 表示无匹配）。已有部署绝对路径不是此次新增，参见 `account-runtime.py:15`。
- 测试真实性通过：`account-tests.py:24` 的镜像 Cmd 与 live Cmd 独立由 mock 返回；`:33` 刻意制造二者不同并断言拒绝，避免仅测成功路径。独立额外检查断言 docker inspect 确实收到不可变 live Image 而非标签，并使用完整 uvicorn 生产形状参数。所有调用仍为本地 mock，不宣称已访问生产 Docker。
- 视觉对比不适用本次范围：无页面、样式、文案或组件差异；未打开浏览器，不将既有截图当作本次新证据。基线 UI 审查仍由原完整报告限定。
- 未发现需要修复的安全或质量问题。生产 prepare 和切换仍需主 Agent 使用新包实际执行；本地测试不代替生产结果。

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
Ran 6 tests in 0.115s

OK
```

`python -m py_compile scripts/release/account-runtime.py scripts/release/account-tests.py` 原始 stdout/stderr 为空，独立记录退出状态：

```text
PY_COMPILE_EXIT=0
```

独立临时内存验证（未改产品代码）：

```text
PASS production-shaped command uses immutable live image ID
PASS all explicit entrypoint forms fail before default lookup
```

## 快照边界

开始审查时 review-status 原始输出：

```json
{"currentId": "18b88494187a7f43465ea61a670c0d8e94da23bde4333c02643fd827d21af70e", "reviewedId": "98086c8f797d5d8a3ad55f70b4754bb830faa0c8a8022afbd45df249d01d860d", "changedFiles": ["scripts/release/account-runtime.py", "scripts/release/account-tests.py"], "approved": false}
```

审查未修改产品代码，只生成本报告。由主 Agent 在确认当前快照仍一致后对同一 candidateId 登记两阶段 PASS；本 reviewer 不写 clean、不 commit、不执行生产操作。
