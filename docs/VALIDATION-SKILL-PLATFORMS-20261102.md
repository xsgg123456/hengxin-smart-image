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

## 安装与生产验收（已执行）

- 已审源码提交 `16aa0091fc0d35631bfa00fbd168d54fb9e77f34`，生产版本 **0.2.57**；独立审查快照 `7f9ed634b94ebfe777f609e3201d7b3f24851826c0604d5bb143fdb472c0ed3d`，两阶段 PASS。
- 制品 `skill-platform-20261102-16aa009`，SHA-256 `fb8417f156dc14ee524411de5cf7c7074c99f51a0a23c3c2efb2c8c3ef408bff`，4,968,280 bytes，隐私扫描 PASS。只包含海外 API 的9个文件和1个迁移，以及前端资源/验证材料。
- 从实际安装镜像、实际 API 运行身份执行隔离 PostgreSQL/Linux 回归：**172 passed、0 failed、0 skipped**；包括平台并发、版本冲突、迁移、安装文件权限及 Windows 剩余失败模块。日志 `output/skill-platforms/installed-linux-tests.txt`；未将 Windows 全套409项跳过算作通过。
- 正式切换前确认任务空闲，停止海外 API 接单、暂停原生队列消费。私有数据库备份在隔离库恢复成功；迁移后旧记录、原有列和开关值保持，重复迁移稳定。生产升级至 `overseas_0023`。
- 海外 API 镜像 `sha256:e4fa8e1f4644120c6de5f588ce5f52a1d2c53a78f7f2243102cfa13677045dd7`，健康检查通过；前端资源与制品逐项校验通过，原生消费已恢复。
- 保护校验通过：999个 Skill 文件（含历史安装包、字体等）的字节哈希相同；7个原生服务的 PID、源码与配置相同；21个受保护其他容器状态与镜像相同。未更改执行器或 Skill 执行内容。
- 生产平台管理显示15项：Amazon10、Wayfair2、Walmart2、未分组1，其余三平台0。对一个原本关闭的 Skill 增加 Wayfair、保存、刷新重新读取，再移出 Wayfair，确认 Amazon 保留；已恢复原关联且始终关闭，仅留下正常版本递增和两条操作审计。
- 真实 Amazon 历史任务下拉只显示3个已开启匹配项的名称，无描述；原聊天、图片及任务素材正常显示。
- 取回文件真实读取91项：文件名 `.ZIP` 匹配小写 `.zip`，路径 `/WORK/OUTON_TASK/` 匹配58项；无结果0项、清空恢复91项；跨筛选保持已选1项并提示隐藏项。验收后已取消勾选、关闭弹窗并恢复侧栏，未新增重复取回记录或触发生图。
- 生产页面目视核对通过，浏览器 error 日志为空。截图 `output/skill-platforms/production-{management,skill-names,recovery-search}.png`；部署证据摘要 `output/skill-platforms/production-proof.json`。

恢复材料留在服务器私有发布目录 `/opt/hengxin-releases/skill-platform-20261102-16aa009`。迁移已完成，后端按向前修复处理；静态入口保留旧资源和备份。未将生产数据库备份复制进 Git 或发布包。

