# Codex 执行节点依赖与验收

Ubuntu 24.04 节点统一使用 `codex-runtime-packages.txt`。首次建机或依赖修复先执行：

```bash
sudo python3 install_codex_runtime.py --expected-host "$(hostname)"
sudo python3 install_codex_runtime.py --expected-host "$(hostname)" --apply
```

安装器只补齐依赖，拒绝移除或升级已安装包，不主动重启业务服务；保留输出中的实际版本。更新 apt 索引、升级已有包及发行版升级应独立安排，不在此脚本中静默执行。Node 为发行版提供的运行时，未承诺任意第三方 npm 包已安装。PPTX 基础读取使用 Python ZIP/XML，页面渲染使用 LibreOffice/Poppler，不依赖在线 Adobe/PowerPoint 连接。

每次部署/CLI 升级必须以两侧真实 worker UID、工作目录和服务环境执行 `python -B -m app.execution.runtime_check`；内网 systemd drop-in 将其作为 ExecStartPre。不能只运行 `codex --version` 或 `--help`。该检查不需要账号、不调用模型、不接触业务数据库。

完整安装验收使用 `verify_codex_runtime.py --workspace-module <backend>/app/execution/workspace.py --binary <实际Codex路径> --pptx <测试副本> --output <新的私有证据目录>`，覆盖内层命令、隔离、Python/Node、图片/DOCX/XLSX/PDF/PPT 渲染。输出目录含资料渲染图，只授权维护者访问，不打入发布包。

`verify_codex_model.py` 会产生真实模型用量，只有得到授权才执行。必须使用真实 worker UID/环境和既有账号 broker；海外测试读取指定 PPT，国内只生成一张受控修改图，不写生产业务库。脚本保存私有工具证据、会话结果并清理临时凭据。业务级按钮、数据库投递及其他格式仍需各自验收，不能以该脚本代替。

CLI 包的 `codex-code-mode-host` 与 `codex-resources/bwrap` 必须随版本保留。共享 `sandbox_command` 将内部 bwrap 以只读方式提供给沙箱；发行版 bwrap 同时在 PATH 上。只提供所需字体及 LibreOffice 只读配置，不挂载全部 `/etc`，不关闭 AppArmor 或沙箱。旧 CLI 无资源目录时依赖发行版 bwrap。

`office_render.py` 必须以0755部署在每份 workspace.py 同目录，由外层只读挂载为 `/opt/hx-tools/libreoffice` 和 `soffice`。这两个入口支持离线PDF转换、版本与帮助，拒绝其它选项；调用官方LibreOfficeKit稳定ABI，不启动IPC，不放开内层网络。每次转换限90秒，支持PPT/DOCX/XLSX等LibreOffice可读资料转PDF，失败不覆盖既有产物，输出限任务/work或/tmp。配套源码必须成套发布；验收脚本检查真实PDF/PNG，系统启动探针也实际渲染一页DOCX。
