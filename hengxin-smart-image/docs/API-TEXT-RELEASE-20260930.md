# API文案功能生产发布 · 2026-09-30

## 发布结果

2026-09-30 10:35（Asia/Shanghai）生产切换完成：前端0.2.14、schema0022；功能835e3af，发布fc3dbbd。本地Git已提交，未推送远端。

- 发布标识api-text-20260930-fc3dbbd；804文件/4924610字节，SHA256 820c634db30779e7456b4c03475a3e8dd6bed6c88d75021f5ac304f0d0a7e099。归档隐私扫描、字节回读、本地/服务器SHA和逐成员哈希通过，两份内置提示词资源齐全。
- 发布增量修复后独立Stage1/2 PASS，候选df867252aef8c9ce63b017833bbad073954e02840472f764f9dd625649e9becd。22项发布测试及24子测试通过。首次失败报告单独保留。全量历史发布测试中硬编码旧annotation overlay的一项失败未改，未算成本轮通过。
- 实际服务器新镜像断网、无生产挂载、带init安装回归：1313 passed / 78 skipped / 1 deselected / 15 warnings，165.38秒。条件跳过及源码对照排除不算通过；开发独立数据库专项139通过见功能验收记录。
- 关闭接纳排空后备份成功，database.dump 529985字节且pg_restore列表校验通过，COMPLETE存在。0021→0022迁移成功，kind为nullable varchar(20)；native依赖51包兼容、Worker就绪。
- 五个后端服务均匹配已测试镜像及310个后端文件，原生app162文件（含提示词）、前端488文件（含package）逐项哈希通过；原13层Compose链保留并追加本轮overlay，既有环境/命令未漂移。
- ready全部up，native active，API暂停解除，capacity gate仍关闭。六服务自启动日志无Traceback/ImportError/ModuleNotFoundError/CRITICAL。API Worker启动探测首次未发现节点、按既有重试后就绪并发5，部署退出0。
- 历史CLI成功52/失败12/取消2，API成功143，发布前后数量一致。旧任务读取及原图790×1166/旧成品1024×1024的DTO与实际文件解码一致；历史成品不改写。
- 公网首页、入口JS/CSS均200且哈希匹配；真实登录态auth、CLI列表与详情、API列表与详情、Skill目录均200。旧版本kind兼容为generation。真实公网浏览器确认修复文案按钮、纯文字修改完整内置提示词预览、创建默认完整原文，pageerror为空。浏览器阻断全部非GET/HEAD/OPTIONS请求，未提交付费生成；临时验收会话已撤销并确认401。

生产发布目录：/opt/hengxin-releases/api-text-20260930-fc3dbbd；备份：/opt/hengxin-backups/api-text-20260930-fc3dbbd。有效API_RELEASE/API_IMAGE_RELEASE/FRONTEND_RELEASE/API_TEXT_RELEASE清单一致，历史API_SIZE_RELEASE保留。后续Compose操作必须包含运行labels的完整链及本轮api-override.yaml。

本地证据output/release/api-text-20260930-fc3dbbd/：package-audit.json、dependency-audit.json、frontend-build.log、release-tests.log、build.log、installation-tests.log、deploy.log、verification.json、auth-smoke.json、runtime-check.json、browser-verification.json及线上截图。真实模型清晰度/杂色修复效果本次未新增收费验证。

用户已授权提交Git、打包部署。功能提交835e3af；目标前端0.2.14、schema0022。

只读线上基线：schema0021，前端0.2.13，镜像api-size-20260929-bf7dabd；CLI成功52/失败12/取消2，API成功143；无在途，API未暂停、capacity gate关闭；PostgreSQL/Redis/MinIO ready，native active。

策略：固定本轮发布基线，保留完整Compose叠加链；安装包显式包含text_edit_prompt.txt与text_repair_prompt.txt，同步原生app资源。构建及镜像安装验收后才切换；关闭入口排空、数据库及源码/入口/配置备份、迁移0021→0022、上线验证。失败时恢复旧代码/入口，新增可空字段保留，不覆盖业务数据库；排空未知或开放后失败保持入口关闭并保留执行现场。

未新增收费生图，线上验收读取历史任务及打开新交互，不提交生成任务。

发布准备：功能已提交835e3af；0.2.14生产构建32.57秒exit0，依赖审计critical0/high33/moderate30/low1（既有依赖未更新）。初轮发布测试20通过；独立审查识别verify主路径断言问题，发布前修复并补验，不将原测试通过视作完整验收。
