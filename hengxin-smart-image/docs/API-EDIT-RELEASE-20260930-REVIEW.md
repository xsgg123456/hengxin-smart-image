# API 单张图片/文字互斥生产发布增量审查

- candidateId：`c6b38c76fd373fc4a08b9c93a2c7ddeede012474bd1ae935ec44bc7753008de4`。
- 范围：功能提交 `3359989` 之后的 `frontend/package.json`、4 份 api-edit 发布脚本及其 4 份测试；源要求为 `hengxin-smart-image/docs/API-EDIT-RELEASE-20260930.md:3` 至 `:9`。本报告不重新批准已审功能、不代表生产部署完成。
- 开始与结束独立运行 review-status，currentId 均等于以上候选，审查期间未发现受控代码变化；未修改代码、未提交、未部署。
- 使用 `.agents/skills/code-review/SKILL.md`，只读代码和本地验证。

## Stage 1：PASS

|要求|结论与证据|
|---|---|
|目标前端 0.2.15、沿用 schema 0022|完整实现。`hengxin-smart-image/frontend/package.json:3` 仅版本变更；`scripts/release/package-api-edit.py:120` 校验版本、迁移文件、全部 helper；`scripts/release/api-edit-deploy.py:67`、`:84` 双检查 schema，部署路径无执行迁移命令。|
|已提交、已审源码白名单与归档校验|完整实现。`scripts/release/package-api-edit.py:73` 拒绝 tracked dirty，检查审查凭据并逐项读取 git show，`:107` 复核快照/HEAD，`:38` 归档回读字节比较，`:103` 逐文件 SHA；正式归档生成留给提交之后。|
|三份提示词随容器和 native 同步|完整实现。`scripts/release/package-api-edit.py:16`、`:120` 三资源强制白名单，`scripts/release/api-edit-runtime.py:94` native 安装实际字节，`scripts/release/api-edit-verify.py:15`、`:46`、`:58` 覆盖五服务和 native 的资源哈希；缺资源测试拒绝安装。|
|服务器镜像安装测试前置|完整实现。`scripts/release/api-edit-deploy.py:57` 实际镜像 network none 运行 pytest，成功才写 image ID，`:66` 切换前匹配同一 ID；`:12`、`:19` 仅排除仓库工具和单个源码对照用例。实际服务器安装测试尚待主 Agent 执行。|
|现网基线和完整 Compose 链|完整实现。`scripts/release/api-edit-runtime.py:48` 从运行容器 labels 获取全部路径，核对五服务旧镜像/环境/命令；`:64` 覆盖仅 image/build，保留旧链；`scripts/release/test_api_edit_runtime.py:18` 用 11 层链和既有资源/网络配置验证。|
|关接纳、排空、备份再切换|完整实现。`scripts/release/api-edit-deploy.py:68` 首检零在途，`:73` 关闭入口/生产者，API drain、native stop 后再次检查；`:80` 停 variants 后备份，`:85` gate 检查；`scripts/release/api-edit-runtime.py:74` pg_dump + pg_restore list、native/前端/Compose 备份及 COMPLETE 标记。|
|故障回退与排空不明不强停|完整实现。`scripts/release/api-edit-deploy.py:105` 开放后故障保留新执行器并关入口，`:114` 排空不明不重启 Worker，`:123` 备份恢复旧代码、前端入口和发布标记；回退失败再次关入口。`scripts/release/test_api_edit_deploy.py:129` 起覆盖 schema、备份、安装、前端中断、排空、开放后和回退失败。|
|五服务、native、前端、健康、历史及只读公网验收|完整实现。`scripts/release/api-edit-verify.py:49` 验证五服务镜像 ID/配置/字节，`:69` schema/列定义/版本/native/暂停/gate，`:81` 历史计数、ready，`:84` 公网页和静态资源 SHA、匿名 401，无创建生成请求。真实线上响应待发布后采集。|
|UI 一致性、引导真实性、Spec 漂移|本增量无 UI/业务实现变更，前端 diff 仅 `package.json:3`；无新页面/API/表/迁移。视觉与邻居页面对比不适用此增量，不能把此报告当新业务 UI 的重验。|

