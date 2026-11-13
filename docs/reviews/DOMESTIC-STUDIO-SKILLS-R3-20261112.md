# 国内 Skills 管理独立复审 R3 · 2026-11-12

- 送审 candidateId：`2644f2c300a0a314f06d8e1c751cc46db72fb4e2d93fddc0b49136c0726b8f74`。
- 范围：国内超级管理员权限及撤权并发、五工作台初始空绑定与 CAS、保存中草稿、目录刷新、文件夹上传及校验、差异确认、ZIP、启停与删除、不可变引用与回收、崩溃恢复、国内外隔离及共享海外代码回归。基准为 `Product-Spec.md:3-11`、`Design-Brief.md:1-3`、`DEV-PLAN.md:1-10`、`docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:1-24` 和 `frontend/preview-domestic-studio/Skills.vue`，并复核此前两份 Skills 审查报告。
- **Stage 1：FAIL；Stage 2：未执行。** 首次安装在建立发布日志前崩溃后无法恢复，属于阻断功能的问题。报告不能登记两阶段 PASS。
- 快照：审查开始及执行测试后，`python .codex/hooks/harness.py review-status` 的 `currentId` 均等于上述 candidateId；本 reviewer 未修改产品代码。审查期间主 Agent 更新了 `Product-Spec.md:6,8` 与 `Product-Spec-CHANGELOG.md`，登记会话仅创建人可见及成品库可见范围；这些 Markdown 不属于 harness 代码快照，也不改变本次 Skills 管理范围。最终批准前仍应由主 Agent 再核对快照。

## Stage 1 阻断问题

### HIGH：首次安装在创建空目录版本时进程崩溃，之后无法再读取或安装

`Product-Spec.md:9-11` 要求管理员上线后上传、配置 Skill 并具备失败恢复。空的安装目录是合法初始状态（`backend/app/overseas/management/installed_catalog.py:142-152`）。国内首次安装调用共享 `prepare_release`（`backend/app/modules/domestic_studio/skill_publication.py:55-68`），该函数先执行 `write_release(root, [])`，后创建 `current.json`（`backend/app/overseas/management/skill_objects.py:87-94`）。`write_release` 先创建 `releases/.install-*` 并写入清单（同文件 `:21-35`），只有调用栈正常退出才由 `finally` 清理（`:40-42`）；若进程在此时强制退出，`current.json` 和 `.pending.json` 均尚不存在。恢复器只处理 `.pending.json`（`backend/app/overseas/management/skill_publication.py:47-52`），故进程重启及周期恢复都不会处理此状态（`backend/app/overseas/management/skill_publisher.py:25-45`）。目录读取会把残留的 `releases` 判为没有索引的非空目录并拒绝（`installed_catalog.py:142-151`），后续安装入口在准备新版本前也会读取此目录（`domestic_studio/skill_publication.py:55-56`），无法自恢复。这是国内首次上线的核心上传路径；共享实现亦应检查对海外首次安装的影响。

**独立复现，使用隔离临时目录，不访问生产：** 在 `hengxin-smart-image/backend`，以下 PowerShell 命令在子进程刚写完第一份空目录的清单时执行 `os._exit(79)`，模拟进程被强制终止；随后调用真实共享恢复器、目录读取及重试准备函数。故障注入只改变该子进程内的函数引用，不修改文件代码。测试没有调用 HTTP，也没有模拟断电造成的底层文件系统损坏。

