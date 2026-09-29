# API尺寸与PNG生产发布 · 2026-09-29

## 发布结果

2026-09-29 19:21（Asia/Shanghai）生产切换完成。前端0.2.13、schema0021，功能提交c60a0de，发布提交bf7dabd；Git本地提交，未推送远端。

- 发布标识api-size-20260929-bf7dabd，归档795文件/4911561字节；SHA256为6bd1676e0d144d53aa558266545923db54486db847c6af13cf5cf6c4c498ac9b。白名单隐私扫描、归档字节回读、本地/服务器SHA及解包成员逐项校验全部通过。
- 发布增量独立Stage 1/2 PASS，批准快照2f4d2aba7f628759509374272a2bc58f3bd20cb8b12239ac099055db6ebd9bb2；14项发布/回退测试通过，前端生产构建31.18秒退出0。依赖审计critical0/high33/moderate30/low1，既有依赖告警未在本轮升级。
- 实际新镜像在服务器使用--init、断网、无生产挂载执行安装测试：1307 passed / 77 skipped / 1 deselected / 15 warnings，171.11秒。条件跳过及仓库源码对照排除不计为通过；完整工作区测试见开发验收记录。
- API和原生CLI排空完成；数据库dump503079字节、pg_restore列表可读，备份COMPLETE存在。迁移0020→0021成功；原生51包兼容检查通过，原生Worker就绪；API Worker首次启动探测未找到节点，按既有策略重试后正常，并发5。
- 五个后端服务镜像ID均为sha256:c1c7d6c186c0c96aa07fd722d35726f64b8c6855e545d7f30055c8a4b77c5976，各304个后端文件哈希匹配；原生app159文件、前端486文件匹配。12层原Compose链保留、追加本轮overlay，环境和命令保持。
- ready成功，PostgreSQL/Redis/MinIO均up；原生active，API暂停解除，容量准入仍关闭。六个容器自本次启动以来日志无Traceback/ImportError/ModuleNotFoundError/CRITICAL。CLI成功52/失败12/取消2、API成品116，发布前后数量一致。
- 公网首页和入口JS/CSS均200且哈希匹配；登录态auth/me、CLI列表/旧详情、API列表/旧详情、Skill目录均200。读取旧任务617646f4-3008-4fae-abd3-c43937c3c48b首图：原图790×1166、旧成品1024×1024，DTO宽高与实际下载解码一致。历史图片未改写。
- 真实公网登录态浏览器确认对照宽高及尺寸不一致提示、新建页“按原图尺寸 · PNG”，无pageerror；临时会话撤销后401。未创建付费生图任务，本轮线上验证不代表再次验证上游按请求尺寸出图。

服务器发布目录/opt/hengxin-releases/api-size-20260929-bf7dabd，备份目录/opt/hengxin-backups/api-size-20260929-bf7dabd。后续Compose操作必须保留API labels中的完整链，末层为本次目录下api-override.yaml。API_RELEASE.json、API_IMAGE_RELEASE.json、FRONTEND_RELEASE.json、API_SIZE_RELEASE.json已更新；旧TEXT_RELEASE.json保留历史记录。

本地证据output/release/api-size-20260929-bf7dabd/：package-audit.json、build-install.log、installation-tests.log、deployment.log、verification.json、auth-smoke.json、runtime-check.json、browser-verification.json及production截图。SSH短暂断连发生在部分独立连接建立阶段；部署使用服务器独立进程，退出码0，未因此中断或重复执行。

用户已授权提交Git、打包和部署生产。功能提交c60a0de。目标前端0.2.13，数据库0021。

生产只读基线：racknerd-058889d，前端0.2.12，schema0020，五个后端容器镜像text-edit-20260928-0ebb3bc，原生CLI active，ready全部up。CLI成功52/失败12/取消2；API任务14、成功成品116；无在途任务，API未暂停，容量准入关闭。完整12层Compose来自运行API的labels。

发布顺序：已审功能提交→版本和固定发布脚本审查提交→白名单包及隐私审计→实际镜像断网测试→关闭接纳/排空→可读数据库dump及源码/入口/配置备份→迁移→同步服务和前端→恢复接纳→线上接口、页面及哈希验证。

回退：新入口开放前失败恢复旧源码、镜像、静态入口和配置，保留新增nullable schema，不用dump覆盖业务数据。排空状态不明则保持关闭接纳、不强停未知Worker；入口开放后失败保持新代码并关闭接纳，避免在新任务状态未核实前盲目回退。旧镜像、旧静态哈希资源保留。

开发验收见API-SIZE-20260929-VALIDATION.md；发布安装、审查和线上证据将在本记录追加。不把旧图片离线缩放或模拟模型测试当作本轮收费生图效果验证。
