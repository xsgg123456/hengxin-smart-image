# API 换套图优化发布增量审查

2026-09-22。Stage 1 **PASS**；Stage 2 **PASS**。本次受控代码增量无 HIGH / MEDIUM 问题。

candidateId：`d3590c3b44e08e9b62f547c445d508765409f99bdadfda86d9cfa592bc1b8b8b`。
承接已批准候选：`e01e12ead14cc83416ec66f98ce557132cb480f01967f9133f1ad5a5e21ce057`。

范围仅为前一候选之后的受控代码发布增量、版本元数据与需求/部署计划一致性；不审查 output 中正在准备的部署脚本，不代表生产发布或收费生图验收。遵照主 Agent 指定范围，不重复完整功能测试。

## 快照证据

Reviewer 独立解析 `.codex/review-state.json:1`，比较 approved.snapshot.files 与 candidate.files 的全部键和值，唯一变化为 `hengxin-smart-image/frontend/package.json:3`。git diff 确认为 `0.2.1` → `0.2.2`。其余受控文件（包括依赖锁、迁移、测试、正式页面及框架规则）哈希相同。

上一报告 `docs/API-IMAGE-OPTIMIZATION-IMPLEMENTATION-REVIEW.md:3` 的文件 SHA256 实测为 `e973af425d81c355946f07e274b6345ad8ece222b79c12da7ccbe1cdb47c49c3`，与批准凭据 report.sha256 相同；凭据 stage1/stage2 均为 PASS。

Reviewer 使用 bundled Python 独立执行 `harness.py review-status`，退出0，原始输出：

```json
{"currentId": "d3590c3b44e08e9b62f547c445d508765409f99bdadfda86d9cfa592bc1b8b8b", "reviewedId": "e01e12ead14cc83416ec66f98ce557132cb480f01967f9133f1ad5a5e21ce057", "changedFiles": ["hengxin-smart-image/frontend/package.json"], "approved": false}
```

`approved:false` 表示本候选尚待主 Agent 根据本报告登记，并非沿用旧批准。审查时未发现送审候选之外的受控代码变化。默认 python 不在 PATH，backend/.venv 启动器无法启动其 Python312 基础解释器；改用工具提供的 bundled Python 后上述检查成功。

## Stage 1：Spec Compliance

依据 `Product-Spec.md:4`、`DEV-PLAN.md:4`、`docs/API-IMAGE-OPTIMIZATION-IMPLEMENTATION.md:7` 和 `hengxin-smart-image/docs/API-IMAGE-OPTIMIZATION-DEPLOYMENT-20260922.md:7`。正式实现要求保持不变，发布计划明确指定前端0.2.2。

下列原审查条目均逐项核对承接关系；原报告简称 R=`docs/API-IMAGE-OPTIMIZATION-IMPLEMENTATION-REVIEW.md`。表中结论来自已验证未变化的实现及已批准证据，不声称本轮重跑这些测试。

| 条目 | 增量判定与证据 |
|---|---|
| 每批最多10张及10+1顺序 | 完整实现结论保持；R:13，claims.py:42、:54。 |
| 首调外3次退避及失败项重试 | 完整实现结论保持；R:14，outcomes.py:27、versions.py:97。 |
| 租约、心跳、不确定执行与迟到隔离 | 完整实现结论保持；R:15，claims.py:47、heartbeat.py:11。 |
| 回执后只重新收图 | 完整实现结论保持；R:16，execution.py:103、outcomes.py:42。 |
| 紧凑记录、操作人、静默刷新 | 完整实现结论保持；R:17，RealRecords.vue:59、use-records.ts:25。 |
| 当前结果与可选标注/意见、输入验证 | 完整实现结论保持；R:18，schemas.py:26、versions.py:84。 |
| 修改失败保旧结果与冻结基础图 | 完整实现结论保持；R:19，versions.py:89、outcomes.py:18。 |
| 不可变历史、编号、下载和恢复 | 完整实现结论保持；R:20，versions.py:32、:110。 |
| 修改/失败/打包时切版限制 | 完整实现结论保持；R:21，versions.py:117、RealTaskDetail.vue:40。 |
| 当前版一致快照完整ZIP | 完整实现结论保持；R:22，zip_download.py:16、files.py:64。 |
| 幂等、权限、引用保护、0016迁移 | 完整实现结论保持；R:23，router.py:23、迁移0016:13。 |
| 前端未知请求恢复与防重 | 完整实现结论保持；R:24，item-command.ts:7。 |
| UI与预览/邻居一致、双宽度 | 完整实现结论保持；R:25及:48，页面/CSS哈希未变。 |
| 0.2.2发布元数据 | 完整实现；frontend/package.json:3 与部署计划:7匹配。 |

表中后端相对路径以 `hengxin-smart-image/backend/app/modules/api_image_edits/` 为根，前端以 `hengxin-smart-image/frontend/src/views/hengxin/api-image-edits/` 为根，迁移位于 `hengxin-smart-image/backend/migrations/versions/0016_api_image_versions.py`。

部分实现/未实现：本次增量未发现。Spec漂移与死引导：唯一变更为版本字符串，未新增页面、提示、API或行为。生产备份、排空API Worker、0016、独立overlay及保留CLI范围在部署计划:8–11完整列明；回退不能重放新revision的边界在:15列明。本结论只确认文档覆盖，实际执行需另附发布证据。

## Stage 2：Code Quality

| 检查 | 结论与证据 |
|---|---|
| JSON、结构与依赖一致性 | PASS。package.json可正常JSON解析，143行；仅第3行变更，无脚本/引擎/依赖变化。pnpm-lock.yaml:10 的根importer不记录项目自身版本，锁文件保持前一批准哈希。 |
| 安全增量 | PASS。唯一新增字符串为0.2.2，无凭据、注入、危险函数或新增暴露变量；既有安全结论承接R:47。 |
| 测试真实性 | PASS。未新增或改弱测试，测试文件哈希保持；真实PG/HTTP与模拟上游的边界承接R:46、:75、:81。版本元数据调整无需新增镜像式单测。 |
| 视觉 | 本轮无渲染变更，承接R:48邻居与正式截图对比；未再次打开页面，不将历史截图称为本轮生产截图。 |
| 构建 | PASS。实际读取本次production构建日志，4431模块转换并成功35.19s；原始输出见下。 |

## 构建原始输出及边界

`output/api-optimization-release/build.log:1`、:3、:5、:389：

```text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 4431 modules transformed.
✓ built in 35.19s
```

日志:8仍有既有钉钉登录页混合动态/静态导入警告，非构建失败：

```text
dynamic import will not move module into another chunk.
```

0.2.2是package发布元数据；构建日志的 `hx-frontend-1` 来自 `hengxin-smart-image/frontend/vite.config.ts:16`、:31，不是package版本，不能据此声称线上页面已显示0.2.2。主 Agent 应以发布清单与产物/源码哈希核对生产版本。

主 Agent 可为上述同一候选登记两阶段PASS；本报告不写clean、不提交、不部署。生产脚本、产物安装完整性、服务健康、迁移与回退准备需由发布流程继续验证。
