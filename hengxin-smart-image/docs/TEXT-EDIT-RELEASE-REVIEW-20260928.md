# 0.2.11 文字替换发布增量独立审查

日期：2026-09-28。审查人：独立 code-reviewer。使用 `.agents/skills/code-review/SKILL.md`。

candidateId：`92d05a54d9398ad57b76aa38e1cf2734cef92e05d48e68963d89443ccc46474e`。

结论：**Stage 1 PASS；Stage 2 PASS（本次发布增量范围）**。无本轮 HIGH/MEDIUM 问题。历史发布测试存在一个未改动的失败，下文单独披露；不宣称全历史测试通过。本报告不代表生产已经发布或实际镜像安装测试已经运行。

## 范围及快照

- 基线 `e282255` 的业务功能已另行审查，本轮不重复完整业务审查。
- 审查 `frontend/package.json` 版本差异，以及根目录 `scripts/release/` 下新增 `package-text.py`、`text-deploy.py`、`text-runtime.py` 和对应三个测试文件；核对 CHANGELOG 和同目录 `TEXT-EDIT-RELEASE-20260928.md`。
- 来源：`DEV-PLAN.md:3` 的四步生产发布计划、`Product-Spec.md:3` 的单图文字需求；发布授权以主 Agent 派发及 `Product-Spec-CHANGELOG.md:3` 为准。
- 审查开始与测试结束两次 `review-status` 均返回上述 currentId；未发生受控代码变化。旧 reviewedId 为 `ef78a2638abcce9111b9c4ecac6319430c49c72d92a22256c9b644e5cb1bc142`，approved=false；本报告不代替主 Agent 的 review-approve。
- 未连接生产、未修改代码、未提交；只创建本报告。

## Stage 1：Spec Compliance — PASS

| 发布要求 | 核对结论与证据 |
| --- | --- |
| 0.2.11 / 0020，可追溯且不夹带运行数据 | 完整实现。`scripts/release/package-text.py:15` 精确文件及 Python 路径白名单，`:70` 要求已提交且已审快照，`:100` 记录 commit、candidateId、文件 SHA；`:117` 强制版本/迁移/辅助脚本齐全。归档读回逐字节校验位于 `:35`。 |
| 秘密审计与静态产物 | 完整实现。`package-text.py:51` 拒绝敏感文件名、非允许后缀并递归检查 gzip；`:83` 拒绝符号链接；`:87` 复用源码隐私扫描。实跑 483 个 dist 文件 PASS；负例覆盖见 `test_package_text.py:13`、`:24`、`:30`。 |
| 真实生产链及配置保留 | 完整实现。`text-runtime.py:43` 从 live API labels 获取完整链，核对五后端服务运行状态/镜像/env/command；`:59` 只覆盖 image/build，`:64` 拒绝原生依赖漂移。11 层继承测试见 `test_text_runtime.py:16`。只读基线记录 `output/text-production-before.json:1` 支持主 Agent 描述，未自行联网生产复查。 |
| 实际镜像安装测试门禁 | 完整实现，但执行待发布阶段。`text-deploy.py:57` build 目标镜像并断网运行 pytest，`:63` 保存成功镜像 ID，`:66` 部署前比对同一 ID。`:19` 仅排除六个仓库工具测试和一个需要前端源码的契约比对；未排除整套 contracts。 |
| 关闭入口及排空 | 完整实现。`text-deploy.py:67` 要求 schema0019/未暂停/零在途；`:73` 停 web/API/outbox、暂停 API，先检查 Worker 排空后停止，`:78` 再检查零在途，`:80` 停派生消费者后备份。原辅助脚本 `image-inputs-worker.py:48` 核对 active/reserved/scheduled 与 DB；原生维护逻辑 `backend/app/worker/maintenance.py:29` 无法确认排空就拒绝停止。 |
| 排空不确定不得自动重启 | 完整实现。`text-deploy.py:114` 保持入口关闭，不进入普通恢复分支；独立执行 `test_text_deploy.py:116` 验证没有 systemctl start。 |
| 可读备份与完整标记 | 完整实现。`text-runtime.py:69` 备份 pg_dump 并由 pg_restore --list 验证可读，保存 native app、前端入口/package、发布元数据、完整原配置及各层文件，最后 `:86` 写 COMPLETE。`text-deploy.py:81` 在备份返回后才迁移，`:130` 恢复原生源码前要求 COMPLETE；备份失败测试 `test_text_deploy.py:95` 验证不迁移。 |
| 迁移、原生/容器同步及配置不扩张 | 完整实现。`text-deploy.py:83` 迁移并断言 0020/容量准入关闭，`:87` 更新原生 app 并 pip check/启动验活，`:92` 更新五服务；`text-runtime.py:89` 保留原 uid/gid，`:101` 先资源后原子入口。`backend/migrations/versions/0020_builtin_text_tasks.py:11` 仅新增 nullable prompt/放宽 Skill nullable，保留旧数据。 |
| 开放前回退不覆盖业务数据 | 完整实现。`text-deploy.py:123` 排空/停止新执行端，恢复 native、入口及发布元数据，使用原 Compose 链；没有 restore dump 或降级 schema。`test_text_deploy.py:103` 验证旧 app 恢复但 schema0020 保留。恢复失败 `:151` 继续关闭入口。 |
| 开放后新无 Skill 任务不能交给旧代码 | 完整实现。`text-deploy.py:99` 在启动 web 前设置 opening，`:106` 失败后只关闭接纳并保留新代码，不执行旧代码恢复。`test_text_deploy.py:122` 独立执行证明新代码保留且没有旧 compose up。 |
| 健康/权限/历史兼容/哈希及页面验收 | 脚本健康与 Worker 核验已实现（`text-deploy.py:90`、`:94`、`:95`、`:102`）；生产权限、历史任务、安装哈希和实际页面属于发布后人工/只读验收，尚未执行。`TEXT-EDIT-RELEASE-20260928.md:3` 明确准备阶段，未冒充上线完成。 |
| 不运行收费生成、不变更产品范围 | 匹配。`text-deploy.py:57` 的镜像测试断网；部署控制器无创建任务/模型调用。前端只变版本；无新增页面/组件/交互，视觉对比在本轮不适用，原业务 UI 审查由先前报告承担。 |

