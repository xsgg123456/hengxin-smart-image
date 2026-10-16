# 国内退役打包修复增量独立审查（2026-10-16）

## 快照与范围

- candidateId：`a7fdfb3ea7f1f180979e3d30448635f87610d35ad7ce599485adcc0a59b41589`。
- **Stage 1：PASS；Stage 2：PASS。无新增 HIGH/MEDIUM 问题。**
- 基础提交：`a0a21420f8481f073404d52c4d6f011924823416`；基础已批准快照：`2d74fa56fe64546dbaba18f7bad43028177b2a5e878a976209fe1a52263c0630`。
- 继承完整基础审查 `docs/reviews/DOMESTIC-RETIREMENT-20261016.md:3` 的产品、迁移、保护矩阵及其明确限制；本报告不把旧报告直接当作新版本通过。独立读取并全审增量文件 `scripts/release/package-retirement.py`、`scripts/release/test_retirement_safety.py`，核对共享打包器调用链；相对 HEAD 仅这两文件变化（2增1删、10增）。
- 开始和验证结束的 `review-status` 均确认 currentId 等于本 candidate，changedFiles 仅上述两文件。审查期间受控代码未变化。审查者仅新增本报告，不改代码、不登记批准、不提交、不操作生产。
- 依据：`Product-Spec.md:941`、`docs/DOMESTIC-RETIREMENT-20261016.md:3`、`:11`、`:16`；流程依据 `.agents/skills/code-review/SKILL.md:18` 和 `docs/HARNESS-REVIEW.md:7`。

## Stage 1：Spec Compliance

| 条目 | 结论与证据 |
| --- | --- |
| 删除国内旧业务专属测试夹具后仍能校验发布文件 | 完整实现。`package-retirement.py:13` 精确列出已删 `backend/tests/fixtures/cli_revision_briefs.json`，`:14` 从继承 REQUIRED 中排除；没有通配排除其他文件。真实 git 跟踪文件选择加现有生产构建资产共1186文件、103必需文件通过 validate。内存恢复旧要求时，立即因同一夹具缺失拒绝，确认修复对应实际根因。 |
| 保留 API、海外及必要发布文件 | 匹配。`:14` 集合差仅一个旧夹具，`:15`—`:17` 的0030、0029及retention worker要求保持；`:47` 将同一 REQUIRED 传给继承校验器，`:38` 继续调用原校验。新增测试 `test_retirement_safety.py:133` 对真实仓库路径逐项检查，唯一跳过 `frontend/dist/` 生成资产；本次独立真实资产校验补足该边界。 |
| 已审提交、隐私校验和禁止旧业务源码进入发布包 | 匹配。`package-retirement.py:33`—`:38` 保留拒绝旧源码、缺文件及继承版本/资产校验；`:51` 仍委托原 build，`package-overseas.py:181`—`:212` 的干净提交、已审状态、提交字节比对、隐私扫描和前后快照复核不变。`test_retirement_safety.py:112`、`:126` 的退役源码/版本/脏工作树拒绝用例独立通过。 |
| 产品及 UI 不受新增打包修复影响 | 匹配。git diff 与 review-status 仅列上述两脚本；未改页面、API、模型、迁移或依赖。UI一致性和相邻页面视觉检查沿用基础报告，本增量不适用新增页面实测。 |

部分实现、未实现：本增量无。Spec 漂移：无新增业务功能；精确移除旧夹具要求属于已授权退役发布修复（`Product-Spec.md:943`）。实际发布归档生成、镜像安装测试、生产迁移仍须主 Agent 在批准并提交后执行，本报告不宣称其完成。

## Stage 2：Code Quality

- 结构：`package-retirement.py:13`—`:14` 用明确命名的集合差表达删除范围，56行；`test_retirement_safety.py:133`—`:140` 检查实际文件，177行；均低于300行，没有新增依赖、动态外部输入或异常吞掉。
- 测试真实性：新增用例从实际脚本路径定位仓库，并对 scripts 与应用文件使用生产目录映射，未mock文件存在性；缺文件断言输出具体名称。生成资产明确交给实际打包验证，不宣称此单测覆盖生产构建。独立验证实际1186文件及恢复旧要求的拒绝路径，证明不是仅给 REQUIRED 自造空文件的循环断言。专项共23通过，见原始输出。
- 安全：两文件扫描 eval、innerHTML、前端密钥、密钥前缀、个人路径无匹配。测试 `test_retirement_safety.py:76` 的 `/opt/...` 为既有部署路径测试夹具，没有新增凭据或危险执行路径。`:148` 的发布源码隐私扫描专项也通过。仅差集调整，不改变归档来源或权限门禁。
- 视觉：本增量无UI文件变化，基础报告 `docs/reviews/DOMESTIC-RETIREMENT-20261016.md:61` 所述实际页面证据及限制继续适用；本轮未重跑浏览器或全量产品测试。

## 独立验证原始输出

初次系统 Python 缺 pytest，未计通过：

```text
python -m pytest -q scripts/release/test_retirement_safety.py scripts/release/test_retirement_deploy.py
C:\Users\82358\AppData\Local\Programs\Python\Python312\python.exe: No module named pytest
```

切换项目环境后的实际输出：

```text
uv run --project hengxin-smart-image/backend pytest -q scripts/release/test_retirement_safety.py scripts/release/test_retirement_deploy.py
.......................                                                  [100%]
23 passed in 0.21s
```

只读验证调用真实 selected / collect_assets / validate；恢复旧 REQUIRED 仅在临时 Python 进程内发生，未写代码。随后对两文件调用 Python compile：

```text
PASS actual tracked source selection + production assets validate: 1186 files; 103 required
PASS old-required regression rejected: Missing retirement runtime files: backend/tests/fixtures/cli_revision_briefs.json
PASS compile scripts/release/package-retirement.py; 56 lines
PASS compile scripts/release/test_retirement_safety.py; 177 lines
```

`python -m py_compile` 与 `git diff --check` 均无输出；前者编译本次两文件。最后快照核对原始输出：

```json
{"currentId": "a7fdfb3ea7f1f180979e3d30448635f87610d35ad7ce599485adcc0a59b41589", "reviewedId": "2d74fa56fe64546dbaba18f7bad43028177b2a5e878a976209fe1a52263c0630", "changedFiles": ["scripts/release/package-retirement.py", "scripts/release/test_retirement_safety.py"], "approved": false}
```

两阶段 PASS 仅用于本 candidate。主 Agent 可登记同一快照的 review-approve，再提交和实际打包；不得写 `.needs-review` 为 clean。源代码、必需文件校验已验证，完整归档构建和生产交付必须另留执行证据。
