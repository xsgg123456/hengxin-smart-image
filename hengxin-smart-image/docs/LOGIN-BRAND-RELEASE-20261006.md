# 登录品牌文案 0.2.19 发布

用户已授权生产部署和Git提交；打包器要求已提交、已审源码，因此先提交功能及发布参数，再打包安装，最后提交生产验收记录。生产只升级静态前端，沿用现有frontend-static.py备份和失败回退流程，不重启执行服务。

## 发布前验证

- 生产实查：前端0.2.18，frontend-progress-20261006-73347b0，API健康、CLI worker active。
- 登录文案已通过独立审查，见根目录docs/LOGIN-COPY-REVIEW-20261006.md；217项前端测试通过。
- frontend-static.py专用安装/损坏包/同名资源冲突/失败回退4项测试通过。
- pnpm audit --prod：critical 0、high 36、moderate 34、low 1。此次未变更依赖，既有依赖告警仍存在，不声称零漏洞。
- 生产构建日志 output/brand-release-build.log；安装包将由白名单隐私扫描和逐文件SHA256回读校验后部署。

## 验收标准

安装文件哈希匹配、公网标题及三处文案匹配、API readiness正常、容器和CLI Worker启动标识与发布前一致。备份旧入口、package及FRONTEND_RELEASE；保留旧哈希资源。

## 生产验收结果

2026-10-06 北京时间15:47公网验收完成。前端0.2.19，发布frontend-brand-20261006-40f6952，源码提交40f6952；发布增量Stage1/Stage2 PASS，批准快照3408049f8d169b454a72112b2f6ccdb808e80ab98245ccc51dd16d6ff1d932ba。

- 构建成功39.90秒；4项安装回退测试通过；本轮功能217项测试通过。
- 包500文件、4606897字节；最终SHA256 49d8ae9b6c11d137c5358aa00d6b1260e48b5d4cbfce35096007f66d12717040。包白名单隐私审计、服务器归档成员及逐项SHA验证通过。
- 第一次安装在切换前拒绝favicon.svg同路径不同字节。比较确认仅CRLF/LF差异（591/587字节），重打包时保留线上favicon原始字节；未放宽安装保护、未改业务代码。首包及解包目录保留为first-package，未变更生产入口。
- 最终498个前端安装文件哈希一致；公网HTML与包内SHA一致。备份/opt/hengxin-backups/frontend-brand-20261006-40f6952；旧哈希资产保留。
- 公网Playwright独立匿名会话：标题、主标题、副标题精确匹配，企业AI生图横版标识真实加载并截图。证据output/brand-production-login.png。未发起钉钉登录或付费生成。
- readiness为ready，PostgreSQL/Redis/MinIO均up。发布前后9个项目容器ID/镜像/StartedAt及CLI Worker PID/ActiveEnterTimestampMonotonic完全一致，执行端未重启。证据output/brand-runtime-before.json、brand-runtime-after.json。
- 未推送Git远端。依赖告警保留前述边界。
