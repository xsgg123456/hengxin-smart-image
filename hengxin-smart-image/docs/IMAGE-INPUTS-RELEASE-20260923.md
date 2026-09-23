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

2026-09-23 21:11（北京时间）生产切换成功，脚本返回0。发布编号 `inputs-20260923-b2841c7`，代码提交 `b2841c7`，前端版本0.2.4。部署完成后补写本文档的提交不改变发布代码。

包内622个文件，压缩包4,808,482字节，SHA-256 `5d54c8be64179a7ecf363153526e5a64cf14a31ee034d5a2027103ee4d5f6f5a`。包位于仓库 `output/inputs-20260923-b2841c7/release.tar.gz`，服务器发布目录 `/opt/hengxin-releases/inputs-20260923-b2841c7`。

镜像 `hengxin-smart-image-backend:inputs-20260923-b2841c7`，已安装镜像ID `sha256:2f3fe00e3f86bf467b6941983f3aca8f8a494d4d16de09c1629b69c1ec7ca8cb`。断网临时容器运行API、单张修正提示词、任务排空专项测试：153 passed、12 skipped（未接独立PG测试库），23.01秒。测试使用安装镜像，无生产凭据和数据挂载。

实际执行及独立验收：

- API与原生CLI先取消消费、检查active/reserved/scheduled及数据库，均为空后停止。数据库dump经 `pg_restore --list` 校验，旧前端、manifest、实际镜像清单、native源码保存在 `/opt/hengxin-backups/inputs-20260923-b2841c7`，备份保留。
- 迁移0016→0017成功，`api_image_items.revision_snapshot` 存在。API channel恢复未暂停；原44个CLI任务状态30成功/12失败/2取消，8个API任务成功，未产生测试业务任务。
- API健康，两个outbox和API worker运行；API worker队列 `api_image_edits`、池5；原生CLI service active、队列 `celery`、ping响应pong。CLI超时7200秒、并发5、版本0.156.1保留。
- 安装后逐文件哈希核对：前端461文件，四个后端服务各152文件，原生CLI2文件，全部匹配发布manifest；四个release manifest均指向本次发布。
- 公网 https://zhitu.qhhengxin.top/ 浏览器加载成功，首页哈希匹配、无脚本异常、无JS/CSS加载失败；健康接口200，匿名auth/me及API换套图tasks接口401。
- 本地证据：`output/image-inputs-20260923/deploy.log`、`installation-tests.log`、`production-browser.json`、`production-login.png`。服务器同发布目录保留构建、安装测试与部署日志。

首次尝试在停止服务前被镜像ID校验阻断：重复Docker build的attestation导致image index变化。已提交修复，deploy阶段直接复用已测试镜像；独立审查见 `../../docs/IMAGE-INPUTS-IMMUTABLE-IMAGE-REVIEW-20260923.md`。旧失败尝试未迁移、未停服务。此前打包路径/沙箱固定路径误报也经独立审查修复，未放宽实际凭据和开发者路径扫描。

线上验收使用匿名浏览器，未绕过登录、未在生产新增付费生图任务。登录后的拖拽/粘贴/原图对照/弹窗交互已在同一正式构建的隔离浏览器测试中验证；本次生产不宣称已重新执行登录后业务全流程。

维护使用基础三个Compose文件，并按顺序叠加 `three-fixes-20260923/api-override.yaml`、`cli-two-hour-20260923/api-override.yaml`、`inputs-20260923-b2841c7/api-override.yaml`（均在 `/opt/hengxin-releases/` 下）。最新容器源码位于本发布src/backend，原生CLI仍位于 `/opt/hengxin-smart-image/backend`，只同步本次两份提示词文件。
