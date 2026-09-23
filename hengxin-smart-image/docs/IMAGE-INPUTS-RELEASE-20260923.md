# 前端图片整改与API多图修正生产发布

用户已授权提交Git并打包部署到既有 https://zhitu.qhhengxin.top/ 。前端功能提交ab7de22，API多图修正b5d8398；发布增量版本0.2.4。未要求推送Git。

## 发布计划和完成标准

1. 复核已审功能快照，构建0.2.4生产前端并审计依赖及白名单产物。后端/迁移/正式静态文件和发布脚本随包，排除Demo图片、凭据、运行数据、测试数据库。
2. 在生产构建新后端镜像，用无网络临时容器检查安装产物及专项测试，镜像ID固定后才允许切换。停止接纳并证明API和CLI队列、进程及数据库在途为空；未知/忙碌不强停。备份DB dump并校验目录、旧前端/manifest和两份原生CLI源码。
3. 迁移0016→0017，切换API、API专用worker/outbox、CLI outbox镜像；原生CLI仅同步prompts.py与新增image_revision_prompt.py（提示词输出保持）。验证native队列/心跳、API池5与专用队列、健康；保留模型/并发/7200秒、Skill和凭据。
4. 前端保留旧哈希资源，最后切换首页与manifest，恢复访问。独立核对包及安装哈希、0017、健康200、匿名鉴权401、线上登录页无脚本错误。无现成登录态不绕过认证、不创建付费生图任务。

## 预检事实

2026-09-23实际读取生产racknerd-058889d：0016；CLI job_records为30成功/12失败/2取消；8笔API任务及67图全部成功；channel未暂停。API和CLI outbox为cli-two-hour-20260923，API专用worker/outbox为three-fixes-20260923；相关旧manifest落后于实际容器，发布脚本按两个实际overlay合成并比对运行image/environment/command，不使用旧manifest推断回滚配置。原生worker PID1294761。

0.2.4生产构建含类型检查成功，Vite30.21秒。生产依赖审计critical0、high33、moderate30、low1；本轮无依赖升级，不声称零风险。完整功能验证161单测及浏览器证据见 ../../docs/IMAGE-INPUTS-VALIDATION-20260923.md；此前后端完整1071通过、64条件跳过及真实PG迁移/快照证据见 ../../docs/API-REVISION-MULTIREF-VALIDATION-20260923.md。

## 回退边界

发生错误先停止HTTP接纳和派发，排空后恢复旧镜像/旧前端/旧native文件。保留数据库0017及新增业务数据，不降级、不覆盖DB、不删除快照。迁移后失败默认保持HTTP维护关闭和API通道暂停，人工核实后再恢复；排空失败不强停。备份目录必须新建，不覆盖旧备份。回退流程仅静态检查，不在生产主动注入故障。

## 发布状态

待实际部署后补充发布编号、包哈希、镜像ID、备份、安装验证与线上验收结果；上述计划不是发布成功声明。
