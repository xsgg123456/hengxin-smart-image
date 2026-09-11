# Phase 4 管理接口补充契约

> 以下保留 Phase 4 的模拟契约与当时边界。当前 Skill 管理及模块默认接口已在 Phase 7 接真实服务，默认绑定使用 `/management/skills/defaults`；用户管理、统计、监控和系统配置仍按 Phase 12–13 接入。现行接口及后续补充见 [API-CONTRACT.md](API-CONTRACT.md)，阶段进度见 [DEV-PLAN.md](../../DEV-PLAN.md)。

仅前端模拟，真实 HTTP 同结构且不回退；身份权限在每次请求重新检查，真实后端阶段实施服务端授权。前端不接收或保存任何 AppSecret、CLI 凭据。

接口根 `/management`：GET usage（from/to 为 Asia/Shanghai YYYY-MM-DD，含首尾日，userId/mode 可选）、GET monitor、GET/PUT users（PUT /users/:id）、GET/POST skills（POST multipart file/mode/version）、POST skills/:id/install、PUT skills/:id/status、GET/PUT settings。响应类型见 frontend/src/types/management.ts。上传只接受非空 ZIP（≤20 MiB）并计算 SHA-256；模拟安装验证生命周期，不执行包，不宣称真实目录/依赖验证。安装返回 installing，通过列表刷新查看结果；失败保留旧可用版，成功可用但不自动切默认。默认版本由 settings 显式切换；无删除接口，历史引用保留。

统计以实际开始时间归日，任务以创建时间归日；按操作者归属执行、按创建人归属任务。attempt id 去重，排队不计执行。成功率 success/(success+partial+failed+timeout)，零分母 null。任一执行 usage 缺失时该汇总 Token 为 null，避免把不完整合计当实际总量。个人身份指定其他 userId 返回 403。列表 users 仅超管，usage 自带许可范围内筛选用户。监控主管仅总体与业务明细，超管 detail 含模拟依赖信息；过期场景 unknown 与 idle 不混淆。

前端预览建议上限：并发 1–10，超时 60–7200 秒，上传限制 1–10 MiB，均为整数；后端实际容量另行确定。settings.version 必须等于当前版本，否则 409；默认 Skill 必须为匹配类型的 available 版本（允许 null）。HTTP 回调域名只接受不含路径/查询/账号的 HTTPS origin。每次保存递增版本并记录操作者、时间、变化字段，仅适用于后续轮次。当前已激活用户不能清空角色；待授权必须无角色；保护当前管理员与最后一位活跃管理员，防止预览自锁。

模拟管理故障独立参数 managementScenario：default/empty/unknown/idle/unavailable/list-error/save-error/install-error/worker-lost/auth-rejected/rate-limited/timeout。监控通过可选 issue（code/message）分别表达存储不可达、Worker 失联、认证拒绝、限流和超时；不把所有依赖一起标坏。请求错误场景首次失败后可重试；install-error 每版本首次安装失败，重试恢复。

模拟业务轮次真实记录每次开始/结束，统计引用独立历史账本，删除任务不减少历史任务及执行计数；关联已删除任务时详情返回 404。Round.executionConfig 可包含 version/concurrency/timeoutSeconds 快照；模拟执行器按并发排队和超时停止，设置不改变已提交轮次。上传限制应用于后续新上传；默认 Skill 引用与业务目录同源。模拟数据不表示真实 CLI 执行或 usage 采集，真实采集在 Phase 9/13。
