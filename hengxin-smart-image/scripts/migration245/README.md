# .245 内网迁移与维护工具

这些工具记录2026-11-10至11-11的已授权迁移和修复，包含特定主机、原生版本路径和基线摘要。不是可以在任意生产机一键重复运行的安装器；源或目标不符合保护条件时应停止，不能删备份或放宽校验强行重跑。

| 文件组 | 职责 |
|---|---|
| collect_runtime / transport | 受控只读采集与既有SSH身份连接，敏感运行配置仅在私有通道传递 |
| build_compose / build_native / build_edge / build_sandbox_proxy | 生成隔离容器、原生服务、入口及当时基线所需的代理适配 |
| data_copy / data_policy / install_files | 指定用户权限与Skills选择性迁移、文件摘要与路径校验，不复制旧业务历史 |
| ip_access / build_lan_frontend / hengxin-lan.tmpfiles.conf | 内网IP访问、正确前端菜单模式、重启后通信目录恢复 |
| upgrade_codex / fix_account_proxy | 已锁定CLI升级与账号代理修复，包含排空和回退 |
| fix_runtime | 沙箱与离线Office依赖修复发布，三处共享代码成套校验，worker启动自检 |

系统依赖和执行节点常规验收见 ../../infra/CODEX-RUNTIME.md；实施结果索引见 ../../../docs/INTRANET-245-RESULTS.md。真实配置、账号、数据库快照、模型测试附件、日志及构建输出不入Git。

## 测试与历史基线

本目录包含 `*_test.py` 和 `test_*.py` 两种命名，测试时两种均须收集。普通测试使用合成数据/临时目录；POSIX文件权限与链接用例需要Linux；真实PostgreSQL隔离用例仅在显式 `DATA_COPY_PG_TEST=1` 且Docker可用时执行，不使用业务数据库。

`fixtures/workspace_before_lan_proxy.py.fixture` 固定取自Git提交 `04b7c39` 中 `hengxin-smart-image/backend/app/execution/workspace.py`，规范化LF后的SHA256为 `35d4ba0240f5c1ffaaec317c3592ef28899cf04c414f6f640b737ef3465fcb75`。它是一次性旧版本补丁的测试输入，不是可发布模块；不能从当前已修复源码动态生成，否则后续源码迭代会让历史补丁测试失真。当前执行环境测试位于backend/tests/test_execution_*等文件。

## 发布边界

提交或推送这些脚本本身不会执行迁移，不应在CI导入时调用main。实际执行前仍须核对最近部署记录、目标主机、基线版本、在途任务和授权范围。数据库搬迁只面向首次空实例；维护脚本分别保护对应版本，不能作为任意版本更新工具使用。
