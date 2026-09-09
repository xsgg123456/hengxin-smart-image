# Phase 1 验收记录

日期：2026-09-09。范围：正式前端工程承接、接口契约、集中模拟与真实模式隔离。Phase 2–14 未开始。

## 执行结果

| 项目 | 证据 | 结果 |
|---|---|---|
| 独立依赖安装 | `npx --yes pnpm@10.33.4 install --frozen-lockfile`：772 packages，Done in 1m18.1s；node_modules 普通目录，无 junction；锁文件 SHA256 与原型一致 | 通过 |
| 类型检查 | `npx --yes pnpm@10.33.4 build` 首步 `vue-tsc --noEmit`，退出码 0 | 通过 |
| 服务测试 | `npx --yes pnpm@10.33.4 test`：tests 7、pass 7、fail 0 | 通过 |
| 生产构建 | `vite v7.1.7 building for production`，3252 modules transformed，built in 28.65s | 通过 |
| 代码审查 | 见 PHASE1-REVIEW.md；HTTP 成功响应结构与模式文案缺陷已修复 | Stage 1 PASS / Stage 2 PASS |
| 创建与返工 | 浏览器校验空输入、创建、单张返工第二张 v2、其余 7 张 v1、归档后成品可查 | 通过 |
| 模板与空态 | 名称/图片校验、模拟保存、搜索无匹配提示 | 通过 |
| 真实模式失败 | 未启动后端时连接与重试均阻断工作区，不返回模拟数据 | 通过 |
| 响应/身份恢复 | 畸形 JSON 结构错误、禁用身份阻断、重新连接恢复、真实空工作区无示例按钮 | 通过 |
| 写后读失败 | HTTP 202 后 GET 503，保留受理 taskId、POST 仅 1 次、重新读取不重复写 | 通过 |
| 轮询 | 任务页轮询，离开任务页停止 | 通过 |
| 视觉/导航 | 原型和正式 1440px 对照；1280px 无横向溢出；三种独立处理页可访问 | 通过 |

服务测试原始输出：`frontend/phase1-test.log`；构建原始输出：`frontend/phase1-build.log`（本机日志不纳入版本控制）。服务测试使用独立内存实例，无用户数据库。浏览器使用独立 hx-phase1 Playwright 会话；API 故障采用浏览器拦截，未启动或修改后端。

## 浏览器回归复跑

根目录启动前端3008 mock服务，以及临时3018真实模式服务（均仅127.0.0.1）。命令：前端目录 `pnpm dev`，另一个终端 `pnpm exec vite --mode development --port 3018`。需要 Chrome 和 Playwright CLI。

在根目录使用 `npx --yes --package @playwright/cli playwright-cli -s=hx-phase1 open http://127.0.0.1:3008 --browser chrome` 创建独立会话；再按顺序执行：

```powershell
npx --yes --package @playwright/cli playwright-cli -s=hx-phase1 run-code --filename scripts/phase1/core-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase1 run-code --filename scripts/phase1/template-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase1 run-code --filename scripts/phase1/api-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase1 run-code --filename scripts/phase1/response-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase1 run-code --filename scripts/phase1/accepted-flow.js --raw
```

模板脚本会只读打开原型3007作视觉对照。截图输出到根目录 `output/playwright/`。accepted-flow 需要该目录下 1×1 PNG 测试素材 pixel.png，见脚本目录 README。截图已人工查看：frontend-wallpaper.png、prototype-wallpaper.png、api-disconnected.png。API 503/500 故障测试有预期网络错误，页面异常监听为 0。

模拟预览构建 `npx --yes pnpm@10.33.4 build:preview`：built in 30.44s。生产 JS 扫描模拟身份与种子任务标识：0 命中。最终复审报告已确认 Stage 1/2 均 PASS。

## 已知边界与后续工作

- 原型保持原状；正式业务维护源为 frontend。模拟数据只在内存，不声称 AC-009 后台持久化已完成。模拟生成与文件下载为示例，未接真实 Skill、存储或钉钉。
- 继承锁文件的 `pnpm audit --prod --json` 返回 76 条依赖告警：critical 1、high 40、moderate 34、low 1。原始审计保留在 `output/playwright/phase1-audit.json`。涉及 xlsx、axios、Vite、tar、lodash、PostCSS 等直接及传递依赖；数量不是已证实的业务可利用漏洞数，尚未逐项做可达性分析。
- 此阶段保留原组件和锁定版本；依赖升级、逐项可达性核查与回归为上线前整改项。当前结果仅表示本地 Phase 1 功能验证通过，不表示可安全发布。
- 分页、完整失败场景、全部业务/管理页面、真实文件引用分别按 Phase 2–4 与后端阶段完善，契约中的过渡接口不能当作生产最终设计。
