# 海外工作台下载与表单调整验收 · 2026-11-02

## 范围及实现
沿用现有图片勾选，归档按钮旁增加所选原图ZIP下载。复用海外鉴权原图缓存及既有buildZip/imageExtension/safeFilename，原始字节直接入ZIP，不重新编码、不归档。切换任务/会话卸载下载组件时取消，失败不保存残缺ZIP。
提交/修改图需去任务名称示例，平台顺序调整，品牌三选项且初始空值；旧品牌和旧平台作为兼容选项保留。
先更新Product-Spec及CHANGELOG，再实施，最后回归。DEV-PLAN及Design-Brief无改动；此次轻量布局继承原页面；用户后续已授权提交 Git、发布 0.2.56 并线上验证四项功能，不改生产数据。

## 本次验证
- `pnpm test`：428项通过，0失败/跳过。原始输出：`output/studio-download-tests.log`。
- `pnpm run build`：内含`vue-tsc --noEmit`，类型和Vite正式构建通过（48.36s）。原始输出：`output/studio-download-build.log`。
- `node tests/studio-download.browser.mjs`：退出0，PASS。原始输出：`output/studio-download-browser.log`。本地3032正式Vue/Element页面、隔离浏览器上下文、受控API，不访问生产。测试进程已关闭。
- 专项单测覆盖部分/全选ZIP原始字节、同名不覆盖、鉴权原图地址、空选、异常地址、403失败、取消、按钮忙碌防重复、失败重试、卸载不保存、新旧表单值兼容。
- 浏览器覆盖部分/全选真实下载和解包逐字节校验、503失败不产残缺包、重试、请求未完成时切会话不保存、1366桌面/390窄屏按钮及裁切祖先边界、新建平台/品牌下拉和任务名称无placeholder。

## 可复核产物与边界
`output/playwright/studio-download/desktop.png`、`mobile.png`、`form.png`及`partial.zip`、`full.zip`。
桌面与窄屏截图在故障重试之后拍摄，仍显示既有工作台error横幅；重试成功下载已由计数与字节校验确认。窄屏使用现有顶部任务素材开关收起侧栏后验收下载按钮。浏览器只使用隔离模拟接口，未调用模型、未线上实测；后端和数据库无改动。
独立审查及最终快照凭据由主Agent登记，本文件不代替审批。
