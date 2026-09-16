# 恒鑫智图品牌接入验证 · 2026-09-14

## 本次交付

按照用户已确认概念图制作红色 H 与橙色菱形的矢量资源，使用思源黑体 Medium 收整文字。交付目录 `../branding/`；`恒鑫智图-品牌资源.zip` 包含资源、预览及生成源码，不包含测试日志。

正式前端已更新共享 ArtLogo、系统名称、登录页完整横版、启动标题、页头工作区名称、浏览器标题及 SVG/ICO/触屏图标。原有蓝色主题和业务逻辑不变。

## 命令及结果

运行目录：`hengxin-smart-image/frontend`。因机器上的 pnpm 包装器尝试自动安装时失败，本次直接调用仓库中已安装的相同工具入口，没有新增前端依赖或改动锁文件。

| 命令 | 当次结果 |
| --- | --- |
| `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit` | 退出 0，零诊断 |
| `node node_modules/tsx/dist/cli.mjs --test tests/*.test.ts` | 79 项通过，0 失败，0 跳过 |
| `node node_modules/vite/bin/vite.js build` | 退出 0，`✓ built in 28.29s`，无 warning/error 匹配 |

日志分别为 `../branding/typecheck-validation.log`、`test-validation.log` 和 `build-validation.log`（本地验证日志，不进入素材 ZIP）。最终构建在登录页改用既有 `dark:hidden` / `dark:block` 主题工具类、消除两条 CSS 优化警告后执行；这次修复仅改变展示类和 CSS，既有业务测试结果保持适用。

## 界面与资源检查

CUA 浏览器实际检查，不提交真实生图任务：

- 独立模拟预览 `http://127.0.0.1:3018/`：浅色展开侧栏显示彩色 H 和「恒鑫智图」，路由标题为「替换壁纸 - 恒鑫智图」。
- 同一模拟端口：折叠侧栏仍有 36 × 36px 标识；切至深色模式后仅 `.brand-white` 可见，彩色版隐藏。修复了最初 scoped CSS 全局选择器未匹配的问题，并重新检查。
- `http://127.0.0.1:3018/auth/login?auth=denied`：登录错误提示和按钮仍正常；完整横版加载成功，实际尺寸约 280 × 98.234375px，页面无横向溢出。最终工具类复查：浅色仅彩色版 display:block，深色仅反白版 display:block，另一版本为 display:none，两张素材均加载成功。
- 资源预览 `http://127.0.0.1:4189/preview.html`：查看浅底/反白横版、浅深应用图标及 16/24/32/48/64px 图标；H 主轮廓可辨识，较小版本去除折面。
- 用户当前开发服务 `http://127.0.0.1:3008/`：只读打开并看到彩色标识、侧栏「恒鑫智图」、页头「恒鑫智图工作区」及「替换壁纸 - 恒鑫智图」浏览器标题；原有模板列表加载正常。没有提交任务或改变该服务的运行配置。
- XML 检查：10 个 SVG 无 `<text>` 字体依赖、无嵌入位图 `<image>`；PNG alpha 包含 0 与 255，独立标识/横版为透明背景；五种小尺寸 PNG 与标称尺寸一致；ICO 包含 16/32/48/256px；ZIP 完整性检查通过且不含日志。

3018 是本次独立模拟验证端口，测试结束已停止该临时进程；不能代表真实钉钉或真实生图能力。本次品牌接入不改变既有 Phase 验收结论；用户已有的 3008 开发服务仍使用原来运行配置，4189 仅供品牌资源预览。未部署生产、未提交 Git。

## 审查

独立两阶段报告见 [BRAND-IDENTITY-REVIEW.md](BRAND-IDENTITY-REVIEW.md)；以该报告和 harness 批准快照为最终代码审查依据。