部分实现/未实现：本轮代码要求无；后续生产实际操作及核验是待执行步骤，不算本轮已完成。Spec 漂移：未发现新增业务需求。

## Stage 2：Code Quality — PASS

- 生产工具三个文件分别 125/163/118 行，各自负责打包、部署控制、系统操作，均小于 300 行；沿用原发布工具结构而未改写历史脚本。证据：`package-text.py:1`、`text-deploy.py:1`、`text-runtime.py:1`。
- 命令使用参数列表，未使用 shell=True/eval；SQL 均为固定运维语句，镜像/发布名称受约束（`text-deploy.py:35`）。无硬编码密钥、VITE 秘密变量命中。固定 `/opt` 路径是目标生产环境约定，不是个人路径泄露；`text-deploy.py:34` 设置 0077 umask，私有配置及备份不写进分发归档。
- 测试真实覆盖控制器异常分支：备份失败、迁移后失败、回退失败、排空未知、开放后失败、正常完成及仅 build；`test_text_deploy.py:24` 使用真实控制器但 mock 外部系统。该测试证明顺序及恢复状态，不能证明 Linux Docker/systemd/PG 的运行表现；生产安装测试仍必须实跑。
- `test_text_runtime.py:16` 检查只新增 image/build 且保留完整 11 层；`test_package_text.py:47` 检查必需迁移、版本和 helper，历史共用 package-delivery 与 image-inputs-worker 未改动。
- UI/邻居视觉比较不适用：本候选无 UI 源码变化，仅 `frontend/package.json:3` 升级版本；不将未开展的新视觉测试写成通过。

### 范围外既有问题（LOW）

历史全量发布测试中 `scripts/release/test_release_native.py:100` 仍断言 compose 链末层为 annotation，但 `scripts/release/image-inputs-frontend.py:39` 已追加 materials-e3c60c9；因此该用例失败。两文件相对 HEAD 均无差异，最后相关提交为 `2cdb4ff`，不是本轮回归；新包只选 text-deploy/text-runtime/image-inputs-worker（`package-text.py:29`），不执行该历史 frontend 发布脚本。建议另行将历史用例基线同步实际脚本，不能对外声称历史全套通过。

另有历史符号链接用例因 Windows WinError 1314 权限跳过，不能视为 Linux 符号链接路径已实测。

## 验证原始输出与边界

独立执行 `python -m unittest discover -s scripts/release -p 'test_*text*.py' -v`，退出 0：

```text
Ran 14 tests in 0.129s

OK
```

独立执行所有发布单元测试，退出 1（42 通过、1 失败、1 跳过）：

```text
FAIL: test_frontend_manifest_matches_seven_native_files (test_release_native.NativeReleaseTests.test_frontend_manifest_matches_seven_native_files)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "D:\Work_Project\hengxin-smart-image\scripts\release\test_release_native.py", line 100, in test_frontend_manifest_matches_seven_native_files
    self.assertTrue(manifest['composeBaseOverlays'][-1].endswith('annotation-20260924-6b43b3c/api-override.yaml'))
AssertionError: False is not true

----------------------------------------------------------------------
Ran 44 tests in 3.377s

FAILED (failures=1, skipped=1)
```

独立以 ast.parse 读取六个本轮 Python 文件，并逐个调用 audit_asset 审计已有 dist：

```text
SYNTAX_PASS 6
DIST_PRIVACY_PASS 483
```

读取主 Agent 保存的构建原始记录 `output/text-release-build.txt:3`（本 reviewer 未重复构建）：

```text
> hengxin-smart-image-frontend@0.2.11 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
...
✓ built in 32.63s
```

读取 `output/text-release-frontend-tests.txt` 原始尾部：

```text
ℹ tests 197
ℹ suites 0
ℹ pass 197
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 3663.5696
```

依赖审计沿用发布记录的 critical=0/high=33/moderate=30/low=1；本轮无依赖版本变动，不声明没有既有漏洞。正式归档、实际镜像测试、生产迁移/回退实操、权限/历史/哈希/页面验证及真实收费生成均未由本 reviewer 执行；前述 PASS 仅批准该候选的发布增量代码，后续实际发布仍须满足计划门禁。
