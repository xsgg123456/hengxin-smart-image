# API换套图处理动效

复用CLI GenerationPlaceholder的光晕流动与图标呼吸，新增可选自定义文案/静态/紧凑模式，默认调用保持原CLI外观。ApiResultPicture接入正式RealTaskDetail：running/collecting动效，queued/retry_wait/带nextAttemptAt收图等待为静态，failed/uncertain无动效，成功直接显示图片。修改时旧结果保留可点击，底部提示层pointer-events:none。

验证：vue-tsc --noEmit通过；前端153测试通过。真实Vue组件＋Element Plus的隔离浏览器验证9种状态、动态到成功切换、旧结果预览、prefers-reduced-motion，以及1280/760宽度文字裁切检查，MOTION_BROWSER_PASS，无pageerror。沿用离屏及后台暂停。截图与日志output/api-motion/。测试入口已移除，不进入发布包；该验证是组件浏览器联调，不冒充生产登录态。

发布计划：独立审查后仅白名单打包frontend/dist（排除demo-images）与package.json；备份线上前端，复制新哈希资源后原子替换index.html，保留旧资源供已打开页面使用。核对静态哈希、公网首页、API健康及后端/CLI进程标识不变。不重启后端、不改OSS配置、不执行生图。

最终补验：motion通过withDefaults设为true，避免Vue可选Boolean默认false改变原CLI。浏览器default.cjs/default.json证明默认生成流动、默认排队呼吸、显式关闭静态，CLI_DEFAULT_MOTION_PASS。最终生产构建28.54秒。版本0.2.3。
