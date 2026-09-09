# Skill 版本包约定

超级管理员在“管理中心 → Skill 管理”上传 ZIP，填写对应处理类型和版本号，再点击安装。安装完成后可设置模块默认。模板保存时固定实际版本，变更默认不会更新旧模板。

ZIP 可直接包含 SKILL.md，或将所有内容放在单个顶层目录。SKILL.md 使用 UTF-8，文件开头需要 YAML 元数据：

```markdown
---
name: your-skill-name
description: 说明这个 Skill 的用途
---

这里放具体的处理说明。
```

可选的 `hengxin-skill.json` 放在 SKILL.md 旁边，格式如下：

```json
{
  "mode": "wallpaper",
  "version": "1.0.0",
  "requires": {
    "executables": ["python"],
    "pythonModules": ["PIL"]
  }
}
```

mode 可选 wallpaper、product、text；声明时必须与上传表单一致，version 同理。依赖检查只确认 Worker 已预装的命令和顶层 Python 模块；不执行包内安装脚本，也不下载依赖。缺依赖时安装失败，旧版本仍保留，可修复 Worker 环境后重试安装。

ZIP 最大20 MiB，最多1000条目，解压总计100 MiB、单文件20 MiB、压缩比100。路径必须是普通相对路径，拒绝符号链接、设备文件、绝对路径、越界路径、重复路径及损坏内容。

同一个 Skill 名称、类型和版本号不能覆盖已成功上传的包。网络或存储导致上传未完成时，可以重传字节完全相同的原包；变更内容须使用新版本号。启停不删除版本和历史引用。

当前 Phase 7 完成包校验、安装及绑定；具体图像处理和 CLI 执行在后续阶段接入。验收脚本内的测试包仅用于隔离测试，不作为业务 Skill 发布。
