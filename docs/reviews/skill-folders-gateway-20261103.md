# Skill 文件夹发布网关修复独立审查

## 快照与范围

- candidateId：`521070a88d439f95beffca563e9ef07c0f693dd7cfe98df404f868e2b1ceefdb`。
- **Stage 1：PASS。Stage 2：PASS。** 未发现本次 delta 的 HIGH / MEDIUM 问题。
- 使用 `.agents/skills/code-review/SKILL.md`，先核发布合同，再核质量、安全及隔离测试。未修改实现、未提交、未执行生产操作、未写 `.needs-review`；批准登记由主 Agent 执行。
- 范围：相对 HEAD `7c4d1ce` 的六个发布 Python 文件，以及合同 `docs/SKILL-FOLDERS-IMPLEMENTATION-20261103.md:22` 的发布补充。六文件为 `skill-folders-deploy.py`、`skill-folders-recovery.py`、`skill-folders-runtime.py`、`skill-folders-tests.py`、新建 `skill-folders-gateway.py`、新建 `skill-folders-gateway-tests.py`，均在 `scripts/release/`。
- 基线：`docs/reviews/skill-folders-approval-20261103.md:5` 记录 `78d1119ef880fd732715e5943492586eb703dd8fe2670cc1977979a447d2c892` 两阶段通过。当前 `git diff` / `review-status` 证明仅上述六个代码文件变化，业务功能、UI、依赖、版本号未变。本报告继承既有业务审查，不重新声称完成前后端或原生选择器验证。
- 审查开始的 `review-status.currentId` 与派发 candidateId 一致；结束再次检查一致。未发现审查期间代码变化。

## Stage 1：Spec Compliance

源依据为 `Product-Spec.md:1401` 引用的实施合同；合同原业务条目由上述基线报告逐项覆盖，本次新增发布条目拆分如下，无跳过项。

| 发布要求 | 结论与证据 |
| --- | --- |
| 固定网关容器身份，拒绝漂移 | 完整实现。`scripts/release/skill-folders-gateway.py:42` 从 `protected.containers[WEB]` 读取 id/image/running；`:43` 要求64位小写十六进制ID及原运行状态，`:47` 比对实时ID、镜像、名称、运行状态及compose project/service。基线结构真实来自 `scripts/release/skill-platform-baseline.py:34`，`skill-folders-deploy.py:62`、`:66` 原样存入 prepared；不是误用 account-runtime 的另一种数组结构。 |
| 配置检查成功后一次平滑重载 | 完整实现。`skill-folders-gateway.py:52` 先 `nginx -t`，`:53` 再 `nginx -s reload`，两次 exec 均使用已验证容器ID。没有配置写入、容器重建或重载重试循环。测试 `skill-folders-gateway-tests.py:40`、`:55`、`:61` 验证顺序、配置失败不重载、502重试不重复重载。 |
| 发布、回退、切换前恢复均接入刷新 | 完整实现。`skill-folders-deploy.py:204` 在API替换后刷新；`skill-folders-recovery.py:30` 恢复旧API后刷新；`:62` 正常回退后刷新；`:49` 回退排空复查失败、重新启动API后也刷新，然后保留失败状态。测试 `skill-folders-gateway-tests.py:119`、`:138`、`:162` 覆盖这些入口。 |
| 统一总期限 | 完整实现。单次网关刷新在 `skill-folders-gateway.py:41` 建立40秒monotonic deadline；`:45`、`:52`、`:53`、`:54` 的inspect、配置检查、reload和公网轮询共用剩余预算。curl自身和subprocess均限制剩余时间；收到成功响应后还检查deadline，`:32`。测试 `skill-folders-gateway-tests.py:84` 断言预算为6/5/4/3，慢配置检查耗尽预算后不执行reload。此期限指网关刷新及公网验收阶段，不是整个构建、部署、既有本地检查的总耗时。 |
| 公网HTTP200、status ready、必需依赖及全部checks为up | 完整实现。固定HTTPS正式地址 `skill-folders-gateway.py:8`；`:23` 禁用缓存请求、限制HTTPS；`:25` 到 `:31` 分离并检查状态码、JSON对象、postgresql/redis/minio存在及所有checks均为up。HTML、缺项、down、非ready、302及空checks在 `skill-folders-gateway-tests.py:73` 均被拒绝。 |
| 公网失败不得登记完成，不能只凭本地或静态成功 | 完整实现。`skill-folders-deploy.py:221` 在 `API_VERIFIED` 前检查公网；`:227`、`:232` 的frontend/resume继续调用verify。回退与恢复标记仅在refresh返回后写入，`skill-folders-recovery.py:31`、`:63`。测试 `skill-folders-gateway-tests.py:127`、`:138` 断言公网502时不写成功标记。 |
| 网关配置与业务数据保持不变 | 完整实现。新增helper的主机动作仅inspect、对固定ID执行nginx检查/信号、curl，`skill-folders-gateway.py:45` 到 `:54`；无写配置、数据库、Skill目录动作。现有恢复/发布动作不在本次改写范围，diff中仅增加刷新/校验调用。 |
| helper随正式制品交付且不可缺失 | 完整实现。`skill-folders-runtime.py:23` 加入HELPERS；`:50`、`:52`、`:65` 校验所需helper和精确scripts集合。`skill-folders-tests.py:133` 删除gateway的manifest项，真实verify_package拒绝Incomplete package。 |

