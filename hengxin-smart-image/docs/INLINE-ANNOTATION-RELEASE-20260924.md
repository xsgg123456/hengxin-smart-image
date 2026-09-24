# 单画布标注生产发布 · 2026-09-24

用户授权提交Git并打包部署既有生产站点 https://zhitu.qhhengxin.top/ 。功能提交 `f4e7bc6`；前端版本0.2.5。API和Codex CLI共享原尺寸成品标注界面，框选、画笔、拖动、编号意见、提交预览与冻结重试；后端同步标注定位提示词。无数据库迁移，保持0017。

## 发布计划和验收标准

1. 核对已审功能，提交发布增量，构建生产前端、白名单打包、隐私扫描和依赖审计。
2. 沿用完整生产Compose链（three-fixes、cli-two-hour、inputs-20260923-b2841c7），逐项比对运行配置。构建新镜像并从安装镜像执行隔离测试，固定镜像ID后才切换。
3. 再次确认任务为空、停止接纳和派发、排空API/CLI；备份数据库、前端、manifest和原生CLI源码。仅替换本项目API/两个outbox/API worker、原生CLI两份提示词文件以及前端；不改凭据、模型、Skill、并发和7200秒时限。
4. 安装哈希、镜像ID、0017、API池5/CLI队列与心跳、健康和公开登录页通过后交付。不新增收费任务；匿名在线验证不等同于已验证真实生成效果。

## 预检

生产镜像均为 `inputs-20260923-b2841c7`，HTTP健康，原生CLI active。CLI任务30成功/12失败/2取消；API任务8成功；通道未暂停，schema0017。部署前会重新核查。

0.2.5前端类型检查通过，生产构建30.53秒。生产依赖审计critical0、high33、moderate30、low1；本次无依赖变更，已有告警未声称解决。发布脚本通过bash语法检查和Python编译。原始记录位于 `output/annotation-release-20260924/`。

## 回退

保持接纳关闭并重新排空，恢复旧镜像、前端与native源码及manifest，保留数据库和全部业务数据。没有迁移，不做数据库降级或恢复dump，不强停状态不明的生成进程。备份使用新目录，保留旧静态资源便于已打开的页面继续读取。

发布审查发现原回退忽略恢复错误，已加固为所有恢复步骤成功、旧服务配置匹配、API/CLI队列及健康验证通过后才开放；任一错误重新关闭入口和派发并保持暂停。以隔离Shell桩运行实际recover函数的11种成功/失败场景均通过（未对生产注入故障），日志 `output/annotation-release-20260924/recovery-tests.log`。

## 发布状态

2026-09-24 10:48:58（北京时间）部署完成，脚本返回0；随后安装和公网验收通过。发布 `annotation-20260924-6b43b3c`，发布代码提交 `6b43b3c`、功能提交 `f4e7bc6`，前端0.2.5。后续记录提交不改变发布产物。

包包含631个文件，4,833,584字节；SHA-256 `06172542ee3e6c6985868daa6d860d1103acb4fb58b624a5ee67c4d66da94fb4`。本地 `output/annotation-20260924-6b43b3c/release.tar.gz`；服务器 `/opt/hengxin-releases/annotation-20260924-6b43b3c`。

安装镜像 `hengxin-smart-image-backend:annotation-20260924-6b43b3c`，固定ID `sha256:258396c0bd577d9400bbf02f49111183cf6ed011444327cdc016ae6dab6b60ef`。无网络、无生产凭据和数据挂载的安装镜像专项测试187 passed、3 warnings，26.05秒；覆盖API单张冻结快照/执行/版本、CLI单张输入/材料/提示词以及Worker排空。

实际执行及验收：

- 停止HTTP接纳与派发，API/CLI取消消费并证明active/reserved/scheduled及数据库在途为空后停止。没有中断在途生图。
- 数据库dump经pg_restore目录校验；旧前端、manifest、实际镜像清单和native源码备份到 `/opt/hengxin-backups/annotation-20260924-6b43b3c`，备份保留。
- 前端470个文件、四个后端服务各152个文件、原生CLI两份提示词源码，逐文件SHA256均匹配发布manifest。四份release manifest指向新发布；API healthy，其余服务running，native active。
- API Worker池5、专用队列验证通过；native CLI队列与ping通过。CLI0.156.1、超时7200秒、并发5保持。
- schema0017与revision_snapshot列保持，API通道恢复未暂停。原44笔CLI任务状态30成功/12失败/2取消、8笔API任务成功，没有新增测试业务任务。
- 公网 https://zhitu.qhhengxin.top/ 登录页正常，首页哈希匹配，无脚本异常或JS/CSS失败；health/ready返回200，匿名auth/me与API换套图tasks均401。

本地证据位于 `output/annotation-release-20260924/`，包括发布/安装测试/验证日志、`production-browser.json`及登录页截图。服务器同发布目录保留原始构建、测试、部署日志。SSH曾短暂中断，均先只读确认未启动再重试，实际切换只执行一次。

在线验收未绕过登录，也未创建收费生成任务；登录后标注交互、原尺寸导出和重试一致性依据此前隔离真实页面测试，不宣称本次已在线验证真实生成效果。

今后维护须使用基础三个Compose文件，依次叠加 `/opt/hengxin-releases/` 下 `three-fixes-20260923/api-override.yaml`、`cli-two-hour-20260923/api-override.yaml`、`inputs-20260923-b2841c7/api-override.yaml`、`annotation-20260924-6b43b3c/api-override.yaml`。native源码仍在 `/opt/hengxin-smart-image/backend`。
