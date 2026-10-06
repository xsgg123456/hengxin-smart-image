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
