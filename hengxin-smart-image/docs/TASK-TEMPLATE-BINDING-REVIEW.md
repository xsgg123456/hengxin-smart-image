# 任务模板绑定审查

- candidateId：`97c8dfe0191298b11aeabd9cfaa9e763d786eddd2d5740852ba353b6e4006837`
- 范围：`frontend/src/views/hengxin/components/TaskDetail.vue` 第16、50行新增接入；`frontend/src/views/hengxin/components/TaskTemplate.vue` 全26行。下文路径以 `hengxin-smart-image/` 为基准，Product-Spec.md 以仓库根目录为基准。
- 只读关联证据：Task 类型、后端 queries.py、相邻 TaskSources 卡片；未重审既有全库 dirty 改动。
- 开始及结束前两次 review-status 的 currentId 均匹配上述 candidateId，changedFiles 均为上述两文件。未发现审查期间代码变化。未提交、未 approve、未改源码或业务数据、未运行模型。

## Stage 1：FAIL（1 项 MEDIUM）

需求依据：仓库根目录 `Product-Spec.md:248`。

| 条目 | 结论与证据 |
| --- | --- |
| 详情展示模板名称、版本 | 完整实现：`frontend/src/views/hengxin/components/TaskDetail.vue:16`、`:50` 接入组件；`TaskTemplate.vue:3`、`:5`、`:6` 输出标题、名称和版本。 |
| 优先冻结快照，兼容任务自带字段 | 完整实现：`TaskTemplate.vue:15`、`:17`；`frontend/src/types/hengxin.ts:52` 至 `:55` 定义必填名称和可选版本/快照。 |
| 不查模板库最新版；更新、改名、删除不改变历史绑定 | 完整实现：`TaskTemplate.vue:12` 至 `:19` 仅计算 props，没有模板查询；`backend/app/modules/tasks/queries.py:60` 至 `:64` 从任务快照映射名称、版本、快照。 |
| 文字任务未绑定模板显示“未使用模板” | 完整实现：`TaskTemplate.vue:5`；没有名称与版本时，第6行隐藏版本标签，不伪造版本。 |
| 历史记录缺失版本显示“版本未记录” | **部分实现，MEDIUM**：`TaskTemplate.vue:6` 仅在名称存在或版本存在时显示标签。非文字历史任务同时缺失名称及版本时，只显示“未保留模板信息”，没有需求要求的“版本未记录”。 |
| UI 与既有卡片一致 | 代码结构匹配：`TaskTemplate.vue:2`、`:3` 与 `TaskSources.vue:2`、`:3` 使用相同 ElCard、hx-gap、shadow=never、strong 标题。主Agent报告实际截图无溢出；本 reviewer 未直接取得截图，不将其记作独立视觉验证。 |
| 引导真实性与 Spec 漂移 | 本次范围无新增操作、API 或引导入口；`TaskTemplate.vue:8` 的冻结版本说明与 `queries.py:60` 至 `:63` 一致。未发现范围漂移。 |

### MEDIUM-01：历史模板信息完全缺失时，漏掉明确的版本缺失提示

Spec 原文：`Product-Spec.md:248`，“历史记录缺失版本显示‘版本未记录’”。

可达性：`backend/app/modules/tasks/queries.py:50` 默认 `template=''`，`:60` 仅在存在快照时补充版本。前端契约 `frontend/src/types/hengxin.ts:54`、`:55` 允许版本和快照缺失。因此非文字历史任务可以进入此分支，不需要构造违反契约的数据。

对 `TaskTemplate.vue:5`、`:6`、`:15` 至 `:18` 的表达式进行了无副作用 Node 复算，exit 0，原始输出：

```text
{"input":{"mode":"wallpaper","template":""},"name":"","version":null,"text":"未保留模板信息","showVersionTag":false}
```

具备名称但无版本的历史任务会正确显示“版本未记录”；缺失名称及版本的非文字任务不会。主Agent已补验的 v1/v2 和无模板文字任务均未覆盖此分支。修复验收应覆盖这个分支，并保持文字任务无伪造版本。

## Stage 2：未执行

依 skill“Stage 1 通过才进 Stage 2”，本轮未进入代码质量、安全扫描及独立浏览器视觉审查；不能登记两阶段 PASS。

## 已提供的测试、编译和浏览器证据

以下均为主Agent提供的结果摘要，未附原始命令输出和截图文件；本报告不将其冒充 reviewer 独立执行结果：

- `pnpm test`：79 passed。
- `pnpm build`：exit 0，44.05s，包含 vue-tsc。脚本定义可见 `frontend/package.json:10`：`vue-tsc --noEmit && vite build`。未取得完整原始编译输出，故无原始编译日志可附。
- 旧任务 `e731427e...` 显示换壁纸 v1，模板库现为 v2；新任务 `be1ed618...` 显示换壁纸 v2；文字任务 `fb8f30f3...` 显示未使用模板且不显示伪造版本。
- 主Agent确认素材区、任务状态正常，截图新增卡片边界清晰、无溢出、复用相邻 Card。

本报告仅覆盖指定增量。修复后由主Agent重新固定 candidateId，再从 Stage 1 复核；当前 candidate 不具备两阶段通过结论。
