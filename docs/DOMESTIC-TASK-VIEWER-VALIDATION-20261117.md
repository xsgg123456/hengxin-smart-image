# 任务中心只读浏览优化验证记录

2026-11-17，用户授权优化、中文Git提交和国内前端部署。范围为任务中心只读会话的展开与统一图片查看，不变更后端、数据库、依赖或写权限。版本0.2.77。

## 实现与验证

- ManagedTaskWorkspace保存展开状态，同任务切换会话仍保持；同步状态/刷新、会话列表、只读提示可见，加载或404期间仍可退出展开。SessionDetail/消息列表不因展开退出重挂载。
- 管理图片复用StudioAssetImage和useImageViewer，分别以每轮附件/结果和抽屉当前标签组查看；工作台原有文件名、进度、左右切换、缩放拖动、原图下载及Esc行为保持。管理资源适配仅调用原有readManagedAsset GET，不把管理URL交给个人文件HEAD/缓存；每次读取校验权限，不引入后端接口。
- 两个新增单元用例验证管理GET参数、逐次读取、组切换/关闭/卸载回收、403错误和重试、会话更新关闭、迟到响应及跨作用域URL拒绝。全量599项前端测试通过，vue-tsc无错误，国内生产Vite构建通过。日志：output/task-viewer-{unit,typecheck,build}.log。
- 管理正式Vue/Element应用在隔离Chromium里使用拦截的测试API，16组浏览器检查、112个只读业务请求通过。覆盖1920/1000/390布局、展开不重载、同任务切会话、120px阅读位置保持、三图组导航、滚轮缩放/拖动/原图下载、附件Enter/Space、抽屉层级及Esc、503重试、预览403清除；回归五业务隐藏/恢复重验、同步、404、迟到响应及真实401。此处切页为生命周期事件驱动，不是实际OS标签切换验收。
- 国内生产构建产物经本地预览服务3042/domestic运行同套16组管理浏览器回归也通过，111个只读业务请求；证据output/task-viewer-built-browser.log及output/playwright/task-viewer-build/report.json。
- 正常工作台单独浏览器回归通过：默认图片缓存与原图路径、两图键盘导航、下载ZIP内容字节一致、失败重试、切会话取消、桌面与窄屏。旧studio-download脚本混杂的过期平台选择表单超时，与本次图片修改无关；未修改旧脚本，新studio-viewer-regression脚本限定图片回归并使用当前task-assignees测试接口。
- 实际打开截图对照：管理viewer-expanded-desktop/390、viewer-image-390，与正常工作台desktop及normal-image-viewer。卡片使用既有128px结果/80px附件尺寸，查看器复用同一组件；展开工具栏与只读提示在窄屏可达，消息独立滚动，没有横向溢出。截图位于output/playwright/task-viewer和studio-viewer-regression。

依赖未变更；pnpm audit --prod报告critical=0，既有high=39、moderate=35、low=5，不代表无已知依赖告警。生产包审计、发布与正式入口核验另记部署记录，未执行的步骤不计通过。
