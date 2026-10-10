# 管理中心 API 统计发布增量审查

日期：2026-10-10。candidateId：`e34a4307aacb6b59f7ef99acc96a6ec4fc91a97a5395fbd3b6e36d1d43e753a1`。

结论：**Stage 1 FAIL，1 项 HIGH；Stage 2 未执行。不得登记两阶段 PASS。**

范围：`docs/MANAGEMENT-API-RELEASE-20261010.md`、`scripts/release/{package-management,management-runtime,management-deploy,management-verify}.py`、对应四个测试文件及 `hengxin-smart-image/frontend/package.json`。功能基线为 bccf95e，功能审查记录为 `docs/MANAGEMENT-API-R2-REVIEW-20261010.md`；本次不重新认证基线功能。预存 `.agents/skills/dev-builder/SKILL.md` 排除。读取 Product-Spec.md:920、933 和发布文档并按主 Agent 提供的发布授权审查。

审查时 `review-status` 返回 currentId 与上述 candidateId 一致，受控差异为版本文件及八个发布 Python 文件。没有修改代码，没有生产写入，没有提交。

## Stage 1：需求符合性

### HIGH R1：完整验证没有接入发布事务，失败无法关闭接纳

要求：发布计划第 5 项要求核对安装哈希、健康、独立心跳、真实统计、图片与任务基线、公网页面及鉴权；主 Agent 交接进一步要求验证后开放、失败 fail-closed。

实际：`scripts/release/management-deploy.py:101` 仅调用 `--contracts-only`。随后发布前端、取消暂停、启动 web，至 :109 直接输出 `DEPLOY_COMPLETE`。完整安装文件与五服务镜像校验在 `scripts/release/management-verify.py:104`，原生/前端哈希在 :117，公网资源及鉴权在 :148、157；这些分支从未由 deploy 调用。完整 verify 作为后续独立进程失败时，不会触发 deploy :112 的开放后关闭接纳分支。错误镜像、错误静态资源或鉴权不符合预期时，可能已经持续接纳新业务而发布流程显示完成。

独立复现：运行现有 `RecoveryTests.exercise('success')`，收集实际执行事件，得到：

```text
BACKUP_COMPLETE
DEPLOY_COMPLETE management-20261010-abcdef0 backup=<临时测试目录>
verification_calls= [('python3', '<临时测试目录>/src/scripts/release/management-verify.py', 'management-20261010-abcdef0', '--contracts-only')]
final_state= {'schema': '0026', 'paused': False}
code= new
```

修复标准：安装哈希、五服务镜像与本地准备校验在开放前完成；公网静态资源与鉴权校验在开放后、同一个 deploy try 内完成，成功后才报告完成。公网验证失败必须触发关闭接纳、保留新执行器，不能恢复旧执行代码或覆盖业务数据库。增加安装哈希失败阻止开放，以及公网哈希/鉴权失败自动关闭接纳的故障测试。主 Agent 已确认此差距需修复。

### 逐条核对

