# 国内清理发布 Schema 修复增量审查

- 审查日期：2026-10-21。
- candidateId：`62ef978c63ddedf91a24d5da0e0c5cb9d62bc320463d3c48ae79543c43d953bb`。
- 基线：主 Agent 提供的 `745b608`；本轮仅审查其后 4 文件、68 增行/2 删行，以及发布所调用旧助手的兼容性。
- 文件：`scripts/release/retention-management-drain.py`、`retention-management-deploy.py`、`test_retention_management_drain.py`、`test_retention_management_deploy.py`。
- 需求依据：`Product-Spec.md:1` 与 `docs/CLI-RETENTION-MANAGEMENT-20261021.md:21` 的排空、备份、迁移、安装全部规则消费者、生产验证要求。其余完整产品功能沿用上一轮独立报告，本报告不重复声明生产已完成。
- **Stage 1：FAIL（1 个 HIGH）。Stage 2：未执行。不得登记两阶段 PASS。**

## Stage 1 — 功能对照

| 条目 | 结论 | 证据 |
| --- | --- | --- |
| 当前 Schema 排空 SQL 不再访问退役 files 表 | 完整实现 | `scripts/release/retention-management-drain.py:18` 使用 api_image_files 和 api-image-edits 域；`:51`、`:79` 均使用新常量。`backend/migrations/versions/0030_retire_legacy.py:17` 删除 files，`:77` 删除 originals 派生登记；新条件与现行 `backend/app/modules/files/variant_worker.py:52`、`variants.py:67` 的消费/补登记域一致。后端路径均相对 hengxin-smart-image。 |
| 未完成派生图、token、lease、漏登记原图以及活动/未知 CLI 工作阻止排空 | 完整实现 | `scripts/release/test_retention_management_drain.py:74` 在独立 PostgreSQL 事务 schema 中建立四张相关表，并证明 files 不存在；计数依次 0、1、0、1、1、1、3。本次独立执行通过，未跳过 PG 测试。 |
| 关闭入口及停止服务之前验证 SQL 可执行 | 完整实现 | `scripts/release/retention-management-deploy.py:34` 在 DEPLOY_STARTED、gate.close、graceful_stop 之前执行 CLI/VARIANTS；`test_retention_management_deploy.py:109` 注入 schema mismatch，断言未写启动标记且无关闭/停止/备份行为。本次执行通过。 |
| 备份复用助手是否仍必需退役表 | 检查范围内未发现阻断 | `scripts/release/retention-management-backup.py:19` 动态枚举现有 public 表；`:54` 将 restore_check 使用的 fingerprint 替换为本发布函数。旧 `member-release-backup.py:114` 的恢复流程执行 dump/restore 和该替换函数，无硬编码 files。此项为调用链静态核对，未冒充本次实测生产恢复。 |
| 迁移后原生 worker 验证能执行 | **未实现，HIGH H1** | `scripts/release/retention-management-deploy.py:58` 仍调用旧 native-verify；见下述确定性复现。 |
| API worker 验证兼容性 | 检查范围内未发现退役表依赖 | `scripts/release/image-inputs-worker.py:40` 的 api-verify 分支仅检查队列及并发池并返回，不进入旧 native-verify 导入。 |
| UI 一致性/引导真实性 | 本增量不适用 | 4 个变更文件均为发布脚本/测试，无页面或引导文案改动。 |
| Spec 漂移 | 未发现新增产品范围 | 差异只改变发布 SQL 与前置校验及对应回归；未增加页面、业务 API、数据库表或产品行为。 |

### HIGH H1 — 迁移后的 native-verify 必然导入已删除模块

需求要求安装并验证全部规则消费者后继续发布。实际调用链：

1. `scripts/release/retention-management-deploy.py:49` 已执行 0032 迁移，`:54` 已切换原生路径，`:57` 已启动新 worker。
2. `scripts/release/retention-management-deploy.py:58` 调用旧 `image-inputs-worker.py` 的 native-verify。
3. `scripts/release/overseas-runtime.py:45` 将其转成 run-native-verify；`image-inputs-worker.py:12` 从实际 worker cwd/env 启动该解释器。
4. `scripts/release/image-inputs-worker.py:90` 无条件执行 `from app.execution import prompts`。当前后端已无该模块，独立复现得到 ImportError。因此会停在 switch，入口保持关闭，且此时数据库已迁移。旧助手并未因为只用“verify”就免除退役依赖。

独立复现，工作目录 `hengxin-smart-image/backend`，命令 `.venv/Scripts/python.exe -c "from app.execution import prompts"`，退出码 1，原始输出：

```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
ImportError: cannot import name 'prompts' from 'app.execution' (D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\app\execution\__init__.py)
```

修复方向：本发布专属原生验证只依赖现行 worker/队列及业务模块；不要修改历史共享助手。增加实际执行新验证分支的回归，避免 `test_retention_management_deploy.py:46` 对 r.worker 的 mock 掩盖导入错误。修改后重新固定 candidateId，并从 Stage 1 重新审查。

## 本次验证记录

独立运行 4 份存在的 retention 工具测试（drain/deploy/native/verify），通过独立本地 PostgreSQL 端口 65435、数据库 retention_test；没有连接生产。原始输出：

```text
....................................................                     [100%]
52 passed in 1.38s
```

首次测试命令曾误列不存在的 runtime/backup 测试文件，返回 `ERROR: file or directory not found: scripts/release/test_retention_management_runtime.py`、`no tests ran in 0.00s`；修正为实际四文件后得到上述 52 pass，不把失败命令记成通过。

使用 Python compile 对 4 个增量文件做语法编译，退出码 0，原始输出：

```text
COMPILE_OK 4 files
```

主 Agent 提供的 `output/retention-management-20261021/release-schema-fix-tests.log` 记录 180 passed in 1.54s；该记录不能覆盖 H1，因为编排测试 mock 了真实 worker 调用。本报告仅将独立执行的 52 项计为本轮亲自复核。

审查起始 `review-status` 的 currentId 与提供候选一致，changedFiles 为上述 4 文件。报告结束复查时，主 Agent 已开始修复，currentId 变为 `8b9453e77530c0d8f78aa3f57ad2ed97fc831899e5438d51049b14c17acc5556`，新增变更 `scripts/release/retention-management-native.py`。本报告所有结论仅对应原候选 62ef978c…，不覆盖该新版本。reviewer 未修改生产、实现或共享旧助手；报告写入本身不参与代码快照。修复完成须新候选复审。

## Stage 2

未执行：Stage 1 存在 HIGH 阻断，按 code-review skill 停止，不给出代码质量/安全/视觉综合 PASS。

