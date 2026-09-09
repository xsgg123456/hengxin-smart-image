# Phase 2 验证记录

日期：2026-09-09。范围：三种图片创建入口、共用上传、模板库维护及独立接口适配。仅前端模拟及 HTTP 契约验证，未接 AI、MinIO 或生产后端。

| 验证 | 当场结果 |
|---|---|
| 服务测试 | `npx --yes pnpm@10.33.4 test`：tests 13 / pass 13 / fail 0；1032.4483 ms |
| 编译及生产构建 | 独立审查运行 `npx --yes pnpm@10.33.4 build`：vue-tsc --noEmit 零错误，3263 modules transformed，built in 29.00s，exit 0 |
| 独立审查 | fresh code-reviewer Stage 1 / Stage 2 通过，详见 PHASE2-REVIEW.md |
| core-flow.js | 三类创建、文字要求必填、SKU 输入、壁纸 8 张/文字 2 张、单图返工仅目标 v2、归档成品回归 PASS |
| upload-flow.js | 实际 PNG 上传一次失败后重试、移除及同文件重选、损坏图片解码、空文件、超 10 MiB、SVG 拒绝、第 21 张拦截；提交失败保留输入/素材并重试 PASS |
| template-flow.js | 模板必填、前后排序并保存、保存失败保留、编辑 v1→v2、使用深链接、删除取消与确认、无 Skill 草稿/文字阻断、列表失败重试 PASS |
| pagination-flow.js | UI 建 13 模板，12+1 分页、名称排序、第二页搜索重置、跨页模板深链接、创建页 4 条分页与搜索 PASS |
| api-flow.js | 原生 multipart 文件接收、模板/Skill/SKU/文件引用参数、上传中不可提交、删除后迟到响应不复活、连续双击仅 POST 1 次、202 后工作区 503 仍保留 taskId、读取重试不重复写、任务轮询/离页停止、断连无模拟回退 PASS，pageerror=0 |
| response-flow.js | 畸形 JSON、禁用身份、重新连接恢复、真实空态无示例按钮、商品文字导航 PASS，pageerror=0 |
| visual-flow.js | 1440/1280 主页面和 1280 模板编辑无横向溢出，pageerror=0；实际截图对照既有 Art 原型 |

以上浏览器命令统一为 `npx --yes --package @playwright/cli playwright-cli -s=hx-phase2 run-code --filename scripts/phase2/<文件> --raw`，均返回 PASS、exit 0。复跑前提、文件生成和会话关闭见 `scripts/phase2/README.md`。

## 修复及验证闭环

1. 初次审查发现任务只有模板 ID/版本，没有旧版有序图片。补服务生成的完整 `templateSnapshot`，测试编辑及删除后旧任务快照仍等于旧模板，服务返回副本隔离。
2. 上传选择控件完成后清内部列表并重建原生 input，支持移除后直接重新选择同一文件；浏览器真实文件回归验证。
3. API 故障测试发现工作区读取失败卸载表单后会丢失受理跳转。改为按提交时路由判断是否跳转，允许读取错误后继续进入受理任务；用户主动离页不强制跳回。用 202→503 故障和双击断言复验。

## 视觉证据

本机截图在 `output/playwright/`：phase2-wallpaper-1440.png、phase2-wallpaper-1280.png、phase2-editor-1280.png、phase2-templates.png、phase2-upload.png。原型基准 prototype-wallpaper.png。截图不纳入源码仓库；保留本机供本次验收查看。

## 范围与边界

前端遵循已确认的 JPG/PNG/WebP、10 MiB/张、20 张/组、任务名称必填、SKU 可选、文字自然语言输入。模板/Skill 目录默认策略仍按文档待确认项模拟，不增加 Skill 安装或管理权限实现。当前所有生成均标注为示例。刷新会清空本次模拟输入；生产持久化、权限鉴权与真实执行按后续 Phase 实现。

复用依赖的历史审计项沿用 Phase 1 记录，未借本轮 UI 验证声称具备生产发布安全结论。未新增运行时依赖，未修改原 prototype/source。
