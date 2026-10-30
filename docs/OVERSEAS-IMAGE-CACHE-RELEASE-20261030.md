# 海外图片缓存与两小时时限生产交付

2026-10-30 已开发、审查、提交、打包并部署到生产。版本 **0.2.55**，源码提交 `0aa591297e73bd96b573108bd6bcdf2153d7d577`；本记录是部署后的补充文档，不改变已发布代码。用户明确授权本次生产部署。

## 交付行为

- 图片列表加载独立缩略图；预览、缩放、标注和原图下载继续使用原件，原件内容与分辨率不变。
- 当前会话整批渐进预取，后台最多两个原件请求，点击优先，共享在途下载。页面缓存以128 MiB/40张为上限，退出或换账号清理，切换会话取消无用队列。
- 重复打开先做轻量权限和版本校验，未改变则复用本地原件；刷新后利用浏览器私有HTTP缓存，304不重传图片正文。授权、删除和版本变化仍正常生效。
- 海外新轮次默认7200秒（2小时），队列可见性7800秒。既有轮次冻结值、国内默认值保持。没有引入Redis图片缓存。

首次未预取完成仍需等待网络下载；超过缓存预算、浏览器清理缓存或图片更新时可能重新下载。预取改善等待体验，不会提高服务器出口带宽。缓存保留的是原图数据，不能保证任何设备、网络下都立即显示。

## 测试与审查

| 检查 | 最终结果及证据 |
| --- | --- |
| 前端单测 | 424通过；`output/image-cache-frontend-tests.log` |
| 类型与生产构建 | 均退出0；`output/image-cache-frontend-typecheck.log`、`output/image-cache/frontend-build-final.log` |
| 真实浏览器集成 | 18项通过，errors为空；实际HTTP而非路由模拟，覆盖原图下载哈希、304零正文、去重/优先级/取消、权限、缓存预算和失败恢复；`output/image-cache/result.json` |
| 后端扩展专项 | 123通过、1跳过；`output/backend-image-cache-targeted-final.txt` |
| Windows后端全量 | 2514通过、405跳过、8失败；7项依赖POSIX安全打开、1项缺Windows符号链接权限。不能将本次全量标记全绿；`output/backend-image-cache-regression-final.txt` |
| 实际Linux安装镜像 | 84通过，无跳过或失败，包含上述8项Windows失败用例及缓存/删除/缩略图/时限回归；`output/image-cache/installed-tests.txt` |
| 发布保护 | 4项测试与Python语法检查通过；安装测试、基线、排空和配置保护接入发布入口 |
| 隐私及依赖 | 制品隐私审计通过；前端audit critical=0，既有low=5、moderate=38、high=39，本轮未变更依赖，未声称无历史漏洞 |

独立审查Stage 1、Stage 2均PASS，无未解决HIGH/MEDIUM，报告见 [审查记录](OVERSEAS-IMAGE-CACHE-REVIEW-20261030.md)。批准快照：`198d3b3534d6378ac954b26d0f0ad486e5bcdacbed0694e18d512af6e73f63af`。该报告中的待发布事项已由下面的实际部署验收补齐。

## 生产验收

正式入口 `https://zhitu.qhhengxin.top/`，任务“C形杂志桌灯测试”，会话“新skills测试3 v2修正”。通过真实Chrome打开列表、原图查看器、关闭重开、下载及刷新，目视检查布局与查看器工具栏，页面错误日志为空。

- `P03_final.png`：列表缩略图384×384；查看器原图1600×1600，3,168,542字节。真实UI下载文件与服务器原件SHA256一致：`c0b08e17f0796d7f4961488e2ef582385e0fbf38f5ae6644c5a6e1c05d7e6551`。
- 缓存后首次观测打开约1406毫秒，关闭再打开约364毫秒。包含自动化操作及DOM观察耗时，是本次观测而非稳定性能承诺。
- 服务器日志证明重复预览只有HEAD 304，没有新增原件GET；刷新后原件GET返回304，复用浏览器已有正文。证据：`output/image-cache/production-p03-requests.json`、`output/image-cache/production-p03-after-refresh.json`。
- 原图下载入口验证正确字节；下载操作仍可能发起GET，不把预览缓存效果等同于下载请求完全去重。
- 匿名条件请求返回401，不绕过权限返回304。国内与海外就绪接口均HTTP 200。
- API实际管理生效值7200，实际worker/outbox进程环境及队列可见性7200/7800；旧轮次冻结3600。任务接纳恢复，未重放旧任务。
- 保留完整Compose链、原生worker工作目录/启动命令、账号授权及Skill配置。国内、身份与账号服务未重启；无数据库迁移或数据恢复。

汇总证据：`output/image-cache/production-final.json`；服务器保存对应`FINAL_VERIFIED.json`，核验时间2026-10-30 10:10:56 UTC。

## 制品与回退

- 发布标识：`image-cache-20261030-0aa5912`。
- 本地安装包：`output/release/image-cache-20261030-0aa5912/release.tar.gz`，680文件，4,932,001字节。
- 包SHA256：`bbf0e8a5b240a4acf60156dafd5d4a99a7738abc25a9e5ae3038392eda2c2840`。
- 服务器发布目录：`/opt/hengxin-releases/image-cache-20261030-0aa5912`。`source`为安装源码；`work`保存安装测试、部署前后状态和私有配置证据，不纳入Git或公共制品。
- `work/RECOVERY.txt`记录API及原生服务恢复步骤；`work/frontend-backup/`保存旧入口、安装清单和静态恢复证据。旧API镜像与两代哈希静态资源保留。回退前同样停止接纳并排空，不恢复数据库、不覆盖凭据或业务数据。

源码已本地Git提交；没有执行远端push。用户原有`AGENTS.md`修改保留，不混入本次提交。
