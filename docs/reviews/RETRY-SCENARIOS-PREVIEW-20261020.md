# 重试场景独立前端预览审查

- 日期：2026-10-20；审查角色：code-reviewer；使用 code-review skill。
- candidateId：`9f9be3235b2ff3c62bdbfbafbe127a6d1d32a43cc1f8861dcb6222762e238fc1`。
- 结论：Stage 1 **PASS**；Stage 2 **PASS**；仅批准本地独立预览的限定范围，不批准正式产品实现、提交或部署。
- 范围根目录（下文 `P`）：`output/api-retry-vue-preview-20261020/`。对照主 Agent 转交的用户最新要求：简单提示、无管理员核实入口、真实前端副本、15 个场景可切换、错误可恢复、单图和批量重试演示。
- 已阅读 Product-Spec.md。正式重试合同的后端限流、持久化、未知结果处理不属于此次预览验收；不能用模拟成功证明正式业务能力。
- output 被 Git 忽略，candidateId 不包含预览源码。额外固定全部 src 文件 SHA256 清单：`P/scenarios/reviewer-src-sha256.txt`，清单 SHA256 为 `472A8F00D23714BF5B37D437DDC63BF05BDFCE6FBC58FE5DA775068D668B203D`。审查起止清单比较无差异。主 Agent 如修改 src 必须重新审查对应差异。

## Stage 1：需求符合性

|要求|结论与证据|
|---|---|
|真实前端独立预览，隔离业务调用|完整实现。`P/src/api/api-image-edits.ts:5` 使用真实记录组件；`:39` 将未模拟请求交给明确抛错的 fetcher。复核请求记录为空，未触达业务接口。|
|15 个场景可切换|完整实现。`P/src/api/retry-preview-scenarios.ts:1` 至 `:16` 定义 queued、generating、retrying、busy、saving、mixed、partial、failed、stopped、completed、recovering、refresh_error、download_error、retry_error、unavailable；`P/src/api/retry-preview.ts:24` 重置场景、清理旧定时器，`:42` 至 `:57` 建立对应状态。逐场景现有证据 `P/scenarios/evidence.json:2` 与 `P/check-scenarios.mjs:37` 至 `:66` 一一对应，未跳过场景。|
|顶部下拉、上一场景、下一场景、查看图片状态|完整实现。`P/src/views/hengxin/api-image-edits/RetryPreviewControls.vue:5` 至 `:10`；`:22` 定位未完成图片。`RealTaskDetail.vue:3` 在抽屉标题栏接入。审查者实测同一抽屉从下载错误切换到提交错误，恢复 6/11 和可用批量重试按钮。|
|整体进度一句话，每张图一个状态|完整实现。`RealTaskDetail.vue:17` 仅一个 overall-progress，`:71` 至 `:84` 按场景生成简短文案；`:24` 单一图片状态标签；`GenerationPlaceholder.vue:11` 至 `:12` 的 simple 模式移除重复状态文案；`ApiResultPicture.vue:6` 仅此图片组件使用 simple。`P/check-scenarios.mjs:42` 断言唯一进度，截图显示一致。|
|不堆技术词语，不要求管理员核实|完整实现。`RealTaskDetail.vue:10` 至 `:39` 无原管理员核实入口；`ItemRetryStatus.vue:3` 只呈现停止操作；`ChannelNotice.vue:2` 至 `:5` 只呈现短提示。`P/check-scenarios.mjs:43` 对 15 场景检查管理员、核实、恢复探测、发送名额、请求技术标识等禁词均未出现。|
|停止、单图和批量重试|完整实现。`P/src/api/retry-preview.ts:66` 至 `:84` 仅重新处理 failed 图片，4.5 秒后模拟成功；`:109` 至 `:112` 停止单图。现有交互证据 `P/check-scenarios.mjs:72` 至 `:78` 验证停止后单图 7/11、混合状态只重试两张后 8/11。|
|刷新、下载、提交错误可恢复|完整实现。`P/src/api/retry-preview.ts:67`、`:90`、`:115` 分别模拟已确认失败；`RealTaskDetail.vue:67` 清除刷新故障；`use-records.ts:51` 保留上次详情。审查者独立浏览器复核三条故障恢复及下载文件事件，全部通过，提交重试最终到 11/11。|
|成功图片保留、服务暂不可用禁用重试|完整实现。`P/src/api/retry-preview.ts:71` 只变更失败项；`RealTaskDetail.vue:14`、`:34` 和 `:74` 提示并禁用；`P/check-scenarios.mjs:65` 验证 unavailable 禁用。|
|继承既有布局、窄屏可操作|完整实现。对照 `P/review-baseline.png` 与 `P/scenarios/partial.png`：同为 1440×1000，抽屉起点 x=400、宽 1040，保留白底、蓝色按钮、圆角卡片、三列图片和共用素材区；删除冗长进度文字，增加明确标注的预览栏。`RealTaskDetail.vue:151`、`:164`、`:165` 保留响应式网格。目视 `mixed-cards.png` 与 `mobile-partial.png`，图片状态与动作可区分，390px 场景控件和批量按钮未横向溢出。|