部分实现：无。未实现：无。Spec漂移：无；新增网关helper与回归测试直接对应发布补充，没有新增页面、业务API或数据模型。UI一致性及邻居视觉比较：本delta无UI文件，继承基线报告，不重复浏览器操作，也不将此前原生目录选择器限制描述为已解决。

## Stage 2：Code Quality

- **组织与运行时绑定 PASS**：helper仅依赖注入的r，没有重新加载发布runtime或全局r，`skill-folders-gateway.py:17`、`:40`。调用者传入同一r，`skill-folders-deploy.py:204`、`skill-folders-recovery.py:30`。既有helper装载链 `skill-folders-runtime.py:24`、`:30` 调用捕获的original_helper，新增模块不引入循环加载。六文件均低于300行，原始结果见下。
- **安全 PASS**：`skill-folders-gateway.py:7`、`:8` 是固定容器/HTTPS入口；命令使用参数列表，容器ID先验证，执行目标固定。`scripts/release/account-runtime.py:28` 的实际run使用 `subprocess.run(args, capture_output=True, ...)`，非shell执行；失败仅输出命令名，不输出inspect结果或原始环境。helper不打印容器JSON或响应体，不接收密钥。扫描新增文件的eval、HTML注入、前端密钥、硬编码令牌及shell=True模式无命中。既有deploy中的publisher-unused占位值不属于新增秘密。
- **错误路径 PASS**：身份漂移中止；配置失败中止；reload失败由run异常中止；502、JSON错误、非200、依赖异常和超时均不能成功，`skill-folders-gateway.py:23` 到 `:37`、`:47` 到 `:54`。回退中途重启分支刷新失败也不会写回退完成标记，`skill-folders-recovery.py:47`。
- **测试真实性 PASS（隔离边界）**：独立复跑20项测试通过。gateway核心测试调用真实refresh/readiness，替换主机命令与时钟，断言具体exec顺序、次数、budget及失败行为，`skill-folders-gateway-tests.py:16` 到 `:95`。入口测试调用真实deploy/recovery控制流，隔离外部主机/DB/文件系统依赖，并检查失败后无成功标记，`:98` 到 `:170`。制品测试使用真实临时文件和verify_package，`skill-folders-tests.py:133`。这些测试证明脚本控制流，不冒充真实nginx或公网端到端重部署测试。
- **生产旁证边界**：只读查看主 Agent 提供的 `output/skill-folders-release/production-public-health.json:1`，记录HTTP200、ready、postgresql/redis/minio全部up。本 reviewer没有重新执行生产reload或部署；该记录支持已恢复的现场状态，不替代上述隔离脚本验收，也不证明原生目录选择器已通过。

## 独立执行原始输出

`python -B scripts/release/skill-folders-tests.py`，退出码0：

```text
..........
----------------------------------------------------------------------
Ran 10 tests in 1.172s

OK
```

`python -B scripts/release/skill-folders-gateway-tests.py`，退出码0：

```text
..........
----------------------------------------------------------------------
Ran 10 tests in 0.019s

OK
```

使用内置 `compile(source, path, 'exec')` 逐个编译六文件并断言行数不超过300，不执行模块主机操作，退出码0：

```text
scripts/release/skill-folders-deploy.py: compile PASS; 279 lines
scripts/release/skill-folders-recovery.py: compile PASS; 65 lines
scripts/release/skill-folders-runtime.py: compile PASS; 74 lines
scripts/release/skill-folders-tests.py: compile PASS; 168 lines
scripts/release/skill-folders-gateway.py: compile PASS; 54 lines
scripts/release/skill-folders-gateway-tests.py: compile PASS; 174 lines
```

主 Agent 现场记录原始内容：

```json
{"Status":200,"Body":"{\"status\":\"ready\",\"checks\":{\"postgresql\":\"up\",\"redis\":\"up\",\"minio\":\"up\"}}"}
```

结论限定于本candidate六文件发布修复。可登记同一candidate的两阶段PASS；不授权用本报告批准后续变化，也不要求重新部署已恢复的业务。