```powershell
@'
import os, subprocess, sys, tempfile
from pathlib import Path
from types import SimpleNamespace
from app.overseas.management import skill_objects, skill_publication, installed_catalog

with tempfile.TemporaryDirectory(prefix='review-first-publish-crash-') as temporary:
    root = Path(temporary) / 'domestic-skills'
    root.mkdir()
    code = '''from pathlib import Path\nimport os,sys\nfrom app.overseas.management import skill_objects\nroot=Path(sys.argv[1])\noriginal=skill_objects.atomic_json\ndef abrupt(path, value):\n    original(path,value)\n    if path.name == "manifest.json": os._exit(79)\nskill_objects.atomic_json=abrupt\nskill_objects.prepare_release(root, [])\n'''
    process = subprocess.run([sys.executable, '-c', code, str(root)])
    print('child_exit_code:', process.returncode)
    print('root_entries_after_crash:', sorted(path.name for path in root.iterdir()))
    print('release_entries_after_crash:', sorted(path.name for path in (root / 'releases').iterdir()))
    print('pending_exists:', (root / '.pending.json').exists())
    store = SimpleNamespace(installed_root=root, protected=False)
    print('recover_return:', skill_publication.recover(store, None))
    for label, action in [('read_catalog', lambda: installed_catalog.read_catalog(root)),
                          ('retry_prepare_release', lambda: skill_objects.prepare_release(root, []))]:
        try:
            print(label, ':', action())
        except Exception as error:
            print(label, ':', type(error).__name__, str(error))
'@ | .\.venv\Scripts\python.exe -
```

原始输出：

```text
child_exit_code: 79
root_entries_after_crash: ['releases']
release_entries_after_crash: ['.install-20b0q9b2']
pending_exists: False
recover_return: None
read_catalog : ValueError Skill installation has no published catalog
retry_prepare_release : ValueError Skill installation has no published catalog
```

建议在首次初始化及对象/目录准备的所有持久化阶段建立可辨认、可校验且可恢复的状态，确保不把未知或已有用户数据误当暂存垃圾；修复后对首次和已有目录在日志创建前、指针切换前后的进程终止边界分别重启复验，同时验证国内与共享海外回归。当前已有恢复测试 `backend/tests/test_domestic_skill_publisher.py:177-211,226-270` 覆盖日志及提交前后部分情形，没有覆盖本复现的首次空目录初始化崩溃点。

## R2 三项修复复核

1. **撤权与绑定/启停写入：所测两种 PostgreSQL 顺序通过。** 两路由在事务内先调用 `authorize_write`（`backend/app/modules/domestic_studio/management_router.py:138-157`）；授权先持有权限 advisory lock，再锁并刷新当前用户（`backend/app/modules/domestic_studio/skill_publication.py:19-29`），随后才由绑定/启停取得 execution gate（`backend/app/modules/domestic_studio/bindings.py:36-44`、`skill_state.py:28-34`）。`backend/tests/test_domestic_admin_permissions_pg.py:74-115` 对两路由分别验证撤权先提交返回 403 且数据库未写，以及写入持锁后撤权等待、写入先完成。使用指定临时 PostgreSQL 的随机 schema，独立执行四例均通过；实际目录为测试 fixture，未验证生产部署。
2. **保存期间其他下拉草稿：所测路径通过。** `frontend/src/views/hengxin/admin/DomesticStudioBindings.vue:6,32-38` 保存时禁用选择框；父页 `frontend/src/views/hengxin/admin/skills.vue:4-7` 保存时禁用切回目录。组件测试 `frontend/tests/domestic-studio-skills.test.ts:76-94` 延迟请求并检查禁用、完成后恢复和事件。未进行真实浏览器交互。
3. **目录刷新时绑定标签：代码链路及组件测试通过。** `frontend/src/views/overseas/admin/OverseasLiveSkills.vue:36-39` 刷新目录时通知父组件；`frontend/src/views/hengxin/admin/skills.vue:21-29` 重新请求绑定并以序号防止旧响应覆盖；组件测试 `frontend/tests/domestic-studio-skills.test.ts:107-116` 验证刷新通知。未做双浏览器交互复验。

## 其他范围内逐项状态

