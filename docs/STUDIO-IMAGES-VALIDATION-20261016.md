# 工作台图片预览与标注正式接入

用户已确认最终紧凑预览，并授权正式开发、真实 Codex 发送、Git 提交及生产部署。本轮目标版本 0.2.38。

## 范围与验收

1. 正式工作台待发、已发、成品、素材四区缩略图与分组原图预览；沿用最终预览尺寸和紧凑摘要，保留文档下载、选择与归档。
2. 框选/画笔及编号描述；移除已有标注图上传和整体要求框；确认仅回填输入区，补充后用户主动发送。原图、标注图及说明按 ID 冻结关联，保持旧请求幂等、权限和任务会话。
3. 类型检查、完整前后端回归、真实隔离 HTTP/文件存储及浏览器交互；独立两阶段审查固定快照后提交。
4. 发布包隐私/源文件哈希审计，生产安装镜像测试，关闭海外入口并排空后备份切换，正式入口目视与接口验收。无需数据库迁移。

## 已取得的证据

- 前端：类型检查通过，完整单测 378/378；日志 `output/studio-image-frontend-tests-20261016.log`。覆盖真实上传参数、回填、替换、失败保留、双100边界、未知结果同请求重试与草稿隔离。
- 后端：专项及关联回归 101 passed / 1 skipped（Windows下既有Linux链接边界跳过）。补齐生成图片 HEAD 后预览专项 14/14，涵盖鉴权、元数据检查、缺失文件及GET/HEAD一致性。
- 依赖审计：critical 0、high 70、moderate 48、low 5；与上一版记录相同，本轮无依赖升级。原始审计 `output/studio-images-20261016/dependency-audit.json`。
- 真实生产只读基线：前端0.2.37，前端台账 `domestic-20261015-4c64c1a`；海外台账及worker/outbox为 `overseas-20261015-726ede0`；国内worker/删除服务为 `domestic-20261015-4c64c1a`。数据库实查国内0029、海外overseas_0016。
- 海外native用户 `hengxin-overseas`，国内worker/删除服务用户 `codex`。部署校验两组现有身份及路径，保持国内和统一身份服务不变。

## 验证边界

单测使用受控执行进程边界，无收费模型调用。浏览器及真实 HTTP 验收使用独立本地数据库和MinIO；正式部署、安装测试和生产目视结果在实际完成后补记，当前不作为已完成声明。

## 正式前端与真实接口联调

- 生产构建成功，4739 modules，80秒；`output/studio-images-20261016/frontend-build.log`。
- 真实PG/MinIO/API验收：发送及同key重放、跨任务403、PNG/JPEG/WebP GET/HEAD与默认下载、文档preview422。执行prepare真实写入3份文件，逐一比对MinIO字节哈希与prompt路径；7772字符意见完整保留。证据 `studio-image-edits-result.json`、`studio-image-edits-prompt.txt`。
- CUA真实浏览器：引用6素材→只显示3项/全部弹窗6项；框选和画笔2处，填写逐条意见，确认回填，仍2条消息且原主文字/附件保留。再次编辑后取消，描述仍是上次确认值。
- 主代理实测待发56×56、消息72×72、结果110×110、素材48×48/行68、上传条32、输入区235.5px，无横向溢出。截图 `canvas.png`、`draft.png`。
- 附件预览过滤文档后共4图，JPG3/4右键盘切至WebP4/4；真实发送后消息共6图，标注5/6切原图6/6，下载标注PNG成功，原始尺寸790×790。
- 浏览器主动发送后PG实查：原6附件+标注附件索引6+原图索引7，单条imageEdit绑定正确，框选/画笔两条描述与工作台补充完整；execution_count=0。随后通过UI停止排队任务。证据 `browser-send-evidence.json`、`sent.png`。
- 390×844窄屏：页面scrollWidth390，展开工作台并收起素材后发送按钮bottom784；画布确认按钮bottom816，可见可操作。截图 `mobile.png`、`mobile-canvas.png`。浏览器error日志为空。
- 发布工具完整回归549 passed / 1 skipped / 213 subtests passed，`output/studio-images-release-tests.xml`。
- 首轮Linux全量使用了缺少--init的测试容器，pytest作为PID1触发既有进程监督保护，8项失败；修正为docker-init作为PID1后相关文件26 passed / 1 skipped，未修改业务监督代码。最终全量重跑结果另补。
- 最终Linux全量：**2551 passed / 195 skipped / 0 failed**，325.27秒；`backend-final.log` / `backend-final.xml`。跳过项依赖独立外部服务等环境条件，真实PG/MinIO集成结果单独记录。

## 生产首轮切换及恢复依据

- 业务实现提交106d07d；发布包overseas-20261016-106d07d，SHA256 3d1cac2b4ac099b1630856b46748aeae0a231cfd494920963739e58563c32c76。
- 服务器镜像安装2443 passed / 194 skipped / 1 deselected，容量4 passed。首次SSH断开未切换服务，重连确认无残留构建后以systemd后台任务成功完成。
- 排空两次检查及完整备份成功，新API/native启动，verify-installed误报Domestic native process changed，按失败保护关闭海外入口及API；前端尚未发布。
- 实查国内删除服务PID3925617、实际cwd、文件hash均未变化，NRestarts=0；仅ExecStart展示由start_time真实值/pid3925617变n/a/pid0，发生于daemon-reload。国内业务未被停止。海外jobs/deleting/queue/unacked均0，备份COMPLETE存在。

- 恢复增量测试：新发布/恢复专项83 passed +24 subtests；相关旧upload/attachments/recovery/retention回归83 passed +48 subtests；Python编译通过。主代理另用项目venv重跑专项83+24通过。
