# API 单张修改多图参照 · 独立审查

- candidateId：`68ea3a6063665605371a85a6b607381065fcead200f023dfa890885792634014`
- Stage 1：**PASS**。Stage 2：**PASS**。未发现需要修复的 HIGH / MEDIUM 问题。
- 范围：本轮 git diff，新增公共提示词、0017 迁移、snapshot/PG/prompt 测试及 CLI golden fixture；排除会话前已有的 PERFORMANCE 文档。不是全产品重新验收。
- 依据：`Product-Spec.md:3`、`DEV-PLAN.md:3`、`Design-Brief.md:3`，已完整读取这三个本轮条目及相关历史覆盖关系；按 `.agents/skills/code-review/SKILL.md` 执行。未改实现、未部署、未提交。
- 快照：独立 `review-status` 返回 currentId 与上述 candidateId 完全相同；approved=false 是主 Agent 尚未登记本报告，不是本次审查失败。审查中仅新增验证 Markdown/计划证据链接，未发现送审代码变化。

## Stage 1 · 需求逐项核对

以下路径省略公共前缀 `hengxin-smart-image/`。

| 本轮验收项 | 结论与证据 |
|---|---|
| 当前成品、对应原图、共用素材、可选标注依次为图1至图4 | 完整实现。`backend/app/modules/api_image_edits/versions.py:94` 按此顺序冻结，`execution.py:39` 顺序读取，`relay.py:101` 顺序编码；独立通过 `test_api_image_revision_snapshot.py:26` 的三图/四图 wire 与读取 ID 断言。 |
| 后端自动取原任务文件，不需重传 | 完整实现。`versions.py:94` 使用 item.source_id/task.material_id；前端仅文案变化，`frontend/src/views/hengxin/api-image-edits/RealRevisionDialog.vue:13`。 |
| 缺失、删除、损坏拒绝，不省略 | 完整实现。`files.py:17` 校验文件状态与删除，`:66` 校验长度/SHA256；`execution.py:44` 解码；`:122` 失败终止。独立通过 `test_api_image_revision_snapshot.py:67` 四角色×四损坏路径，断言未调用上游且旧成品保留；`:96` 检查受理前不可用文件。 |
| 当前成品唯一修改对象；原图/素材/标注各自语义 | 完整实现。`backend/app/image_revision_prompt.py:9`、`:21`、`:29`，API 共用素材采用通用替换内容语义，标注仅定位且不得进入成品。 |
| 意见或标注至少一种；仅标注默认定位指令 | 完整实现。`schemas.py:25`、公共提示词 `:32`；独立通过 `test_image_revision_prompt.py:24` 和 `test_api_image_versions.py:87`，空白意见且无标注返回422。 |
| 意见 JSON 编码 | 完整实现。公共提示词 `:32` 对受理后的意见用 json.dumps 编码，未拼为指令结构；`test_image_revision_prompt.py:12` 验证引号、换行。既有请求 schema 的首尾空白规范化保持原状。 |
| 局部修复、保留成果、不恢复旧内容、输出前对照 | 完整实现。公共提示词 `:13`、`:36` 明确这些要求，不新增平台视觉循环。这是模型指令契约，不宣称生成像素效果已验证。 |
| CLI 共用核心且原输出不变；商品/文字/首次生成不变 | 完整实现。`backend/app/execution/prompts.py:8` 只替换壁纸 wrapper，`:16` 商品/文字分支未改；独立将 HEAD 旧函数实际执行结果对照四条 golden，全部逐字一致。首次生成仍走 `execution.py:31`。 |
| API 仅返回一张完整图，不续 CLI / 不加载 Skill | 完整实现。公共提示词 `:18` 要求单图；`relay.py:165` 拒绝非单结果；`execution.py:139` 调用 RelayClient，无 CLI/Skill 接入。 |
| 受理时冻结引用、最终 prompt、规则版本 | 完整实现。`versions.py:105` 同一事务写三字段，`:77` 提交；`models.py:60` 持久 JSON。独立通过 snapshot 与 PG 测试。 |
| 自动及手动重试输入稳定 | 完整实现。`versions.py:29` 读取冻结值，`:118` 重试不重建；`test_api_image_revision_execution.py:13` 实际四次失败及手动恢复，全部参数相等；`test_api_image_revision_snapshot.py:106` 修改任务提示词/素材引用后输入仍相等。 |
| 旧修正继续一/二图协议 | 完整实现。`versions.py:35` NULL 快照分支，`execution.py:49` 保留六参数；`test_api_image_revision_snapshot.py:126` 独立通过无标注/有标注旧协议。 |
| 成功追加版本、失败保留旧图、只变目标图 | 完整实现。`versions.py:40`、`execution.py:98` 发布到目标 item；`test_api_image_revision_execution.py:13` 使用与原图不同的真实 JPEG 字节，验证失败前后旧版本及邻图完全相等、恢复后仅目标新增版本。 |
| 历史恢复后再改以恢复版本为基础 | 完整实现。`versions.py:143` 切换结果并清空 snapshot；`test_api_image_versions.py:73`、`:80` 验证再次冻结 V1，版本号递增至3。 |
| 文件引用保护、0017 迁移/旧数据兼容 | 完整实现。`files.py:55` 查 JSON 四个位置；`migrations/versions/0017_api_revision_snapshot.py:12` 幂等升级，`:18` 有实际快照拒绝降级、NULL 可往返。独立通过真实 PG `test_api_image_revision_snapshot_pg.py:26`、`:52`，不是仅 SQLite 推断。 |
| 并发、重试、模型尺寸参数保持；不承诺返回尺寸 | 完整实现。`relay.py:86` 固定参数校验、`:107` 沿用 PARAMETERS，调度模块无 diff；API 公共提示词 `:18` 不要求画布尺寸、不自动缩放；CLI 仍保留原尺寸要求。 |
| 弹框仅补说明，保持设计 | 完整实现。`RealRevisionDialog.vue:13` 唯一前端 diff 与 Brief 原句一致，无新增上传/设置。已查看真实 HTTP 联调截图 `output/api-revision-implementation-20260923/real-revision-1280.png`，说明换行完整、按钮未遮挡；与邻居历史弹框截图 `real-history-1280.png` 对照，蓝色按钮、白底圆角、次级文字和图片区域风格一致。 |
| 本地交付、无部署 | 完整实现范围。没有部署配置或生产改动；验证及边界见 `docs/API-REVISION-MULTIREF-VALIDATION-20260923.md:7`。 |

