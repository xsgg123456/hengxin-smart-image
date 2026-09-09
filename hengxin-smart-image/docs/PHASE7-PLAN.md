# Phase 7 执行计划

2026-09-09；依据Product-Spec v0.17、DEV-PLAN Phase7。承接Phase6验收，保留当前未提交修改，不提交或覆盖旧成果。

1. 模板持久化：templates/template_versions/template_images，四角色共享创建/编辑/停用/删除，版本乐观锁，文件校验与图片顺序不可变；默认或专用绑定解析并冻结。验收：分页筛选排序、无Skill草稿、类型错配拒绝、跨owner删除审计、旧版本及对象不被改写。
2. Skill包：skills/skill_versions/module_skill_bindings，超管上传/安装/启停/默认绑定。ZIP可包含根SKILL.md或单个顶层目录；SKILL.md UTF8 YAML name/description必需。可选hengxin-skill.json声明mode/version（须匹配提交值）及requires.executables/pythonModules（仅校验安装环境已有依赖，不执行包安装脚本）。验收：实际CRC读取、拒绝越界/绝对/反斜杠/链接/重复路径/特殊设备/压缩炸弹/超限；包元数据哈希及原ZIP入私有存储，上传与安装状态区分。
3. 异步安装和通用队列：Job新增kind、认领token/租约与终态，安装路由按类型派发；持续心跳期间不重复投递，恢复后可安全重试幂等安装；独立attempt临时目录后原子发布不可变版本目录，失败不影响旧版、失败/成功/取消终态停止重派。验收：真实Linux Worker、重复消息/Redis故障/有效租约/永久失败/取消及旧token失效测试，Phase5队列回归通过。
4. 前端和交付：模板页面接真实列表和版本，Skill管理接上传/安装轮询与默认绑定；不提供假模板或假Skill。验收：前后端测试、构建/迁移、独立两阶段review和隔离数据库/MinIO/安装卷的浏览器业务回归，证据PHASE7-VALIDATION.md。

技术防护基线：ZIP本体20MiB、解压总计100MiB、单条目20MiB、1000条目、压缩比100；超限明确报错。这是受控包上传的工程上限，不改变图片上传10MiB业务规则。包内依赖必须预先在Worker镜像满足，安装不执行任意包脚本，也不访问网络安装依赖；真实业务效果在Phase14验收。

接口补充：GET/PUT /management/skills/defaults，body/response为三个模块到版本ID或null的对象；GET /templates/{id}/versions返回历史Template数组。Template新增可选skillBinding(module_default|specific)，skillVersionId表示该保存版本解析并冻结的实际版本，TemplateInput.skillVersionId=null表示模块默认。旧mock数据无skillBinding仍按显式绑定解释。模板无可用专用时允许保留该绑定草稿；不存在或跨类型绑定拒绝。模块默认切换不改旧模板快照，新建/重新保存才解析新默认。

分工与依赖：执行者A独占backend/app/modules/skills、backend/app/models.py、worker队列与安装、jobs.py、迁移0003及对应tests；执行者B独占backend/app/modules/templates、迁移0004及对应tests。主Agent负责contracts、main.py注册、migrations/env.py注册、settings/依赖、前端、infra和文档。skills模型与resolver API先约定，templates依赖其只读查询。各方不覆盖他人，不spawn，不commit。
