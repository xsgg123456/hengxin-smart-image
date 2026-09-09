# 恒信智能图像 · HTML 交互原型

本目录是已交付的页面和交互原型，作为正式开发的源码与视觉基础；尚未实现真实后端。当前 PRD 新增的四角色权限、钉钉登录及管理中心尚未在原型体现，不代表需求缺失，按根目录 DEV-PLAN.md 后续实现。

- `html/index.html`：静态 HTML 入口及配套 assets、samples。
- `source/`：制作原型时使用的 art-design-pro 源码副本，保留 MIT 许可；与正式业务代码隔离。
- 原始 `D:/Work_Project/art-design-pro` 未修改。

## 预览

无需启动前端开发环境。仓库根目录运行：

```powershell
python -m http.server 3007 --bind 127.0.0.1 --directory prototype/html
```

打开 http://localhost:3007/#/image-processing/wallpaper 。资源使用 HTTP 路径，需要上述静态预览服务，不能直接双击文件打开。

预览路线：图片处理 → 替换壁纸 → 使用示例素材 → 提交生成任务 → 结果详情 → 单张/整套修改 → 下载示例 → 归档 → 成品库。
展开“图片处理”一级菜单可选择替换壁纸、替换商品和替换文字三个二级菜单；侧栏另有任务中心、模板库和成品库。

生成和登录身份为演示；图片是代码绘制的 SVG 示例，未调用真实 Skill。上传文件只在本地浏览器处理，原型数据保存在此地址的浏览器本地存储。

## 底板与组件来源

直接复用 ArtSidebarMenu、ArtHeaderBar、ArtWorkTab、ArtPageContent、ArtTable 与 Element Plus 的 Card、Form、Upload、Dialog、Drawer 等组件。
侧栏、内容布局、表格组件与参考项目同源；没有另造后台框架。

框架组件使用方式参考 [Element Plus 官方文档](https://element-plus.org/zh-CN/component/upload)；静态 HTML 由已有 [Vite 构建流程](https://vite.dev/guide/build) 输出。
