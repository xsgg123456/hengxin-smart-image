# 海外会话热修复独立审查（首轮）

- candidateId：`23952fa87aab0f0b0c2be01962663a8a50da0d91c7cf397e3a8f0ecd1e2b5a57`
- 结论：**Stage 1 FAIL；Stage 2 未执行**。
- 范围：本次 Product-Spec.md:965–971 会话及成员界面修订；IdentityPortal.vue、identity/revalidate.ts、OverseasMembers.vue、management-adapter.ts、新增重验测试，以及前端版本与静态发布脚本差异。不是全项目历史功能重新验收。
- 方法：读取 code-review skill；逐条阅读源规格、差异、身份 API、业务组件和实际安装的 Element Plus 源码；核对构建与测试原始日志。未修改产品代码，未提交或登记批准。

## Stage 1：逐项符合性

以下路径除特殊注明外，相对 `hengxin-smart-image/frontend/`；行号针对送审候选。

| 规格 | 结果与证据 |
| --- | --- |
| 成员列表、编辑弹窗不展示部门，搜索提示仅姓名 | 完整实现。`src/views/overseas/admin/OverseasMembers.vue:5,9,24,96` 删除列与表单字段，提示与只读说明一致。 |
| 无部门输入或必填校验，保留兼容字段 | 完整实现。`src/views/overseas/admin/OverseasMembers.vue:47` 仍保留兼容属性；`src/views/overseas/admin/management-adapter.ts:40–52` 移除非空限制；没有数据库迁移。 |
| 切回窗口重新检查，同一有效身份保留页面及草稿 | 代码实现符合。`src/views/auth/IdentityPortal.vue:2–3,52–55,118–121` 保留业务子树、按成员 ID key，仅更新 member；`src/views/overseas/OverseasPortal.vue:43,50` 和 `OverseasTasksPage.vue:113` 依赖能力字符串而非新对象引用。同 ID 同权限响应不会因此重新挂载或触发加载。真实 UI 持久性验证由主 Agent 进行中，不能用纯函数测试替代。 |
| 并发 focus / visibility 合并 | 完整实现。`src/api/identity/revalidate.ts:21–25` 复用 running Promise；`tests/identity-revalidate.test.ts:8–23` 对并发调用及请求数做断言。 |
| 核验期间阻止操作 | **未完整实现，HIGH H1**。仅根容器 inert，body 下浮层仍可操作，详见下文。 |
| 失效、撤权、服务错误拒绝访问 | 重验失败路径实现。`src/api/identity/revalidate.ts:32–35` reject；`src/views/auth/IdentityPortal.vue:45–49` 清 member；`src/api/identity/auth.ts:12,29` 只接受 active 成员；`tests/identity-revalidate.test.ts:24–31` 覆盖 401/403/503。浮层清理有 H1 关联缺口。 |
| 换号销毁旧页面，切换/退出后旧异步结果不得恢复 | 代码实现符合。`src/views/auth/IdentityPortal.vue:2,105–108,124` key 和 invalidate；`src/api/identity/revalidate.ts:15–18,28–35` 代次检查；`tests/identity-revalidate.test.ts:33–48` 覆盖失效晚返回与不同 ID。尚缺真正挂载组件的换号断言，测试仅证明回调值。 |
| 张帅五角色、八能力，其他账号矩阵不变 | **待独立验证运行证据**。主 Agent 提供已执行正式 patch_member 并审计的说明，`docs/OVERSEAS-SESSION-HOTFIX-20261013.md:9` 亦有记录；本候选未改全局权限矩阵。此次没有收到可独立核对的生产响应或审计原始证据，不能以说明作为生产授权成功的 PASS。 |

## HIGH H1：核验封锁遗漏 teleport 浮层

规格原文（`Product-Spec.md:969`）：**“核验期间阻止操作”**。

候选 `src/views/auth/IdentityPortal.vue:2` 只在包住 OverseasPortal 的 div 设置 `:inert="checking"`。以下实际业务 UI 不在此 DOM 子树中：

- `src/views/overseas/OverseasPictureAnnotation.vue:7,73–81` 明确 `append-to-body`，仍可输入与提交修改；其 disabled 条件没有 checking。
- `src/views/overseas/OverseasMaterialPreview.vue:2` 明确 `append-to-body`。
- `src/views/overseas/admin/OverseasMembers.vue:79–82` 禁用确认使用 ElMessageBox，确认后检查 active 并继续 adapter.save，不检查重验等待。
- `src/views/overseas/OverseasExecution.vue:54–57` 停止执行确认后，alive/epoch/canCancel 未因重验开始变化，仍可调用 api.cancel。
- 实际依赖 `node_modules/element-plus/es/components/message-box/src/messageBox.mjs:9` 默认挂载 document.body；`node_modules/element-plus/es/components/tooltip/src/content.mjs:24–26` 默认 teleported=true；`node_modules/element-plus/es/components/dialog/src/dialog2.mjs:76–78` 将 append-to-body 对话框移出根容器。

可达路径：先打开确认或标注浮层 → 切出再切回窗口 → 身份请求仍在等待 → 点击浮层确认/提交。页面自身未卸载，浮层不继承根 div 的 inert，业务请求可以开始。这里不声称后端一定接受越权请求；问题是核验完成前的操作门禁不满足明确安全交互合同。

另：候选 `OverseasMembers.vue:98` 卸载仅设置 active=false 和 generation，未关闭独立创建的 MessageBox。身份失败后待确认界面可残留；active 检查能阻止后续 save，但不能清除此浮层。

官方语义核对：[MDN inert](https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement/inert) 说明 inert 作用于元素与后代；[Element Plus MessageBox 源码](https://github.com/element-plus/element-plus/blob/dev/packages/components/message-box/src/messageBox.ts) 确认默认挂载 body。上述结论以本地实际安装源码为直接依据。

修复验收应覆盖所有业务浮层的交互阻止，并在真实 DOM 挂载测试或浏览器中验证：请求悬挂期间点击、键盘确认不执行；同一身份完成后草稿保持且恢复交互；失败/换号清旧浮层。单独检查 pending 布尔值不能证明这一要求。

## 编译与测试证据

读取主 Agent 提供的候选日志；本 reviewer 没有重复执行全量构建，未把它描述为独立重跑。

`output/overseas-session-hotfix-build.log` 原始摘录：

```text
> hengxin-smart-image-frontend@0.2.24 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ built in 36.21s
```

`output/overseas-session-hotfix-tests.log` 原始摘录：

```text
ℹ tests 288
ℹ suites 0
ℹ pass 288
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 7653.3632
```

这些结果证明记录中的命令通过，不能覆盖浮层行为。`tests/identity-revalidate.test.ts:9–23` 的 draft 是测试自建普通对象，组件根本未挂载，所以其保持不变断言不证明实际 Vue 表单状态持久性。

## Stage 2

**未执行**：Stage 1 存在 HIGH 问题，按 skill 停止。未签发代码质量、安全扫描、邻居页面视觉对比或两阶段 PASS。

## 快照变化

审查开始 review-status 的 currentId 与 candidateId 一致。提出 H1 后主 Agent 已修改代码并启动构建；结束前只读 review-status 返回：

```text
44d1b470534429a7fa634a49f5b40a2191866f825dee04f8eabfc31c3906c453
```

变化包含 IdentityPortal.vue、OverseasMembers.vue 及生成声明 components.d.ts。主 Agent 说明新增 body.inert 与禁用确认清理。这些修复**不属于本报告所审候选**；必须重新 review-prepare、由新审查核对再决定结论，不得用本报告批准新快照。
