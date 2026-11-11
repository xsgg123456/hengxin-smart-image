# 内网海外 PPT 读取失败只读诊断 · 2026-11-11

范围：用户要求检查公司内网海外工作台读取 PPT 失败。连接 `192.168.1.245`，主机 `hengxin-ai-245`。本轮未修改线上配置、代码、任务或账号，未重跑模型。

## 定位

- 任务：`81689735-a131-4222-994d-85b3daeed908`。
- 会话 2：`c89437c5-25ff-4b41-93ff-bf7f7f4a5182`。
- 轮次：`654a91ab-bae0-488e-b0f1-a1250f13de1f`，北京时间 11:29:05 创建，截图回复时间 11:30:01。
- 数据库 job 为 succeeded，表示模型回复流程完成；回复正文明确没有读取到 PPT，不能将执行结束等同业务读取成功。

## 根因证据

真实 rollout 在 03:29:34 UTC 记录：读取 Skill 的 `cat` 与列目录的 `ls` 均在启动命令前失败，退出码 101：

```text
thread 'main' (...) panicked at linux-sandbox/src/launcher.rs:60:13:
bubblewrap is unavailable: no system bwrap was found on PATH and no bundled codex-resources/bwrap binary was found next to the Codex executable
```

海外 worker 实际使用 `/opt/hengxin-runtime/codex-0.167.1/bin/codex`。宿主有 `/opt/hengxin-runtime/bwrap` 和 `/opt/hengxin-runtime/codex-0.167.1/codex-resources/bwrap`，但 `/usr/bin/bwrap`、`/bin/bwrap` 均不存在。实际 `app/execution/workspace.py` 的外层沙箱 PATH 为 `/usr/bin:/bin`，仅将 Codex 主程序和 code-mode helper 分别挂载到 `/opt/codex`、`/opt/codex-code-mode-host`，未向沙箱暴露 bwrap/配套资源。外层可以启动，内部命令工具找不到其沙箱依赖。

实际源码 SHA-256：`823f0d636da8fa0418da0acae02d8e5439ed6c6fcbd1de1ebf7f9068f095d72a`。此前升级验收只验证版本、help 和 helper 启动，没有覆盖真实本地命令工具执行。

后续备用工具：PowerPoint 文档会话工具返回未连接任何会话；Adobe 初始化返回 UNAUTHORIZED。两者是本地工具失败之后的备用路径失败，不是 PPT 文件损坏的证据。

## 附件检查

会话 persistent/inputs 中《产品资料.pptx》存在，341,870 字节，SHA-256 与存放路径中的内容摘要一致；ZIP CRC 检查通过。包内 2 页幻灯片、2 个媒体文件、0 页备注，幻灯片 XML 可解析，合计文本字符数 502。没有发现上传或落盘损坏。

内网宿主目前无 libreoffice、pdftoppm、unzip 可执行文件，python3 存在。此项不是本次最初失败原因，但完整 PPT 页面渲染能力还需另行验证，不能仅修复命令启动后即声称全部 PPT 能力通过。

## 后续修复与验收方向

完整保留现有隔离边界，补齐 Codex 内层所需 bwrap 及配套资源的只读可见路径。用海外实际服务 UID、实际 Bubblewrap 路径先做无需模型的本地命令与 PPT 解析/渲染验证，再验证实际工具调用。任何部署前须检查在途任务，不能打断用户当前测试。涉及共享执行模块时核查国内业务兼容性；独立审查和必要测试通过后再部署。当前仅诊断，尚未实施修复。
