# 上传容量与设计人选验证（2026-10-14）

范围：Product-Spec.md末节；本地实施，不提交、不部署。500 MB按500,000,000字节。普通附件100个、生成图片引用100张，后端schema不变。

- `pnpm test`：360通过，0失败（output/upload-limits-frontend-tests.log）。
- `pnpm build`：vue-tsc成功，Vite构建34.03秒（output/upload-limits-build.log）。
- `.venv/Scripts/python.exe -m pytest tests/test_overseas_upload_limits.py tests/test_overseas_studio.py tests/test_overseas_materials.py -q`：28通过。包含真实500 MB数据校验与有/无Content-Length的500 MB multipart分段流及请求体超限（output/upload-limits-boundaries.log）。
- 浏览器：upload-limits、material-time、overseas-tasks-faults、overseas-materials-faults、studio-native 五组通过；全部隔离context、接口拦截，无生产写入或模型调用。截图output/playwright/upload-limits/与output/material-time-upload.png。覆盖101项先拦截/100项上传发送/移除后续传、姓名/无搜索框、分页/空态/权限故障、取消上传、移动端。
- 后端Windows全回归：2152通过、314跳过、8失败；8项均为Linux safe-open或Windows符号链接权限。Linux隔离容器全回归：2280通过、188跳过、8失败（output/upload-limits-backend-linux.log），Windows失败项已在Linux通过。Linux的8项失败全部来自phase11a进程监督测试：pytest作为容器PID1触发supervisor的parent==1保护。加`docker run --init`原样重跑两文件，26通过、1跳过（output/upload-limits-linux-supervisor.log），8项失败全部消除；未为此改业务代码。不把宿主专用/外部依赖跳过项宣称验证。
- 补充：真实sessionStorage中101项pending恢复为可编辑草稿，保留原文/Skill/可访问引用，移除后可发送；单测覆盖。390px浏览器等待菜单动画结束、关闭遮罩并收起素材后，断言提示/上传/发送的实际可视矩形，并在移动端移除、重新上传、发送100项；截图已更新。

上传代理：仓库现有nginx模板没有海外路由（当前海外生产路由由发布时的运行配置保存）。新增infra/nginx.overseas-upload.inc为可复用的location内指令，后续发布须将其内容合入每一层实际海外/api/overseas/v1/代理location，不能修改国内10/11MiB限制。最大请求体500065536字节，容纳文件与64KiB multipart包络；分段转发，保留既有鉴权/上游/安全头，nginx -t后reload。本轮未连接或修改生产代理，因此不声称线上500MB已生效。

资料自动文字解析仍限制20MiB、2MiB输出和15秒，上传超过解析资源上限保留原件、明确下载查看。工作台原有格式/Office解压与图片像素校验保留；500MB是传输大小上限，不是取消格式保护或模型上下文上限。
