# API 逐图尺寸与 PNG 成品验证

## 范围与状态

用户2026-09-29确认PNG并授权本地开发。本轮实现逐图向上16倍数尺寸、收图归一化PNG、API图片真实宽高DTO、当前/历史对照尺寸显示，以及受控中转域名下载兼容。不做比例异常阈值，不改变CLI，不部署、不提交、不新增收费生成。

原图尺寸来自最初source_id。方图1024；非方图100%～102%内比例误差最小，无候选单边扩至向上16倍数；并列相对增幅/宽高排序。新修改仍锚定最初底图。ApiAttempt通过0021增加四个nullable宽高列，历史请求保留NULL；PNG最终尺寸来自ApiFile。升级前已冻结旧staging且无新请求证据者按旧字节完成，后续修改走新策略。

## 已执行验证

- 前端worker执行 `pnpm exec tsx --test --test-reporter=dot tests/*.test.ts`：202通过；新增5项实际客户端/SFC测试，含当前/历史选择、异常元数据及未知状态。`pnpm typecheck`退出0。
- 主Agent最终 `pnpm build`：退出0（含vue-tsc），Vite构建29.75秒，日志`output/api-size-build-final.log`。自动生成的无关组件声明恢复基线，独立`pnpm typecheck`亦退出0。不以构建代表真实模型效果。
- 主Agent最终 `node scripts/api-size/browser.mjs`：6组检查通过、pageerror/未预期接口为0。隔离真实API模式页面，浏览器拦截所有业务接口与外域，不连接生产；1440px/390px当前与历史尺寸、版本选择和刷新、未知回退、两个弹窗标题可见及无横向裁切、创建页PNG规格说明。截图及结果`output/playwright/api-size/`，已实际查看matching-wide和mismatch-narrow截图，另存相邻既有详情基准及历史窄屏截图供独立reviewer对照。
- 主Agent `TEST_DATABASE_URL=<独立本机PG> .venv/Scripts/python.exe -m pytest -q tests/test_api_image_dimensions_migration.py`：SQLite/PostgreSQL两项通过（0.61秒），升级前记录保留、重复升级及nullable字段验证。独立tmpfs容器，无生产连接。
- 主Agent使用产品`normalize_result`处理此前已保存的11张真实API图片：11/11均可解码、PNG、尺寸精确等于各自上传底图；校验原始下载SHA256，0次模型调用。证据`output/api-size-normalized/verification.json`及对应PNG。仅证明后处理，不宣称最终向上尺寸策略已整批真实生图验收。
- 后端worker `pytest tests/test_api_image*.py`（设置两个API/迁移专用隔离PG环境变量）：132 passed / 0 skipped，24.46秒；`compileall`通过。新增尺寸23项、迁移双数据库测试及动态relay载荷验证。
- 主Agent最终Linux断网全套：`docker run --rm --init --network none ... -m pytest -q -p no:cacheprovider --basetemp=/tmp/hx-size-tests`，1415 passed / 78 skipped / 15 warnings，136.02秒，日志`output/api-size-backend-full-init.log`。78跳过为需要专用集成环境的既有条件测试；本轮API相关PG专项已另跑。首次未加--init时8项旧subreaper测试触发pytest PID1父进程保护（1406 passed/78 skipped/8 failed），纠正测试启动方式后上述全套通过，未改进程管理业务代码。warnings为既有SQLAlchemy空主键与TestClient cookies弃用提示。

## 限制

本轮没有部署；未来发布必须先执行0021再更新所有读取ApiAttempt的服务。既有历史图片不批量改写。API返回与请求不同仍按用户决定不增加比例拦截，直接还原原宽高；PNG格式不意味着缩放或模型内容无损。后处理超过既有20MiB结果限制等安全校验时收图失败，保留既有收图重试流程，不重新请求模型。

下载仅放行已配置精确域名及配置的中转base_url主机名，仍要求HTTPS、公网地址、DNS绑定、无重定向且不发送模型Authorization。测试中临时允许任意实际返回host的脚本不属于本次生产实现。
