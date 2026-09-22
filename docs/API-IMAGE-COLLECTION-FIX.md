# 已有结果收取阻塞修复

生产证据：任务aa2e9004-8ab6-4e89-a2d8-6bee02894110，第2张collecting、有result_url、无lease_token，收图重试0；第11张uncertain；通道paused=false；Worker active为空。前端显示保存结果中，但claim在发现任何uncertain后直接返回，未启动收图。

计划与验收：
1. 回归复现失败项手动重试＋另一张uncertain，确认旧代码无法收图。
2. 在claim中仅为已返回结果的collecting开放独立收取，保留paused和10并发限制、租约、next_attempt_at；无结果的collecting不得转成生成绕过阻塞。验收真实execute_next不调用生图客户端、下载失败按1/2/4秒退避、成功结果入版本。
3. 相关API测试、独立两阶段审查后发布后端修复，核查原卡住图片收图结果；不自动确认第11张旧请求、不代用户发起额外生成。生产发布沿用既有隔离API overlay，保留CLI及前端。

验证：旧代码首项复现execute_next=False；修复后定向28项通过，新增全局10租约上限后4项新用例通过。整个API模块pytest -k api_image：65 passed、8 skipped（独立PostgreSQL未配置）、919 deselected；compileall成功。日志output/api-collection-tests.log。

生产第二根因：调度修复上线后实际执行收图首次＋3次均失败，原上游result_url域名为openservice-prod-1.oss-cn-hangzhou.aliyuncs.com，未列入生产允许域名。使用相同安全下载器仅临时增加此精确域名，验证HTTPS公共IP固定、无重定向、图片校验均通过，下载1,035,581字节、1024×1024。后续修正运行配置仅增加此精确域名，保留原域名；恢复用户此前明确提交的收图重试，不重新调用生图，不改变第11张uncertain。

## 生产验收

- 已部署api-opt-20260922-733faaf，候选36e5f1b449395499b167ac8bdd1f62736aadcaa6351ad465523721d0949ccb86，独立两阶段PASS。镜像/前端哈希校验与公网鉴权检查通过；CLI Worker和CLI Outbox标识未改变。
- 备份/opt/hengxin-backups/api-opt-20260922-733faaf；发布/opt/hengxin-releases/api-opt-20260922-733faaf，deploy.log为DEPLOY_COMPLETE。包SHA256：5c8cfafd09df816464d7524d994197a1ffa9d560d9eab447baee16a57ff5d444。
- 生产.env仅为API_IMAGE_ALLOWED_RESULT_HOSTS增加上述精确OSS主机；旧配置另备份env-before-result-host。HTTPS、公共IP固定、无跳转、大小及图片验证保持启用。三个API服务重建使配置生效，前端和CLI不改业务代码。
- 修正后第2张收图成功：state=succeeded、current_version=1、collection_retries=0；整单成功10张、uncertain1张。ApiAttempt总数仍为11，证明没有额外生图调用。第11张保留uncertain，未代用户确认停止。
- 证据位于output/api-collection-release/verify.log、verify-final.log与配置修复脚本；代码审查报告docs/API-IMAGE-COLLECTION-FIX-REVIEW.md。
