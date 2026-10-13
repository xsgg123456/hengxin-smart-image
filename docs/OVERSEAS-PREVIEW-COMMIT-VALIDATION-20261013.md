# 遗留预览与规则改动收尾

用户授权处理Phase21–25提交后仍遗留的33个文件：28个未跟踪预览源码/测试/入口，5个已修改文件（Design-Brief、dev-builder规则、gitignore、package脚本和语言隔离配置）。此批开发前已经存在，前五次阶段提交没有包含；本轮核验后单独纳入Git。

## 规划与完成标准

1. 对照历史预览Spec及Design-Brief，核对33文件依赖闭合，保持正式五角色业务入口独立。
2. 执行全部前端单测、类型检查、正式与独立预览构建，运行工作流/管理/页面框架三组预览浏览器，确认无业务API请求与国内业务存储读取。
3. 固定快照交独立code-reviewer审查，修复并复验后批准；分别提交预览交付及通用开发规则，最后`git status --porcelain`应为空。

不改后端、数据库、生产服务或远端。现有3012是用户之前已启动的预览服务，本轮复用验证，结束不擅自停止该服务。规则改动只增加“内置模板不固化单个示例”的通用约束，不改变产品需求。

## 验证记录

- `pnpm test`：282通过、0失败、0跳过（8294ms），`output/remaining-frontend-test.log`。
- `pnpm build:overseas`：包含vue-tsc的独立双入口预览构建通过（50.36s），`output/remaining-preview-build.log`。
- `pnpm build`：包含vue-tsc的正式构建通过（34.79s），`output/remaining-formal-build.log`。
- `node tests/overseas-preview.browser.mjs`：授权场景、多SKU/必填与重复校验、资料失败恢复、方案修改、单图画布返工、全部通过后归档、筛选与退出、390/760/1440视口通过；零业务API请求、不读国内用户/业务存储、零页面异常。`output/remaining-preview-browser.log`。
- `node tests/overseas-management.browser.mjs`：统计随内存任务变化、空态、成员/Skill新增编辑启停删除及取消、配置校验与保存重置、非管理员直链拒绝、390px通过；零业务API请求、零页面异常。`output/remaining-management-browser.log`。
- `node tests/overseas-shell.browser.mjs`：资料类型校验与删除确认、全局搜索/切换重挂、海外与一期卡片模式及实际圆角一致，国内入口保持原模拟页面通过。`output/remaining-shell-browser.log`。

此批不涉及后端变更，未重复运行后端全量；前一正式交付已验收的真实业务代码保持不变。构建生成的声明噪声在最终快照前恢复，仅保留本批有意改动。

- 恢复生成文件后再次执行 `pnpm --dir hengxin-smart-image/frontend typecheck`，退出码0，`output/remaining-typecheck-final.log`。
- 独立审查：`docs/reviews/OVERSEAS-PREVIEW-COMMIT-REVIEW-20261013.md`，Stage 1 PASS、Stage 2 PASS，HIGH 0、MEDIUM 0。候选快照 `5072f0ce8509b03da3c96a7a7efa528f3d4db52fffb7bff580ffec078003f294`。
- 证据边界：浏览器存储读取断言覆盖最后完整工作流文档，未累计四种登录场景的全部历史读取；独立入口另经源码核对。自动移动截图可能处于加载态，审查者已另等待真实空态后实看。两项均为非阻断测试增强建议。
