# API单张图片/文字互斥生产发布 · 2026-09-30

用户已授权Git提交、打包和生产部署。目标前端0.2.15，schema保持0022，无迁移。

顺序与验收：
1. 核对已审功能快照并提交；适配发布脚本、版本号与三份提示词资源白名单，发布脚本独立审查通过。
2. 构建正式前端、审计依赖和发布包隐私；只从已提交源码打包，回读及SHA验证；服务器镜像安装测试通过。
3. 只读核对生产基线，关闭接纳并排空后备份；保留完整Compose链，同步容器及native；成功后恢复接纳。排空不明不得强停，切换失败按既有fail-closed策略处理。
4. 核对五服务镜像/资源哈希、native、前端版本、健康与历史任务；公网交互只读冒烟，不提交收费生成。

已核实服务器racknerd-058889d，当前API镜像hengxin-smart-image-backend:api-text-20260930-fc3dbbd，ready依赖全部up。发布结果见下文。

准备证据：功能提交3359989；正式前端0.2.15类型检查/构建退出0；依赖审计critical0/high67/moderate42/low5，现有依赖本次未更新；新发布25测试通过，全发布107通过/1跳过/1旧annotation固定基线断言失败，不计为全绿。线上schema0022、API暂停false/capacity gate false，CLI成功52失败12取消2，API任务成功24、图片成功174，无在途。

## 发布结果

2026-09-30 13:48（Asia/Shanghai）生产切换完成，前端0.2.15/schema0022。功能3359989、发布df0bc8d，本地Git提交，未推送远端。

- 发布api-edit-20260930-df0bc8d；808文件/4936951字节，SHA256 06fc952367e7e2d042cf557b5a80de0a6108d4eac7e7d89c440690d41765b675。源码白名单、三模板资源、产物隐私扫描及归档回读/服务器逐项哈希通过。
- 独立Stage1/2 PASS，candidate c6b38c76fd373fc4a08b9c93a2c7ddeede012474bd1ae935ec44bc7753008de4；新发布25测试通过。服务器新镜像断网、无生产数据挂载安装测试1337 passed/78 skipped/1 deselected/15 warnings，166.52秒。
- 排空和备份完成：database.dump 564989字节，pg_restore目录校验通过，COMPLETE存在。schema0022保持不变，native51依赖兼容。
- 五后端服务匹配已测试镜像和各313文件；native164、frontend489文件逐项哈希通过。Compose原完整14层链保留并追加本轮overlay，环境与命令未漂移。
- ready三依赖up，native active，API暂停解除，capacity gate保持关闭。六容器自启动日志无Traceback/ImportError/ModuleNotFoundError/CRITICAL。API Worker首次探测未就绪、自动重试后READY_POOL_5，部署退出0。
- 旧CLI成功52/失败12/取消2，API成品成功174保持一致；历史任务、旧图片DTO与实际尺寸一致。公网首页、入口JS/CSS200且哈希匹配，匿名auth401，真实登录态auth/任务列表详情/Skill目录200。
- 公网浏览器验证图片/文字模式、空意见、切换草稿隔离、完整专用提示词预览及创建默认提示词精确匹配；pageerror为空。脚本阻断非GET/HEAD/OPTIONS，未生成收费任务；临时会话撤销并确认401。先前验收脚本未等待切换后的原图加载、二次点击关闭details导致失败，修正等待和折叠状态判断后通过，线上代码未修改。

发布目录/opt/hengxin-releases/api-edit-20260930-df0bc8d，备份/opt/hengxin-backups/api-edit-20260930-df0bc8d。后续Compose操作须使用运行labels完整链并包含本轮api-override.yaml。五份有效发布标记一致，历史API_SIZE_RELEASE保留。证据位于output/release/api-edit-20260930-df0bc8d/，含package-audit、installation-tests、deploy、verification、auth-smoke、runtime-check、browser-verification及线上截图。真实模型修改效果未新增收费验收。