部分实现：无。未实现：无。Spec 漂移：无；新增持久字段/迁移属于明确冻结需求，无新增页面、业务 API 或自发设置。

## Stage 2 · 质量、安全与测试真实性

- 结构通过：公共构建器42行，新增迁移28行；本轮涉及的生产模块均小于300行（versions150、execution145、relay179、files83、models124、CLI prompts 见原模块；前端弹框102）。公共语义集中于 `backend/app/image_revision_prompt.py:8`，CLI/API通过参数适配，无复制两套修复文本。
- 错误处理通过：`execution.py:120` 的存储异常在发请求前变为安全错误码；`files.py:79` finally 关闭并释放流；重试不重新解释意见或读取最新素材。没有把失败改为成功的分支。
- 安全扫描通过：在变更生产文件及关联 API 模块中扫描 eval、innerHTML、dangerouslySetInnerHTML、前端密钥变量、常见密钥前缀/机器路径，未见新增命中。`relay.py:114` 凭据只用于服务端请求头；`files.py:55` 使用 SQLAlchemy JSON表达式，无用户内容拼 SQL；API prompt 使用图号而非服务器路径。`presentation.py:1` 所属模块无新增 snapshot 对外投影，前端不收到内部最终提示词。未新增外部库/API模式，无需为新依赖查询外部资料。
- 测试真实性通过：`test_api_image_revision_snapshot.py:26` 使用实际 RelayClient JSON wire 与 store.open ID 序列；虽后三角色 fixture 字节相同，ID顺序及生产编码循环一起提供角色顺序证据。损坏测试不仅改状态，还覆盖不存在对象、校验不符、校验一致但不可解码。`test_api_image_revision_snapshot_pg.py:26` 特意去掉普通FK引用，只剩JSON引用，确实证明新增保护生效。
- CLI golden 来源独立核实：执行 git HEAD 中原函数再与 fixture 比较，不只信任 fixture 注释，四条匹配；实际改动仅 wrapper。
- 交互证据复核：`output/api-revision-implementation-20260923/real-flow.cjs:8` 拦截时先 route.fetch 再断响应，确实模拟服务端已受理而客户端不确定；后续同键重放、目标只增一版、邻图不变、历史恢复/ZIP均有断言。`real-evidence.json:3` 声明模拟 relay，不能作为真实生成质量证明。reviewer查看两张真实渲染截图，未重新启动已关闭浏览器服务；独立功能验证由上述41项测试承担。
- 无 HIGH / MEDIUM 安全或质量发现。现存构建分包提示和测试依赖弃用警告不阻断本轮，不作为新增缺陷。

## 独立运行与原始输出

隔离 PostgreSQL 下执行五个测试文件：test_image_revision_prompt.py、test_api_image_revision_snapshot.py、test_api_image_revision_snapshot_pg.py、test_api_image_revision_execution.py、test_api_image_versions.py。

```text
.........................................                                [100%]
41 passed, 2 warnings in 6.32s
```

两条警告为 FastAPI/Starlette 的 httpx 与 anyio BlockingPortal 弃用提示。没有 skip。

直接运行 HEAD 旧 CLI 函数核对 fixture：

```text
HEAD CLI golden verified: 4
```

独立后端编译 `python -m compileall -q app migrations`：退出码0，原始 stdout 为空。

独立前端 `npm run build` 退出码0，关键原始输出：

```text
> hengxin-smart-image-frontend@0.2.3 build
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
transforming...
✓ 4434 modules transformed.
rendering chunks...
[plugin vite:reporter]
(!) D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/views/auth/dingtalk-login.vue is dynamically imported by D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/router/core/ComponentLoader.ts, D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/router/routes/staticRoutes.ts but also statically imported by D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/App.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.
✓ built in 35.10s
```

另复核主 Agent 全量日志 `output/api-revision-implementation-20260923/backend-linux-final.log` 原始结尾；这是已阅读的外部验证证据，未冒充 reviewer 独立全量重跑：

```text
1071 passed, 64 skipped, 15 warnings in 121.75s (0:02:01)
```

主 Agent 可对同一 candidateId 用 review-approve 登记本报告两阶段 PASS；本报告不覆盖未来改动，也不批准生产发布。实际视觉修复效果、返回尺寸不是本轮模拟 relay 测试的验收结论。
