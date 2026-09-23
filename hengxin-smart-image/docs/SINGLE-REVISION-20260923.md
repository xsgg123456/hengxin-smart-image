# CLI 单张成品修改简化 · 2026-09-23

## 实现

有成品的单张修改采用统一提示词：成品路径、原参考素材、可选问题位置截图（禁止复制标注）、可选 JSON 引用的修改意见、其他不变且交付1张。取消首轮 Skill 调用、原底图及整套换图要求。壁纸用手机屏幕参考素材，商品用商品参考素材，文字不附素材段。

材料准备跳过原底图对象读取和 Skill ZIP/本地文件加载。只读冻结基础版本；旧轮次未冻结时兼容原当前版本。沙箱按轮隐藏 Skill 发现目录，原 HOME 和 session 文件保留，执行器仍用原 session_id resume。无成品的失败图重试继续原生成分支；整套、首轮和结果收取逻辑保留。

## 验证

- 最终后端 `python -m pytest -q`：865 passed、166 skipped、15 项既有 warning。跳过项依赖平台或外部服务，不计为通过。
- `python -m compileall -q app/execution`：退出码0。
- 针对性回归88 passed、1 skipped：四个 Skill 的单张提示词、可选圈注/意见、历史成品字节、同会话续接、原底图和 ZIP/本地 Skill 损坏不阻塞成品修改、首轮/失败重试兼容、沙箱挂载参数。
- 生产服务器临时目录以 codex 用户执行真实 Bubblewrap 验证：`SINGLE_REVISION_SANDBOX_PASS`。本轮 .agents 下原 Skill 不可见、/work/skills 不存在，成品和会话文件可访问；退出后原发现目录文件仍保留。
- 不调用付费图片生成；以上证明材料、提示词、会话编排与文件隔离，不声明图片视觉效果验收。
- 独立审查发现文字模式原 sources 也是底图；已修正该模式单张成品修改的 inputs 为空，并新增多原图损坏仍可修改成品的回归，材料与单张提示词20项通过，再执行上述最终全量回归。

## 发布范围

仅原生 Codex Worker 的 app/execution/prompts.py、materials.py、workspace.py。生产文件先校验旧SHA256，备份后暂停消费并检查active/reserved/scheduled为空，再停止服务、更换文件、编译和启动。异常恢复全部三个文件。API/UI/数据库无需更新。

## 生产结果

2026-09-23 已完成空闲切换。备份 `/var/backups/hengxin-single-revision-20260923T040908Z` 保留三个原文件。生产三个新文件字节与已审本地文件一致；实际导入生产模块验证四个Skill单张提示词完全相同，删除skillPath仍成功。最新心跳ready，CLI0.156.1，Worker PID735209，celery消费队列恢复。

SHA256：prompts.py=`2dececa1bfc8f7b2d040c2a90b7376ca4c547ba5eb519a0b5493271f51b1c520`；materials.py=`a8fcab7664bc362f6ebbdf9911277669877ac99ef0f44994b13c9914d0807525`；workspace.py=`162eb66297fd95b1c893317bd8543735cc8a87485654671201f92c98cc266def`。

回退需先暂停消费并确认空闲，再恢复备份三个文件、编译并重启专用Worker。独立审查报告 SINGLE-REVISION-20260923-REVIEW.md 两阶段PASS；本轮未提交Git，未创建实际收费生图任务。