- **五项初始空与并发 CAS：代码和自动测试覆盖。** `backend/migrations/versions/0033_domestic_studio_bindings.py:11-26` 建表不插入绑定；`backend/app/modules/domestic_studio/bindings.py:30-33,36-44` 对缺项返回空并在 gate 内比较 expected；真实 PG 的陈旧快照用例为 `backend/tests/test_domestic_studio_bindings_pg.py:102-112`。
- **上传、校验、同名差异、ZIP、启停和删除：相关自动测试通过，实际浏览器全流程未执行。** 路由位于 `backend/app/modules/domestic_studio/management_router.py:77-144`，上传和差异 UI 位于 `frontend/src/views/overseas/admin/SkillFolderUpload.vue:3-15`；`backend/tests/test_domestic_skill_publisher.py:57-117` 和前端 `tests/skill-folder-zip.test.ts`、`tests/skill-folders-components.test.ts` 为受测证据。首次发布崩溃缺陷使此项整体不通过。
- **引用保护和无引用回收：相关基础测试通过。** `backend/app/modules/domestic_studio/skill_references.py:15-32,35-56` 固定并校验引用；`backend/app/modules/domestic_studio/skill_publication.py:64-68,84-107` 按引用保护并规划清理。`backend/tests/test_domestic_skill_publisher.py:81-162` 和 `tests/test_domestic_skill_references_pg.py:23-68` 覆盖引用及净释放量；真实执行器、会话删除及最终回收闭环尚未接入，不能宣称已验收。
- **国内外隔离和共享海外回归：有代码边界和局部测试。** `backend/app/modules/domestic_studio/installed_skills.py:16-36` 限制业务上下文及根目录，`backend/app/modules/domestic_studio/skill_publisher.py:13-31` 使用独立目录并关闭共享维护入口；本次运行了海外发布恢复/传输及前端共享组件相关测试。未验证生产路径的挂载、属主、套接字权限或海外全链路。
- **UI 和 Spec 漂移：未完成实页面比较及全范围漂移扫描。** `frontend/src/views/hengxin/admin/skills.vue:2-7` 为目录/绑定页签，`frontend/src/views/overseas/admin/OverseasSkillCatalog.vue:20-25,52-58` 提供绑定信息及国内 ZIP 模式；这些代码证据不等于实际渲染通过。
- **未接入且不计入本阶段通过：** 五工作台、执行器、会话、成品库及发送时冻结/防绕过的端到端路径；现状见 `docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:3,17`。

## 独立执行的验证

后端在 `hengxin-smart-image/backend` 设置 `TEST_DOMESTIC_STUDIO_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:35439/hx_studio_test`，运行 `python -m pytest -q`，范围包括 `tests/test_domestic_admin_permissions_pg.py`、`test_domestic_studio_bindings_pg.py`、`test_domestic_skill_references_pg.py`、`test_domestic_studio_bindings.py`、`test_domestic_studio_management.py`、`test_domestic_skill_publisher.py`、`test_domestic_skill_state.py`、`test_domestic_installed_skills.py`、`test_domestic_studio_policy.py`、`test_domestic_studio_migration.py`、`test_domestic_skill_state_migration.py`、`test_skill_publisher_recovery.py`、`test_overseas_skill_transfers.py`、`test_overseas_skill_transfers_failures.py`，使用 `.venv/Scripts/python.exe`。原始汇总：

```text
112 passed, 2 warnings in 65.41s (0:01:05)
```

两条 warning 分别为 Starlette TestClient/httpx 和 anyio BlockingPortal 弃用提示。另单独执行四例撤权 PG 测试，原始汇总：`4 passed, 2 warnings in 3.24s`。PG fixture 仅创建并删除随机 schema（`backend/tests/test_domestic_studio_bindings_pg.py:17-41`）。

前端执行 `pnpm exec tsx --test tests/domestic-studio-skills.test.ts tests/skill-folder-zip.test.ts tests/skill-folders-components.test.ts tests/skill-folders.test.ts tests/business-route-access.test.ts tests/roles-integration.test.ts`，原始汇总：

```text
ℹ tests 37
ℹ suites 0
ℹ pass 37
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1769.7692
```

编译类型检查 `pnpm exec vue-tsc --noEmit` 退出码 0，原始输出：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
```

Stage 1 已有 HIGH，未执行 Stage 2 的质量审查、安全扫描或实际页面与邻居页面视觉对照；未独立重跑真实 PG 的 0033–0036 完整迁移，也未进行真实部署及浏览器上传下载验收。
