# 海外工作台草稿与批量移除验收 · 2026-10-22

## 范围

用户确认两项一起实施。本轮仅本地开发和隔离验证，不提交、不部署、不操作生产素材。正式要求见 Product-Spec.md 的 2026-10-22 节。

- 输入区已上传/引用附件、文字和Skill保存在同一浏览器localStorage，按用户/任务/对话隔离，刷新/返回恢复。附件只保存真实引用及显示信息，不保存文件二进制；隐藏与去重后的素材不会被误当成附件失效。
- 图片修改的原图引用、已上传标注、意见与已确认标记一并保留，防止只恢复文件却丢失修改关系。未确认编辑弹窗及尚在上传的本地文件不属于已保存的待发草稿。
- 发送及新对话成功清理草稿；失败保留。未知请求沿用sessionStorage冻结的幂等请求，不自动发起新一轮。新对话响应丢失后重新读取已切换会话时，核实成功仍清理原会话草稿。
- 右侧复用多选/全选，增加独立一行危险操作。单次确认，顺序调用现有移除API，全程锁定重复操作，真实成功项移除、未完成项可重试。历史及输入区已引用附件保持。
- 存储不可用/损坏提示，不将草稿当成服务端权限凭据；附件URL和身份格式校验，后端授权仍执行。草稿不跨浏览器或设备同步。

## 实现依据

复用项目现有Vue监听、Element Plus按钮及确认框。保存使用同步监听以覆盖立即刷新；遵循 [Vue Watchers](https://vuejs.org/guide/essentials/watchers) 的刷新时序说明。批量操作沿用 [Element Plus Button](https://element-plus.org/en-US/component/button) 的danger/plain/disabled/loading能力，不新增依赖或后端接口。

## 已执行验证

工作目录 `hengxin-smart-image/frontend`。

| 命令 | 结果与边界 |
| --- | --- |
| `node --import tsx --test tests/*.test.ts` | 341 PASS、0 FAIL；原有332项与新增9项，记录 `output/studio-draft-materials-unit.log` |
| `pnpm typecheck` | 退出0，vue-tsc无类型错误 |
| `pnpm build:overseas` | 退出0，4683模块，最终构建30.11s，包含vue-tsc；记录 `output/studio-draft-materials-build.log` |
| `node tests/studio-draft-materials.browser.mjs` | PASS：上传和整页刷新、文字/Skill/附件恢复、隐藏附件恢复、勾选全选取消、部分失败重试、发送失败保留及成功清空、新对话清空、完成态禁用、桌面/窄屏裁切祖先检查 |
| `node tests/studio-refresh-skills.browser.mjs` | PASS：空闲/活动/完成轮询、手动加载状态、错误恢复、草稿/附件/Skill/滚动位置和完整描述桌面/移动检查 |

浏览器在一次性无痕上下文执行，限定loopback，所有业务API完全拦截，不连接真实数据库或模型。浏览器通过证明前端真实交互与模拟协议，不等于生产验证。后端未改，列表持久化继续复用已有接口。

## 既存测试失败

额外运行 `studio-native.browser.mjs`，在第65行断言Markdown图片数为0、实际1。此时尚未进行草稿编辑或批量操作。

用临时Vite pre-loader将本轮4个已有变更文件全部替换成`git show HEAD:<path>`原文，在独立3038端口运行同一测试，仍在同一行出现相同失败。HTTP验证当前3037模块包含useComposerDraft，HEAD基线3038模块不包含，确认覆盖实际生效。未修改该旧测试或对话渲染实现，不把它计入通过项。

## 视觉与独立审查

正式组件截图在 `output/playwright/studio-draft-materials/`。保留侧栏宽度、样式和蓝色引用按钮，下方增加红色移除按钮；已检查底部操作及空态在桌面1366×900和窄屏390×844的可见边界。

首轮独立审查报告：`docs/reviews/STUDIO-DRAFT-MATERIALS-20261022.md`。其提示残留建议已修正，并新增测试验证失效Skill未修正时继续提示、换有效Skill或重新填写损坏草稿后清除提示。截图等待真实DOM与过渡稳定，避免动画中的状态作为视觉证据。

终审报告：`docs/reviews/STUDIO-DRAFT-MATERIALS-FINAL-20261022.md`。独立fresh reviewer两阶段PASS，9项专项及浏览器复跑通过，前次LOW已验证修复。最终快照`9887aaaa1ac26ab00bc44c0fdd75f542cff7308cb05f63016c6167ab78aa7fff`已通过review-approve登记。临时HEAD基线服务及文件已清理，保留测试脚本、日志与截图。本轮本地交付完成，未提交Git、未部署生产。
