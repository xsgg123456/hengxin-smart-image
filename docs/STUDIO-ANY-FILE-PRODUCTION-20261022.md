# 海外任意格式附件0.2.48生产发布

用户已授权中文Git提交、打包并部署生产。功能审查及本地验证见 [开发验收](STUDIO-ANY-FILE-20261022.md)。

## 发布步骤与完成标准

1. 核对当前0.2.47、海外0020、国内0032、无在途任务、API与原生服务实际基线；准备0.2.48无迁移入口，保留现有Skill状态与账号绑定。
2. 构建前端，审计依赖和真实发布文件；发布脚本测试、独立两阶段审查通过后中文Git提交，构建不可变发布包并验证摘要。
3. 服务器实际镜像验证源码摘要、安装包测试及500 MB容量；准备原生目标目录；关闭海外接纳并稳定排空，备份数据库并隔离恢复核对行指纹；不调用迁移、不重置数据。
4. 切换海外API/worker/outbox、前端，验证健康、版本、原数据、Skill账号绑定和国内/身份/代理保持；正式页面核对文案/上传选择器，验证任意格式上传和原件下载。记录测试材料及清理方式，不触发收费生图。

## 发布前实查

- FRONTEND_RELEASE与OVERSEAS_RELEASE均为 `overseas-20261022-5c3715f`，版本0.2.47；海外`overseas_0020`，国内`0032`。
- 海外API镜像 `sha256:ed7bafd1e6c0008fb89d7f19ef23e24546f5bcf2819b34de1b7aebb39924935c`，健康、3 GiB限制、unless-stopped。任务状态为4个succeeded；切换时仍重新排空。
- 海外worker/outbox指向该海外发布；国内worker/deletions/retention指向 `domestic-retention-20261021-bec8dd7`；共享认证代理使用既有专用目录。发布入口必须核对实际基线，原生进程及会话保护沿用。

## 结果

发布准备：前端0.2.48正式构建通过（31.77秒）；依赖审计0 critical，7 low / 51 moderate / 72 high，与既有依赖基线相同，本次未修改依赖。新发布入口专项62 passed、24 subtests passed，联合回归141 passed、48 subtests passed，Python编译与差异检查通过。独立发布审查两阶段PASS，候选 `b706bcb51b6d4b1515457a1b904a3b4dfd3e89177d59f6b736b0459c5bf75cee`，见 [报告](reviews/STUDIO-ANY-FILE-RELEASE-20261022.md)。

- 代码提交：`6897b6e64be772e4957bc53bb6c27f427db9b62a`；发布 `overseas-20261022-6897b6e`，前端0.2.48。
- 真实发布包1269文件（含manifest），5,529,472 bytes；隐私与包成员摘要核对PASS。SHA-256：`325bbf571f5996f14f3b7e308145a9274cb2c30bff8c71ebc5b968ca4edb0f08`。
- 上传连接中断后只读确认包摘要正确、尚无src目录，再单独解包并核对1268文件；未重复不明状态的写操作。部署启动连接中断后确认systemd unit不存在，才重新启动。
- 实际Linux镜像560后端文件摘要PASS；安装测试2109 passed、178 skipped、1 deselected、6 warnings（514.76秒），0失败。延续既有安装测试边界：6个本地CLI环境模块不在镜像中运行、1个需要前端源码的contract用例排除。3 GiB内存下500 MB容量专项4 passed（7.24秒）。
- 实际镜像：`sha256:f208b2cfc9fecaaf1c429a0d0ec4a5768105ab4a932cb9637ffcf61b654124f7`。
- 发布PHASE=complete，无FAILURE、无MIGRATION_STARTED；备份 `/opt/hengxin-backups/overseas-20261022-6897b6e`，隔离恢复及精确行摘要验证通过，原海外行和数据库结构保持一致。
- `ANY_FILE_PRESERVATION_VERIFIED`确认现有owner、schema和任意Skill开关状态保持；国内0032、海外overseas_0020。
- 海外worker/outbox均指向本次release/backend，PID388215/388216。国内worker/deletions/retention PID136757/174666/174667与发布前相同；认证代理PID3991624相同。正式站首页、国内与海外ready均HTTP200。
- 浏览器首次加载动态模块失败，服务器逐个核对index及identity-main资源HTTP200且摘要匹配；重新加载后页面正常，原有17份素材和历史消息保留，草稿为空。普通/展开工作台实际截图目视核对通过，新文案“支持任意格式文件”、file input accept=null、多选属性保留；下拉列表仍只有两个指定OUTON Skill。截图在 `output/any-file-release-20261022/production.png`、`expanded.png`。
- 浏览器真实上传验收受扩展权限限制：fileChooser.setFiles返回需开启“Allow access to file URLs”；未修改浏览器权限。两份无业务内容的ZIP/未知后缀测试文件未实际上传，未发送模型任务，线上仍17份素材，无测试数据待清理。生产浏览器上传→刷新→下载完整链路本次未验证，不能声称通过。该链路的接口和原件字节保真已在正式Linux镜像自动测试中通过；前端选择/拖拽/粘贴/草稿恢复已在本地独立浏览器测试通过。
