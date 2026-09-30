# 多图参考与菜单发布适配独立审查

审查角色：code-reviewer；按 `.agents/skills/code-review/SKILL.md` 执行。只审查，不修复、不提交、不部署。

最终 candidateId：`9207fda858efaf945833d0f6e5f3bd6b95b78346d643368979daaefc4e035f20`。

范围：`docs/REFERENCE-MENU-RELEASE-20260930.md:3` 的发布适配。独立执行 review-status，确认相对已批准 `9821cfc1a0b28c31b2a82250bc844351518b34ecbfaa8ba9606b6effac3e8aca` 仅 frontend/package.json 与八个发布脚本/测试变化。多图参考和菜单功能沿用 `docs/REFERENCE-EDIT-IMPLEMENTATION-REVIEW-20260930.md`、`docs/API-ONLY-MENU-REVIEW-20260930.md` 的已审结果，不将本次限定审查冒充全产品复审。构建期间 components.d.ts 有生成噪声；最终 diff 为空且不在 changedFiles，已核实恢复。

## Stage 1 · Spec Compliance · PASS

| 条目 | 结论与证据 |
|---|---|
| 版本 0.2.16 | 完整实现。hengxin-smart-image/frontend/package.json:3；scripts/release/package-api-edit.py:104、127；api-edit-deploy.py:42；api-edit-verify.py:37、76 一致。test_api_edit_verify.py:133 实测拒绝安装版本不符。 |
| 基线镜像匹配、保留运行配置 | 完整实现。api-edit-runtime.py:51-69 读取现有全部 compose，:57 固定 api-edit-20260930-df0bc8d，并核对五服务运行镜像、环境与命令。test_api_edit_runtime.py:16 验证已有覆盖层、资源与网络配置保留。线上镜像实查为主 Agent 提供的交接证据，本 reviewer 未重复 SSH。 |
| 新资源完整发布 | 完整实现。package-api-edit.py:15-34 包含全部后端 app Python、测试和三份提示词；:92-101 包含正式 dist。api-edit-runtime.py:12、92-106 原生安装 Python 和三份提示词。新版 image_edit_prompt.txt 位于既有显式白名单，不依赖遗漏的前端源码打包；新增 Vue 由本次成功 dist 构建包含。test_api_edit_runtime.py:56、75 验证资源原字节安装和缺失拒绝。 |
| 无迁移 | 完整实现。api-edit-deploy.py:67、83-85 只断言现有 0022；未调用迁移。test_api_edit_deploy.py:123、167 分别验证错误 schema 在停服务前拒绝、成功路径无 migrate。归档包含既有迁移文件不等于执行迁移。 |
| 停接纳、排空及备份 | 完整实现。api-edit-deploy.py:68-81 预检空闲、关闭入口、暂停 API、排空 Worker 后再停派生消费者及备份；api-edit-runtime.py:73-89 备份数据库并 pg_restore --list 验证、保存原生 app/首页/版本标记/compose，最后写 COMPLETE。test_api_edit_deploy.py:155、167 验证未知排空不重启和备份顺序。 |
| 失败关闭与回滚 | 完整实现。api-edit-deploy.py:104-159：未确定排空保持接纳关闭；开放入口后失败保留新执行代码并关闭入口；开放前恢复旧代码、首页与配置。test_api_edit_deploy.py:129、134、142、148、161 实际执行控制器故障分支并检查文件与状态。 |
| 隔离安装及上线核验 | 完整实现。api-edit-deploy.py:57-66 使用 network none 安装测试并锁定 image ID；api-edit-verify.py:48-96 验证五服务 image ID、配置、后端/原生/前端哈希、schema、Worker、入口和匿名401。test_api_edit_verify.py:124 执行完整验证主流程。此为工具准备验收，上线和安装测试执行结果仍由后续发布记录证明。 |

部分实现：无。未实现：无。Spec 漂移：无新增页面、接口、表或业务行为；增量只有版本、基线常量和对应测试数据（上述九文件 diff）。本轮没有 UI 变更，不重复打开页面；菜单与多图界面的实际邻居视觉核查证据在前述两份已批准功能报告。

## Stage 2 · Code Quality · PASS

- 结构：四个发布脚本分别为 133/163/128/101 行，职责保持打包、控制、运行操作、验证；未引入新增复杂逻辑或超 300 行文件。版本在入口/清单/验证器一致（package-api-edit.py:104、api-edit-deploy.py:42、api-edit-verify.py:37）。
- 安全：对 api-edit 生产及测试脚本扫描 eval、innerHTML、暴露密钥变量和密钥前缀，无命中。package-api-edit.py:43、54-70、86-90 拒绝路径穿越、符号链接和敏感资源，并检查压缩内容；test_package_api_edit.py:13、24、30 独立运行通过。进程调用使用参数数组（api-edit-runtime.py:20），SQL 为固定内部语句；没有新增用户输入执行路径。
- 测试真实性：恢复测试调用真实 deploy.main，再替换外部 Docker/系统执行边界，临时目录检查实际恢复内容（test_api_edit_deploy.py:25、129）；不只是断言常量。prepare 测试提供新基线且验证保留配置（test_api_edit_runtime.py:16）。这些模拟测试不代表已在生产触发故障或恢复演练。
- 编译和包边界：package-api-edit.py:75-109 要求已提交、已批准快照，比较提交/本地文件，验证归档内容逐字节一致（:49-50）。正式包须在提交后创建，本报告未声称包已生成或生产发布完成。

当前范围无未关闭 HIGH/MEDIUM。依赖未变，本轮不据此宣称历史依赖审计风险已消除。

## 原始验证输出

reviewer 独立执行 `python -m unittest discover -s scripts/release -p 'test_*api_edit*.py' -v`，exit 0：

```text
----------------------------------------------------------------------
Ran 25 tests in 0.336s

OK
```

reviewer 独立执行四发布脚本 `python -m compileall -q`，exit 0，原始输出为空。

直接读取主 Agent 本次 `output/release-reference-build.log:3`、`:4`、`:10`、`:432`：

```text
> hengxin-smart-image-frontend@0.2.16 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
✓ 4494 modules transformed.
✓ built in 31.66s
```

构建 exit 0 由主 Agent 执行结果提供；reviewer 核对原始日志，未重复构建造成声明文件竞态。

最终结论：该 candidateId 的限定发布适配 Stage 1 PASS、Stage 2 PASS。主 Agent 可结合前序功能审查链执行 review-approve；本报告未写 clean、未登记批准、未执行生产操作。