部分实现/未实现：本次发布工具范围内未发现。发布执行、镜像安装结果、真实公网交互和收费模型质量均未在本审查中验收。

## Stage 2：PASS

- 代码质量：职责分为 package/deploy/runtime/verify，均小于 300 行；`scripts/release/api-edit-runtime.py:20` subprocess 使用参数数组、check=True，`:41` 检查哈希/路径约束，`:94` native 安装拒绝符号链接；`scripts/release/api-edit-deploy.py:105` 明确故障路径。无新增阻断质量问题。
- 测试真实性：独立执行新增 25 项全部通过；控制器测试实际执行 main 并模拟可达失败状态，native 测试实际写临时文件验证字节，verify 测试实际走 main，非只看静态字符串。证据 `scripts/release/test_api_edit_deploy.py:28`、`scripts/release/test_api_edit_runtime.py:61`、`scripts/release/test_api_edit_verify.py:58`、`scripts/release/test_package_api_edit.py:14`。这些是本地模拟，不能替代服务器断网安装测试。
- 安全扫描：4 份实现文件扫描 eval、innerHTML、前端 secret/token key、sk-ant/sk-proj 无匹配；`scripts/release/package-api-edit.py:54` 文件名/后缀/压缩内容隐私检查，`:90` 源码 privacy_check；`scripts/release/api-edit-deploy.py:34` umask 077 保护运行配置与备份，SQL 为固定语句或内部固定列白名单（`scripts/release/api-edit-verify.py:71`）。固定 `/opt` 路径为明确服务器部署目标。未发现新增密钥或注入。
- 执行约束：脚本广泛使用 assert 作为发布门禁（如 `scripts/release/api-edit-deploy.py:66`），须按脚本既定普通 Python 模式运行，不能加 `-O` 或设置 PYTHONOPTIMIZE。
- 既有问题：全发布测试 1 项失败，位于未改动的 `scripts/release/test_release_native.py:100`，仍固定 annotation-20260924-6b43b3c 的历史基线；非本候选回归，不得称全发布全绿。依赖审计数字属于主 Agent 提供证据，本审查未重新联网 audit；本候选仅改版本，依赖及锁文件无变更。

## 独立验证原始输出

新增测试命令：`python -m unittest discover -s scripts/release -p test_api_edit*.py` 和 `python -m unittest discover -s scripts/release -p test_package_api_edit.py`。

```text
Ran 20 tests in 0.316s

OK
Ran 5 tests in 0.005s

OK
```

全发布：`python -m unittest discover -s scripts/release -p 'test_*.py'`，完整日志 `output/api-edit-review-tests.log`。

```text
FAIL: test_frontend_manifest_matches_seven_native_files (test_release_native.NativeReleaseTests.test_frontend_manifest_matches_seven_native_files)
Traceback (most recent call last):
  File "D:\Work_Project\hengxin-smart-image\scripts\release\test_release_native.py", line 100, in test_frontend_manifest_matches_seven_native_files
    self.assertTrue(manifest['composeBaseOverlays'][-1].endswith('annotation-20260924-6b43b3c/api-override.yaml'))
AssertionError: False is not true
Ran 109 tests in 3.910s
FAILED (failures=1, skipped=1)
```

Python 编译：`python -m compileall -q scripts/release/api-edit-deploy.py scripts/release/api-edit-runtime.py scripts/release/api-edit-verify.py scripts/release/package-api-edit.py`，exit code 0，stdout/stderr 为空。

前端独立类型检查：`pnpm typecheck`，exit code 0，原始输出：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.

> hengxin-smart-image-frontend@0.2.15 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

正式前端 build 的 exit 0 由主 Agent 提供，本审查没有重复构建或改写 dist。两阶段 PASS 仅对应本候选发布增量；由主 Agent 对同一 candidateId 用 review-approve 登记，继续服务器安装与发布验收。
