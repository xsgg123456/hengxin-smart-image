# 已关闭 Skill 管理目录删除

用户核对十项名单后明确授权“删吧，这些都删掉”。本次使用现有 Skill 发布服务的删除接口，不修改应用实现、不物理删除历史版本或会话文件。

执行步骤及完成标准：
1. 按上轮确认的十个内部名称、内容校验值与关闭状态重新核对，记录八个保留项及历史引用。
2. 通过生产发布服务依次删除，每次携带当前发布版本、Skill 内容校验值及开关版本，记录接口回执；状态漂移停止。
3. 确认目录只剩原八个已开启项、内容及开关不变；验证原发布版本未改写、历史引用仍可读，核对服务健康。

确认名单：amazon-main-image-product-swap-1250、amazon-main-image-product-swap-1600、amazon-outonlife-new-product-aplus、beleev-amazon-aplus、beleev-amazon-image-set、walmart-new-product-image-set-original、walmart-new-product-image-set-revised-0927、walmart-outon-outonlife-main-image-and-aplus-design-dept、wayfair-new-product-image-set-main、wayfair-new-product-image-set-main-aplus。

删除管理目录不等于回收物理磁盘：现有发布机制创建新版本并保留旧版本，本次不删除会话依赖的历史版本，不声称释放90.85MB。

## 完成结果

- 十项均通过现有 publisher DELETE 接口成功删除，每次用当时发布版本、内容校验值和开关版本请求；接口已生成正常的 skill.delete 审计。受信任本地发布接口使用现有有权限管理账号张帅，未改账号权限。
- 原发布版本 `3e805ac91eebe55b9c2ce7c15622a79ab8d6d0ab2a659cd28330a755aed61e14`；最终版本 `5a84781052bd5304ffd233d7cd874db23dd00b3ecf3ecf8d9774690ae9ea64c9`。
- publisher 与正式 API 的目录均验证仅剩原八个已开启项；保留项 checksum、开关、版本与平台设置完全不变。
- 原十二个安装发布目录逐条文件元数据未变；删除项对应历史任务引用的一个独立冻结包重新完整读取校验通过。未删除或修改会话文件。
- 国内、海外 ready 均 HTTP 200；worker、outbox 均 active。没有部署应用、修改代码或调用模型。
- 服务器回执 `/opt/hengxin-disabled-skills-delete-20261106/receipt.json`，核对结果 `verification.json`；本地副本 `output/disabled-skills-delete-20261106/`。
