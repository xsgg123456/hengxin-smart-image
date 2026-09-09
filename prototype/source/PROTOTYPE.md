# 恒信智能图像交互原型

基于本机 art-design-pro 源码副本，保留 MIT LICENSE。原布局、导航、主题、Pinia 与 Element Plus 直接复用。

启动：`npm run dev`，打开 http://localhost:3007/#/wallpaper/index 。
构建：`npm run build:prototype`，生成 dist/index.html 与静态资源；需要 HTTP 静态服务器预览。

当前 node_modules 是指向参考项目依赖的本机目录联接，不进入 Git。在其他电脑请先按 pnpm-lock.yaml 安装依赖，并将 .env.example 复制为 .env。

这是独立本地演示：用户身份是 fixture，任务模拟执行，SVG 是示例商品图，未连接真实 CLI、Skill 或生产认证。不能作为已完成生产系统部署。
