# PDF Worker MIME 兼容增量审查

- 日期：2026-10-13。
- candidateId：`ca5b7f78948cfbfca9291087b608cc1fcff721875be792dd6738f6c7b8ef7ece`。
- 基线：HEAD `823fc85`，完整功能审查沿用 `docs/reviews/requirements-20261013.md:1` 的两阶段 PASS。本次仅审查以下三文件差异及其正式构建产物，不声称重新执行完整功能或生产验收。
- 范围：`hengxin-smart-image/frontend/vite.pdf-assets.ts`、`scripts/release/package-overseas.py`、`scripts/release/test_package_overseas.py`。
- 方法：读取 code-review skill、快照协议、Spec 原文、三文件完整实现、原始测试/编译日志；独立执行正式产物名称、引用、原始及 gzip 字节核对和全部产物打包审计。

## 结论

**Stage 1：PASS；Stage 2：PASS。** 无 HIGH/MEDIUM 阻断问题。结论只对应上述候选及三文件增量；由主 Agent 登记 review-approve。

审查开始时构建生成的 `components.d.ts` 导致临时 currentId 为 `340e3782e28e519d5e502ffaca4e61446a8134f0417256c73ac58b49b79f9aaf`。主 Agent 恢复该生成文件后，reviewer 重新运行 review-status，确认 currentId 恢复为本报告 candidateId，git diff 仅三文件、7 行新增、3 行删除，未将临时快照结论覆盖最终快照。

## Stage 1：Spec Compliance

| 检查项 | 结论及证据 |
|---|---|
| 真实 PDF 阅读所需 worker 可交付 | 完整。`Product-Spec.md:990` 要求真实 PDF 分页/缩放；`frontend/vite.pdf-assets.ts:23` 仅将名字匹配 `pdf.worker.min.mjs` 的资产输出为带 hash 的 `.js`，适配主 Agent 实查的生产 nginx JavaScript MIME 配置。正式产物为 `pdf.worker.min-CjEcRF4W.js`，`dist/assets/MaterialPdfReader-CGlpDd4i.js:1` 引用该名称；原源码 `frontend/src/views/overseas/MaterialPdfReader.vue:14` 导入 URL、`:52` 设置 workerSrc。 |
| worker 内容与锁定依赖一致 | 完整。`scripts/release/package-overseas.py:90` 匹配 `.js` 产物，`:94` 校验 6.4.299，`:96` 仍以原始 `.mjs` 为参考，`:98` 解压 gzip，`:99` 精确逐字节核对。正式 `.js` 及 `.js.gz` 解压后均为 1264342 字节，SHA256 均为 `9536359f1b8367850d485731ca1d5e45c159a7b7a0912325e539937aa21ceb18`。 |
| 其他资源及既有功能 | 匹配增量范围。`frontend/vite.pdf-assets.ts:23` 非 worker 路径保持默认 `assets/[name]-[hash][extname]`；`:33` 仍按明确路径输出字体/CMap/解码器。人工审核、退回、权限、下载和资源回收代码无差异，Spec `Product-Spec.md:985` 至 `:991` 的其余条目沿用基线审查。 |
| UI、引导真实性、Spec 漂移 | 未新增或修改页面、样式、文案、API、数据库或业务行为。三文件均为资源输出/审计/测试变更；视觉结论沿用基线，本次按派发范围未启动浏览器，主 Agent 负责正式构建浏览器复验。 |

表中 `frontend/` 和 `dist/` 分别相对 `hengxin-smart-image/` 和 `hengxin-smart-image/frontend/`。

## Stage 2：Code Quality

| 检查项 | 结论及证据 |
|---|---|
| 命名、类型与结构 | PASS。`frontend/vite.pdf-assets.ts:4` 使用 Vite Plugin 类型，`:23` 回调接受上下文类型，没有新增 any 或危险动态执行；三文件均小于 300 行。改名与发布校验同步，未重写依赖源码。 |
| 测试真实性 | PASS。`scripts/release/test_package_overseas.py:84` 至 `:103` 同时覆盖新 `.js` 名称、原始字节、gzip、内容被改、版本错误；`:106` 至 `:110` 继续拒绝泛化二进制例外。reviewer 额外以真实 dist 和真实依赖执行审计，避免只信任合成测试。 |
| 安全 | PASS。`scripts/release/package-overseas.py:90` 至 `:100` 仍仅对精确路径实施 pinned 内容例外，并保留 symlink、版本、字节检查；其余资产走原审计。三文件差异无凭据、用户输入执行、HTML 注入或 SQL 拼接。 |
| 正式全部资产 | PASS。独立执行 `collect_assets(dist)`，826 项资产全部通过既有审计。worker 原始和 gzip 均通过专用审计。 |
| 视觉对比 | 本增量不适用新视觉比较：没有视图/样式变更，沿用基线报告已记录的实际渲染比较。主 Agent 的浏览器 worker 加载复验属于交付验证，未在本报告冒充已执行。 |

## 编译与测试原始输出

`output/requirements-build.log` 的命令及最终输出（日志全文保留在原文件）：

```text
> hengxin-smart-image-frontend@0.2.25 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
✓ built in 36.25s
```

日志另含 pnpm 字段迁移提示，不是此次编译失败；主 Agent 报告进程退出码 0。

`output/requirements-release-tests.log` 原始输出：

```text
......................................                                   [100%]
38 passed in 1.05s
```

reviewer 独立产物验证原始输出：

```text
workers: ['pdf.worker.min-CjEcRF4W.js', 'pdf.worker.min-CjEcRF4W.js.gz']
pdf.worker.min-CjEcRF4W.js bytes= 1264342 sha256= 9536359f1b8367850d485731ca1d5e45c159a7b7a0912325e539937aa21ceb18 exact=PASS audit=PASS
pdf.worker.min-CjEcRF4W.js.gz bytes= 1264342 sha256= 9536359f1b8367850d485731ca1d5e45c159a7b7a0912325e539937aa21ceb18 exact=PASS audit=PASS
referencing bundles: ['MaterialPdfReader-CGlpDd4i.js']
all production assets audit PASS count= 826
```

## 交付边界

后端镜像安装测试在报告生成时仍由主 Agent 执行，与本次三文件增量无关；其成功及正式浏览器复验、部署后实际响应 MIME/功能检查均由主 Agent 完成。本报告不是生产部署成功凭据。
