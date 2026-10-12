# 二期海外前端本地验证

范围：docs/OVERSEAS-FRONTEND-20261012.md。本轮是真实 Vue 前端源码、本地模拟运行；未接钉钉、AI、海外后端或数据库，不宣称后端隔离验收。

## 直接复用

- LoginLeftView、AuthTopBar：沿用一期登录左右布局、品牌、插画、主题控件。
- ArtSidebarMenu、ArtHeaderBar、ArtPageContent、ArtWorkTab、ArtGlobalSearch：沿用现有应用框架；页头账号插槽保留国内默认行为，海外单独退出。全局搜索卸载时解绑原事件，防止业务切换重复订阅。
- ArtTable、ElUpload、ElImage、AnnotationCanvas：表格、资料选择、图片查看和单画布复用。PicturePreview 含国内身份重验，因此海外复用其底层 ElImage，不引入国内业务回调。
- 独立 Pinia 不安装持久化插件；预览启动不执行一期 bootstrap/身份生命周期/真实守卫；locale 在独立构建下不读取国内用户存储。正式后端隔离仍是后续独立交付。

## 实测

浏览器脚本使用 Playwright 新建临时 context，关闭后释放，不访问生产。

1. `node tests/overseas-preview.browser.mjs`：5 组通过，页面异常 `[]`，业务 API 请求 `[]`。覆盖未登录/无权直链、拒绝授权、四种权限状态、必填与重复SKU、单份资料、多SKU、故障重试、设计审批、方案返工、一期画布框选、单图返工和其他图片审核状态保留、全部SKU通过归档、成品筛选、跨页查看、退出。
2. `node tests/overseas-shell.browser.mjs`：4 组通过，页面异常 `[]`。覆盖原侧栏、空态、无资料阻止、非法文件类型、仅竞品文件上传、删除确认、全局搜索挂载与业务切换、国内入口进入一期原有预览页面，以及海外和一期卡片实际计算样式一致。
3. 390、760、1440 视口检查无页面横向溢出；760px 标注弹窗页脚在视口内，内容单独滚动。存储读取监测未读取国内 user/worktab/hengxin/iframe 键。
4. 同尺寸视觉证据位于 `output/playwright/overseas-20261012/`：02-business-entry、03-create、05-annotation、06-annotation-narrow、08-archive、09-mobile、10-entry-mobile、11-domestic-baseline。

## 构建与测试

审查发现独立入口缺少一期 `data-box-mode` 初始化，导致卡片圆角不一致。已复用现有设置处理器，基于独立内存设置初始化盒子模式；补充国内/海外实际计算样式一致性验收并通过，不读取国内设置存储。

执行 `pnpm test`、`pnpm run build`、`pnpm run build:overseas`，245 项测试通过，两个构建均通过。日志为 output/overseas-unit.log、overseas-production-build.log、overseas-build.log。build 脚本均先执行 vue-tsc --noEmit，具体最终结果在审查报告核对。

## 使用

`pnpm dev:overseas` 启动 http://127.0.0.1:3012/overseas-preview.html。点击钉钉登录模拟授权后选择业务；海外顶部可切换运营/设计体验角色。使用“填入示例”走完整工作流。生产构建不改变一期认证流程；独立预览使用 demo 模式且不代理 API。没有提交、推送或部署。
