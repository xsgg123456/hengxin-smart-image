# API单张修改多图参照 · 验证记录

## 实现范围

新修正按当前成品、原始底图、共用素材、可选标注的顺序提交3/4图。公共提示词与CLI壁纸路径共用，CLI golden四组输出逐字保持。受理时冻结fileIds、最终prompt与policyVersion；NULL历史快照继续旧1/2图协议。文件状态、hash及解码失败在调用上游前终止，失败保留旧版本；恢复历史后重新冻结新修改输入。UI沿用原弹框，补充自动参照说明。

## 本次执行证据

| 检查 | 命令/方式与结果 |
|---|---|
| CLI与公共提示词 | `.venv/Scripts/python.exe -m pytest tests/test_image_revision_prompt.py tests/test_single_revision_prompt.py tests/test_task_prompt.py -q`：56 passed |
| API全部与PostgreSQL | 本地专用临时PG，`python -m pytest tests -k api_image -q`：104 passed，1031 deselected，无skip；各fixture使用独立schema |
| Linux完整后端 | 临时容器运行`python -m pytest -q`：1071 passed，64 skipped，15 warnings，121.75秒。跳过项属于未配置的其他专用集成/环境条件，不计通过 |
| 后端编译 | 同Linux容器`python -m compileall -q app migrations`：退出0 |
| 完整数据库迁移 | 专用空库`alembic upgrade head` → `downgrade 0016` → `upgrade head` → `current`：退出0，0017(head)；已有snapshot拒降由SQLite/PG用例验证 |
| 前端 | `npm.cmd run test`：153 passed，0 failed；`npm.cmd run build`含vue-tsc检查，成功，Vite31.37秒 |
| 浏览器功能 | Playwright、临时SQLite/内存文件存储、模拟relay，正式HTTP：新文案可见、1440/1280截图、意见保留、标注上传、断响应后同键重放、只新增目标1版、邻图不变、恢复历史保留版本、ZIP下载、轮询保留滚动，pageErrors=[] |

Linux首次隔离回归漏复制infra/compose配置，导致29项环境管理fixture初始化错误；补齐非敏感配置后完整重跑通过。前端首次sandbox运行Node用户信息读取失败，正常权限下重跑153项通过。两次失败均不作为验收证据。

日志与截图位于Git忽略目录 `output/api-revision-implementation-20260923/`：backend-linux-final.log、real-evidence.json、real-revision-1440.png、real-revision-1280.png、real-history-1280.png。独立审查报告为 `docs/API-REVISION-MULTIREF-REVIEW-20260923.md`。

## 实际中转能力及边界

本次开发前按用户授权独立实测：同一中转/模型，三图HTTP200、54.81秒；四图HTTP200、167.65秒，均下载并解码成功。实际返回1254×1254 PNG，虽请求size=1024x1024；不承诺返回尺寸、不自动缩放。原证据为 `output/api-multiref-20260923/results/evidence.json`。该实测使用示意图和独立请求，不冒充本轮正式业务链路的视觉效果验收。

本轮实现验证未再调用收费上游；未部署生产，未提交Git。上线需要0017迁移和API/Worker代码同步，已有快照不能通过降级迁移丢弃；部署时需按既有规则排空旧Worker，避免旧代码领取新协议任务。