部分实现：无（限上述预览范围）。未实现：无（限上述预览范围）。Spec 漂移：未发现超出此次预览要求的新页面或正式业务功能；预览选择器与 mock 明确属于本轮授权范围。

## Stage 2：代码质量与验证

- 代码质量：PASS。所审新改文件均小于 300 行，无 `any`；场景数据、模拟接口和选择控件分离（`retry-preview-scenarios.ts:1`、`retry-preview.ts:86`、`RetryPreviewControls.vue:15`）。场景切换清定时器、错误状态；通道与记录事件监听有解绑（`retry-preview.ts:26`、`RealTaskDetail.vue:93`、`use-channel.ts:25`、`use-records.ts:74`）。
- 测试真实性：PASS。既有 15 场景测试走真实页面控件，并检查进度、11 张卡片、错误恢复、下载事件和业务请求为空（`P/check-scenarios.mjs:37` 至 `:89`）；审查者额外独立运行三条错误恢复及同抽屉切换。测试前提明确为 mock 的 400 已确认失败（`retry-preview.ts:69`、`:91`、`:117`），未将网络结果未知或正式生产重试作为已验证结论。
- 安全扫描：PASS（限定文件）。对本轮 11 个文件搜索 `any`、eval、innerHTML、dangerouslySetInnerHTML、VITE 密钥变量及常见密钥前缀，0 命中（rg 退出码 1 表示无匹配）。API 隔离证据见 `P/src/api/api-image-edits.ts:39`，新增下载仅本地静态资源（`retry-preview.ts:119`、`:128`）。未发现新增注入或硬编码凭据。
- 视觉对比：PASS。实际打开并检查原始基准、部分完成、混合图片状态、390px 窄屏四张渲染截图；保留既有颜色、网格和按钮风格，简化文字符合本次要求。依据 `RealTaskDetail.vue:148` 至 `:168` 与上述截图。
- HIGH/MEDIUM 阻塞项：0。

## 原始验证输出

审查者执行 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`，进程退出码 0：

```text
TYPECHECK_EXIT=0
```

主 Agent 执行的 Vite 构建原始日志 `P/build-scenarios.log` 最后一行（审查者读取确认）：

```text
✓ built in 33.60s
```

审查者独立浏览器限定复核，进程退出码 0：

```text
PASS refresh_error
PASS retry_error
PASS download_error
PASS same drawer next; businessRequests=[]
```

完整 15 场景测试的既有原始结果：`P/scenarios/evidence.json`，15 项全列出，`errors: []`、`businessRequests: []`。本审查没有重复全量测试，也没有把现有接口之外的图片修改、版本恢复、删除等继承入口作为已验证功能。

报告与 src 哈希清单是此次审查新增产物；未修改产品代码、未写 `.needs-review`、未执行提交。主 Agent 使用相同 candidateId 按协议登记；该登记仍不扩大到被忽略的预览目录之外的正式开发/部署授权。
