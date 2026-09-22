# 已有结果收取阻塞修复

生产证据：任务aa2e9004-8ab6-4e89-a2d8-6bee02894110，第2张collecting、有result_url、无lease_token，收图重试0；第11张uncertain；通道paused=false；Worker active为空。前端显示保存结果中，但claim在发现任何uncertain后直接返回，未启动收图。

计划与验收：
1. 回归复现失败项手动重试＋另一张uncertain，确认旧代码无法收图。
2. 在claim中仅为已返回结果的collecting开放独立收取，保留paused和10并发限制、租约、next_attempt_at；无结果的collecting不得转成生成绕过阻塞。验收真实execute_next不调用生图客户端、下载失败按1/2/4秒退避、成功结果入版本。
3. 相关API测试、独立两阶段审查后发布后端修复，核查原卡住图片收图结果；不自动确认第11张旧请求、不代用户发起额外生成。生产发布沿用既有隔离API overlay，保留CLI及前端。

验证：旧代码首项复现execute_next=False；修复后定向28项通过，新增全局10租约上限后4项新用例通过。整个API模块pytest -k api_image：65 passed、8 skipped（独立PostgreSQL未配置）、919 deselected；compileall成功。日志output/api-collection-tests.log。
