# 正式入口样式丢失修复

用户生产截图显示登录Logo异常放大、海外侧栏与内容纵向错位。前次仅依据接口和可访问文本判断视觉验收通过不成立，撤回该视觉验收结论。

## 规划和标准

1. 对比生产DOM、加载的CSS和压缩入口：确认丢失的组件样式及原因。
2. 修复动态入口构建链，保留现有设计和鉴权；正式构建必须为身份与国内分支分别加载其CSS依赖。
3. 对实际压缩产物执行分支回归，再以浏览器检查登录、业务入口、海外布局和成员页，覆盖桌面及窄屏。
4. 独立两阶段审查通过后提交；仅发布前端修复，保留备份，生产重新检查截图及CSS加载。

## 已定位证据

生产DOM含IdentityPortal作用域data-v-3616a667，但stylesheet仅prototype、el-divider、dingtalk-login和domestic-main；IdentityPortal、BusinessEntry及OverseasShell样式未加载。

0.2.22压缩入口把两个动态import合并进一个预加载调用，其依赖表只保留国内分支。身份JS加载成功但其CSS依赖没有被请求，导致登录Logo和海外布局一起失效。开发服务器注入样式不经过此压缩链，不能代替正式产物验收。

修复采用禁用Terser条件分支折叠（conditionals:false），避免两个Vite预加载占位调用被合并；不升级依赖。选项含义参考 https://terser.org/docs/options/ 。修复有效性以构建后入口及浏览器为准。

## 验证结果

- 正式构建38.20s通过，类型检查通过，前端282项通过。日志`output/overseas-css-hotfix-{build,typecheck,tests}.log`。
- `node tests/built-entry-css.mjs`执行实际压缩入口的预加载逻辑：6种路由通过，身份5种入口均加载40个CSS，国内分支4个。相同测试运行0.2.22归档提取产物立即失败：`missing IdentityPortal CSS`，确认可拦截原缺陷。
- 浏览器使用正式dist静态服务，3015匿名、3016本地管理员fixture，明确不冒充真实身份联调；桌面登录Logo280px、表单440px，无横向溢出。登录、业务选择、海外首页、成员目录以及390px窄屏登录/海外均已目视检查，截图`output/css-hotfix-{login,business,overseas,members,login-mobile,overseas-mobile}.jpg`。
- 静态验收服务初始使用Python默认监听队列，并行资源请求曾失败；调大监听队列后重新载入通过，没有将该失败轮次算通过。
- 复用前端发布脚本`frontend-static.py`，只更新版本前置与本次发布名称；备份、旧资源保留、入口原子替换及异常回退不变。4项发布测试通过。
- 独立审查候选`55ae6380d4d5645d1b7ac21612719a580ad8b10fda888703350a13464b061915`；生产结果待追加。