| 条目 | 结果 | 证据及边界 |
|---|---|---|
| 已批准代码、版本 0.2.20 | 完整实现（代码机制） | package-management.py:74、81 要求提交并匹配批准快照；frontend/package.json:3 仅版本由 0.2.19 改为 0.2.20。当前发布增量尚未获批，不可先打包。 |
| 白名单及隐私打包 | 完整实现（代码机制） | package-management.py:15、26、55、97、108；限制源码/资源类型，拒绝链接，解压 gzip 后扫描，归档回读比对；6 项包测试通过。 |
| 正式构建、依赖审计 | 已有构建证据，生产包待执行 | output/release/management-prep/build.log 末行 `✓ built in 43.92s`；主 Agent 提供审计基线 critical 0/high 36/moderate 34/low 1，本审查未独立重跑审计。 |
| 最终镜像断网安装测试 | 完整实现（代码机制），实镜像证据待执行 | management-deploy.py:57–66 使用最终镜像、network none，保存并复核 image ID；:13–22 只排除六个依赖仓库 infra 的测试模块及一个 frontend 类型源测试。后端业务测试仍纳入。PG 外部数据库测试会按 fixture 跳过，例如 backend/tests/test_api_image_execution_pg.py:32，不得声称断网运行覆盖真实 PG。 |
| 排空并关闭接纳、派发 | 完整实现（控制流程） | management-deploy.py:30、67、73–83；先检查旧任务/API任务及轮次，再停 web/API/outbox、暂停通道、API drain、二次核查 pending、native stop。未知排空进入 :120 保持关闭且不重启执行器。测试覆盖 CLI busy 和未知 drain。 |
| 备份 | 完整实现（代码机制） | management-runtime.py:85–105 备份 DB 并 pg_restore --list 检验目录、原生 app、前端入口、版本/配置，成功才写 COMPLETE；deploy.py:84–86 备份先于迁移。未实际创建生产备份。 |
| 迁移、幂等回填 | 完整实现（调用链） | management-deploy.py:86–89 迁移后检查 0026，再调用 backfill；backend/app/modules/management/api_stats/backfill.py:9–22 读取既有事实并通过 put 写入；既有业务实现沿用基线审查。测试验证调用顺序及回填失败保留 schema。 |
| 五服务/native/前端更新及配置保留 | 完整实现（安装机制）；最终闭环不完整 | management-runtime.py:57–82 读取全部实际 compose 路径并仅覆盖 image/build；:108–121 拷贝 py 和三个提示词资源，保留 uid/gid，目录 0755、文件 0644；:124–144 发布前端及活动标记。最终哈希校验缺少闭环见 R1。 |
| 并发与清理关闭 | 完整实现（校验机制） | management-runtime.py:48–70 检查 native 5/7200 和清理关闭；management-verify.py:29–38 校验 API 5×10、180/60/360，CLI 5/7200 与 retention disabled；没有启动清理维护服务。 |
| 独立心跳与实际统计 | 部分实现 | management-verify.py:39–49 验证两通道实际 heartbeat，并读取 report 与 facts；deploy.py:101 已将此检查作为开放前门禁。数据基线目前只输出状态计数（verify.py:143–144），未自动对比发布前 task/item/version/file 基线，最终交付仍须另有只读前后比对证据。 |
| 安装、公网页面和鉴权验证 | 部分实现 | 校验函数存在但发布成功路径未调用，见 HIGH R1。 |
| 不发起付费生图 | 完整实现 | management-verify.py:12–51 只读事务和内部报告读取；:145–158 仅健康/静态资源/auth-me 请求，无生成调用。 |
| 回退不覆盖业务数据库 | 完整实现（代码机制） | management-deploy.py:129–177 恢复执行代码、入口、标记与旧服务，没有执行数据恢复；保留新增 schema。开放后 :112–119 保留新执行器，回退失败 :165 起关闭接纳。相关故障模拟通过。 |
| UI、引导真实性及范围漂移 | 本增量不适用 UI 视觉验收；未见新增产品功能 | git diff 中前端仅 package.json:3 版本变化，没有组件/布局/引导变更；发布工具行为均服务本次发布计划。未重新打开基线页面，不能将本报告当作基线视觉验收。 |

没有“完全未实现”的整项发布模块；R1 为核心验收/恢复链路缺失。工具实现通过不等于生产发布完成，实镜像安装、备份、迁移、基线比较与公网证据均须在后续执行取得。

## 独立测试及编译证据

执行 `python -m unittest discover -s scripts/release -p 'test_management*.py' -v`，原始汇总：

```text
Ran 25 tests in 0.637s

OK
```

执行 `python -m unittest discover -s scripts/release -p 'test_package_management.py' -v`，原始汇总：

```text
Ran 6 tests in 0.008s

OK
```

对八个送审 Python 文件使用内置 `compile` 独立语法编译，原始输出：

```text
Python syntax compilation: 8 files PASS
```

正式前端构建由主 Agent 执行，本审查读取 build.log，原始末行：

```text
✓ built in 43.92s
```

上述 31 项单元测试通过未证明 R1 正确：当前成功用例仅验证迁移和开放，未要求完整验证调用；使用模拟 docker/systemctl，不是实际镜像或生产服务验收。

## Stage 2

**未执行**：Stage 1 存在 HIGH。未给出代码质量、安全扫描和视觉对比 PASS。修复后须重新 review-prepare，以新 candidateId 从 Stage 1 起复审；不得用本报告批准后续变更。
