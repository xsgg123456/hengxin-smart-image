# Phase 6 验收复跑

从仓库根目录执行`python hengxin-smart-image/infra/verify_phase6.py`。前置：Docker、Python3.12、Node、Chrome，以及frontend锁定依赖；先按infra/.env.example配置本地环境并构建api镜像。

脚本使用独立Compose项目、随机端口/凭据、新卷和独立Playwright会话，临时Vite通过代理连接该测试API。结束关闭会话/进程并删除测试卷，不写开发库。浏览器脚本只由此入口调用，不能指向用户数据环境跑上传测试。日志/截图在output/playwright。

覆盖真实文件、身份、重启、存储失败、浏览器三入口、20张边界，以及JPEG尾部附加字节的原图下载。队列回归单独运行infra/verify_phase5.py。每张10MiB由后端校验；每组20张在当前前端校验，Phase7/8业务提交再校验整个组。

本地产品预览：后端.env显式ENABLE_DEV_IDENTITY=true，`docker compose --env-file hengxin-smart-image/infra/.env -f hengxin-smart-image/infra/compose.yaml up -d api worker outbox`；前端目录`pnpm dev:api`。现阶段可上传预览下载；模板、Skill、生成未接入时仍明确显示不可用，不回退模拟。
