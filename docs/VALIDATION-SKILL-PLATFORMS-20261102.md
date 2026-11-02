# Skill 平台管理与工作台优化验证记录

对应实施合同：`docs/SKILL-PLATFORMS-IMPLEMENTATION-20261102.md`。

## 本地验证

- 前端全套：435 passed、0 failed、0 skipped；`output/skill-platforms-tests.log`。
- 前端类型检查、独立预览类型检查、生产构建均 exit 0；构建版本 0.2.57，日志 `output/skill-platforms-{typecheck,build}.log`。
- 依赖审计：critical 0，既有 high 39 / moderate 38 / low 5；本次不变更依赖，原始结果 `output/skill-platforms-audit.json`。不宣称全部漏洞已消除。
- 后端 Windows 全套初跑：2533 passed、409 skipped、10 failed。两处旧断言已同步（新增 API 路径、目录 platforms 字段），对应文件复跑 42 passed；受影响功能回归 124 passed、1 个 Windows 权限检查 skipped。剩余 8 个失败为 Linux 安全文件读取或 Windows 符号链接权限限制，具体见 `output/skill-platforms/backend-full-windows.log`。这些结果不替代 Linux 安装验证。
- 发布脚本故障恢复、范围保护和测试日志留痕：14 tests passed。

## 真实 Vue 页面浏览器验证

以正式 Vue 页面配隔离 HTTP 测试数据在本地验证，非生产接口：

- 单项多平台保存、从 Wayfair 移出保留 Amazon、添加已有 Skill 取并集、批量覆盖平台成功。
- 409 版本冲突提示、保留平台草稿，刷新版本后保存成功。
- 管理页只读配置隐藏写操作；后端真实权限以 API 测试为准。
- Amazon 工作台仅匹配已开启项，下拉只有名称；保留主动查看说明入口。
- 已选 Skill 不再适用时保留输入草稿并禁发送；清空 Skill 后可继续无 Skill 对话。
- 取回文件按路径忽略大小写搜索、无结果提示、清空恢复；隐藏已选项计入总数并提示；重新显示仍勾选；原取回回调成功关闭弹窗。
- 390×844 窄屏下搜索框及底部操作可见，验证后恢复视口。

截图：`output/skill-platforms/formal-{management,conflict,skill-names,recovery-search,recovery-mobile,invalid-skill}.png`。

## 发布门槛

先对固定源码快照独立审查并提交，再从已提交制品运行隔离 PostgreSQL、迁移、Linux 权限和受影响回归；安装测试不允许 skipped。通过后排空海外任务、私有备份并隔离恢复验证、执行附加迁移、只切换海外 API 与前端。生产原生执行服务、其他容器、全部 Skill 文件须前后保持一致。

安装测试和生产验收结果由实际执行后补充；本记录不把待执行项目计为通过。

