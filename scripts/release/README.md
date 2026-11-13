# 当前发布入口

生产仅为内网 hengxin-ai-245 / 192.168.1.245:8080。使用 [内网发布指南](../../docs/INTRANET-RELEASE-TOOLS.md)，国内/海外明确选择 scope；禁止整站重发或恢复旧公网发布脚本。

根目录保留 release-retention-state.py 供内网台账复用；retirement-backup.py 及其依赖仅为历史数据库迁移回归提供支持，不是当前发布入口。image-inputs-worker.py 的旧命令行入口已关闭。intranet/ 为当前发布实现。

infra 中 compose.vps.yaml、nginx.vps.conf 和 nginx.zhitu.qhhengxin.top.conf 仍被隔离性能测试和迁移生成器读取，保留为测试/迁移输入，不代表默认生产地址。公网历史文档仅作验收证据；已删源码可从 Git 历史查阅。

删除清单见 [退役清单](../../docs/PUBLIC-RELEASE-RETIRED-FILES-20261113.json)。本次未删除任何服务器文件。
