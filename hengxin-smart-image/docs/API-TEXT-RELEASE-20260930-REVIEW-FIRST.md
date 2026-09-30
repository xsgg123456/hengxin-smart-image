# API 文案发布增量审查

- candidateId：`04e0a1573851b3b51349d0d27b7ded7165beeceebd4cd6c1c3224077822c161c`
- 基线：功能提交 `835e3af`；范围为 `scripts/release/` 下本次 8 个 api-text / api_text 发布及测试文件、`hengxin-smart-image/frontend/package.json` 版本和本轮发布文档。
- 方法：已读取 AGENTS.md、code-review skill、HARNESS-REVIEW 协议、Product-Spec.md 文首、DEV-PLAN.md 发布计划及 API-TEXT-RELEASE-20260930.md。只读实现、执行隔离本地测试，未 SSH、部署、收费生成或修改实现。
- 结论：**Stage 1 FAIL（HIGH）；Stage 2 未执行。不得批准该候选。**
- 审查结束 `review-status` currentId 与所派候选完全一致；未观察到代码变化。

## Stage 1：Spec Compliance

### HIGH：生产验收脚本必然失败

要求：DEV-PLAN.md:8–9 要求上线后验证 schema、配置、哈希、健康并留下发布证据。

实际：`scripts/release/api-text-verify.py:65` 执行 `assert validate_kind_column(sql)`；该函数在 :15–16 仅断言字段约束，成功返回 `None`。因此即使生产 `kind` 正确为 nullable varchar(20)，主流程仍必然抛出 AssertionError，无法执行 :68–88 的原生服务、入口、健康及公网资源验收。

同一段 :67 的 `result['frontendVersion'] == '0.2.14'` 没有 assert，不能充当显式版本断言。包与逐文件哈希已有间接版本保护，但此行依然无验证作用。应修复重复插入的校验代码，并以模拟外部命令、真实运行 `main()` 的成功和错误版本路径证明修复，不能只测 helper。

直接复现原始输出：

```text
valid schema helper result: None
production line 65: AssertionError reproduced
AST PASS: 8 files
```

### 其余发布要求逐项核对

| 要求 | 状态和证据 |
| --- | --- |
| 前端 0.2.14、迁移 0021→0022 | 代码完整：frontend/package.json:3；package-api-text.py:124–127；api-text-deploy.py:66–84。既有迁移 backend/migrations/versions/0022_api_text_operation_kind.py:5–19 为可空 varchar(20)，降级保留字段。尚未执行生产迁移。 |
| 两份提示词随包并同步 native | 代码完整：package-api-text.py:19–20、100、120–123；api-text-runtime.py:12–15、93–106。实际本地文件复制测试通过，缺失资源会在复制前拒绝。Dockerfile.backend:8 复制完整 backend。 |
| 已提交、已批准源码、白名单归档与逐文件哈希 | 代码完整：package-api-text.py:24–34、72–109。归档回读对比 :37–49，manifest SHA :102–104；目标包尚未在本次审查中生成，不宣称产物验收通过。 |
| 保留完整 Compose 链和固定生产基线 | 代码完整：api-text-runtime.py:47–70 取运行容器 config_files，核对指定旧镜像和环境/命令，仅追加 image/build override；本地 11 层 overlay 模拟测试通过。真实生产配置未由 reviewer 连接核验。 |
| 停止入口、排空后备份 | 代码完整：api-text-deploy.py:72–81；api-text-runtime.py:73–90 校验 pg_dump 可列举并备份 native、入口、版本及配置，最后写 COMPLETE。 |
| fail-closed 与数据库不覆盖 | 代码完整：api-text-deploy.py:104–159：排空未知不重启 worker；开放后失败保留新代码并关入口；普通回退恢复旧 app/前端/配置、保留 schema；回退失败重新关入口。相关控制器模拟故障测试通过，未在生产触发回退。 |
| 实际镜像断网安装测试 | 代码完整、执行待发布：api-text-deploy.py:57–66 使用实际 image、network none、check=True，记录并匹配镜像 ID；:12–22 明列 6 个仓库工具测试及 1 个前端接口源码对照排除。此处本地控制器测试 mock Docker，不作为真实安装测试证据。 |
| 新 API_TEXT 记录、保留旧 API_SIZE | 代码完整：api-text-runtime.py:83–89、123–126；api-text-deploy.py:142–144；api-text-verify.py:9–12。真实临时目录发布与回退测试确认 API_SIZE 原字节不变。 |
| 上线哈希、schema、健康、公网验证 | 部分实现，因上述 HIGH 阻断：api-text-verify.py:35–88 提供验证逻辑，但主流程必然在 :65 失败。 |
| 新 UI / 功能漂移 | 本候选仅 frontend/package.json:3 版本变更，无新增页面/API/表；业务功能属于已审 835e3af，本次不重复审业务与邻居视觉页面。 |
| 发布记录 | docs/API-TEXT-RELEASE-20260930.md:3–9 明确基线、策略、待上线步骤及不新增收费调用；尚无本轮生产成功声明。 |

## 验证证据及边界

独立执行 `python -m unittest discover -s scripts/release -p 'test_*api_text*.py' -v`，exit 0，结尾原始输出：

```text
----------------------------------------------------------------------
Ran 20 tests in 0.258s

OK
```

这 20 个测试通过不能推翻上述失败：`test_api_text_verify.py:14–37` 仅覆盖两个 helper，没有执行生产 `main()`。其余测试的 Docker/SQL/systemd 模拟仅证明控制流程。

8 个本轮 Python 文件独立 AST 解析通过，原始输出见上。主 Agent 提供前端 production build 32.57s exit 0、310 个后端白名单隐私通过与 audit critical 0/high 33/moderate 30/low 1 的信息；本轮未重跑，不将摘要冒充编译原始日志。全量 release 测试存在旧 `test_release_native.py` 历史 annotationoverlay 失败，未作为本轮测试通过证据。

Stage 1 已有 HIGH，依 skill 停止；**Stage 2 的质量、安全/隐私、完整测试真实性和视觉评估未执行、未给 PASS。** 主 Agent 修复后须重新 review-prepare 并复核新快照。
