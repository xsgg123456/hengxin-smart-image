# PostgreSQL 恢复约束文本校验修复 · 独立审查

- candidateId：`a64ad7535479f10a2fa0bacebf9fd43fe83252d55d5842d6b98a20827e5e859d`。
- **Stage 1：PASS；Stage 2：PASS。** 本次范围无待修复 HIGH/MEDIUM。
- 基线：HEAD `8b4fe7e`，已批准候选 `d8b96549500601afbecbdbf29b68cc3a1423bbeeff53581e185fd2dd677c281b`，既有审查见 `docs/RECORDS-CLEANUP-RELEASE-FINAL-REVIEW-20261022.md:1`。本报告仅对新增修复进行复审，不重新宣称全部旧业务或生产验收完成。
- 受控代码范围严格为 `scripts/release/domestic-record-filters-schema.py`、`scripts/release/domestic-record-filters-verify.py`、`scripts/release/package-record-filters.py`、`scripts/release/test_record_filters_schema.py`。以下简称均指 `scripts/release/` 中对应文件。
- 已读取 code-review skill、快照协议、Product-Spec 最新联合发布授权、`docs/RECORDS-CLEANUP-RELEASE-20261022.md` 全文和前次最终审查；本 reviewer 未改代码、提交、操作生产、spawn 或登记批准，仅运行本地检查并写本报告。

## Stage 1 · 修复边界逐项核对

| 需求 | 结论与证据 |
| --- | --- |
| 只接受已实证的 varchar 字面量数组整体转 text[] 与各元素转 text 两种形式 | 完整实现。schema `:6`–`:9` 将匹配限制为普通字面量、精确 character varying、固定分隔符及 text[] 尾部；`:21` 限制 CHECK，`:25`–`:32` 仅移动 cast 位置。原字面量 token 完整保留，无去引号、值解析或重新转义。test_schema `:23`–`:28` 验证空字符串、重复值、逗号、双单引号、中文及嵌入括号。 |
| 不掩盖值、顺序、列、类型、运算符差异 | 完整实现。schema `:30`–`:31` 按原顺序输出全部 token，不排序或去重；`:41`–`:43` 逐字符保留外部表达式。test_schema `:31`–`:45` 及 `:83`–`:86` 对新增/删除/重复/改值/换序、列名、ANY/ALL、比较运算符、源/目标类型、长度修饰及大小写变化断言不相等。 |
| 不把不支持或引号内文本误认作可规范化 SQL | 完整实现。schema `:33`–`:38` 完整跳过单引号/双引号段；`:27`–`:28`、`:35`–`:36`、`:39`–`:40` 遇到无法识别的数组、转义、美元引用或注释返回整条原文，已累积的局部结果也不输出。test_schema `:48`–`:74` 覆盖空数组、NULL、函数、坏引号、间距、E 字符串、反斜杠、多维目标和注释等拒绝路径；`:77`–`:80` 验证多个合法数组及 NOT VALID 保留。 |
| 只处理 schema.constraints.definition，其他 schema 和全部行/列比较不变 | 完整实现。verify `:15`–`:26` 的 schema 查询与基线相同；`:29`–`:36` 全表全行指纹不变；唯一新增处理为 `:37`–`:40` 的 definition 映射。relation/name、columns/default/type、indexes 全部保留。test_schema `:89`–`:106` 对完整 state 做等值断言，故意将相同 SQL 文本放入 column_default/indexdef，证明不会误规范化这些字段。 |
| 不忽略 CHECK，不退化成只比较行数 | 完整实现。verify `:35`–`:36` 仍包含全行 JSON 的排序内容摘要及行数；`:65`–`:69` 和 `:74`–`:76` 仍比较完整 state。约束列表、名称和规范化后的定义仍在 state 中，没有过滤掉 CHECK。test_backup `:43`–`:68` 验证恢复助手调用、完整 state、差异拒绝、失败无 COMPLETE 及 finally 恢复助手。 |
| 发布包必须携带新增 helper | 完整实现。package `:10` 将 schema 加入 SCRIPTS；`:11` 传播为 REQUIRED；`:22`–`:28` 保证选入并拒绝缺失。既有 test_release `:29`–`:40` 验证选择路径，`:43`–`:49` 由 SCRIPTS 参数化，实际运行包含新增 schema 缺失拒绝用例。 |
| 真实 PostgreSQL 导出/恢复复验 | 主 Agent 提供的现场证据已读取：`output/records-cleanup-release-20261022/schema-real-restore-result.txt:1`–`:2` 分别为保存的真实状态比较 PASS、新 network none 隔离恢复 PASS。该文件是主 Agent 实测记录；本 reviewer 没有连接生产或自行执行该恢复。其已报告的 PG16.15、5条等价差异和全量比较，与代码边界一致。 |
| 业务、数据库版本与 UI 不变；无新增范围 | `git diff 8b4fe7e -- scripts/release` 与 review-status 确认仅上述4个代码文件变化。package `:34`–`:37` 版本0.2.49、国内0032和海外0020不变；没有页面、API、表或业务行为增量。引导真实性、设计稿/邻居页面渲染对比在此纯发布校验修复中无新增对象，不虚构视觉验收；业务/UI继承已审基线。 |

数组整体 cast 与逐元素 cast 的等价性并非仅来自测试夹具：已核对 [PostgreSQL 16 官方文档 §4.2.12](https://www.postgresql.org/docs/16/sql-expressions.html#SQL-SYNTAX-ARRAY-CONSTRUCTORS)，其明确说明数组构造器的显式类型转换等同于将各表达式转换为目标元素类型。schema `:6`–`:8` 进一步将适用范围缩小到本次已实证的普通 varchar 字面量数组。

范围内没有部分实现、未实现或 Spec 漂移项。重新不可变打包、生产切换及切换后业务验收仍由主 Agent 执行；源码通过不等于生产发布成功。

## Stage 2 · 质量、安全和测试真实性

- 单一职责与规模通过：schema 44行、verify 98行、package 47行、test_schema 106行，均未超过300行。schema `:13` 为无数据库/文件/进程副作用的纯函数，遇不支持内容保守返回原文；verify `:38` 仅修改刚从 JSON 新建的局部对象。
- 测试真实性通过：test_schema `:13`–`:17` 构造形式与生产报告及 PostgreSQL 官方语义一致，正向用例断言精确文本，不是只断言真值；反向用例断言结果不同，覆盖 literal token 的引号/逗号边界；state 层测试验证仅正确字段变化。test_backup `:59` 实际走失败处理路径，test_release `:43` 实际拒绝缺失 helper。单元测试中的数据库响应为 mock，不能替代真实恢复；现场恢复证据已独立标明来源。
- 安全通过：4文件检索 eval/exec、shell=True、危险 HTML、前端秘密变量、sk-ant/sk-proj、个人绝对路径及 password 赋值无命中。schema `:6`–`:10` 仅进行字符串匹配与拼接，不执行 SQL；verify 新增导入 `:12`–`:14` 指向固定同目录文件。没有新增凭据、动态 SQL执行或写数据库动作。
- 视觉比较不适用：本候选没有新增/修改页面或样式；证据是4文件快照范围，既有业务/UI结论仅继承基线，不声称本轮重新浏览或已完成生产视觉验收。

## 独立验证原始输出

```text
命令：.\hengxin-smart-image\backend\.venv\Scripts\python.exe -m pytest -q scripts/release/test_record_filters_schema.py scripts/release/test_record_filters_release.py scripts/release/test_record_filters_backup.py scripts/release/test_record_filters_native.py
........................................................................ [ 63%]
..........................................                               [100%]
114 passed in 1.40s
exit_code: 0
```

```text
命令：.\hengxin-smart-image\backend\.venv\Scripts\python.exe -m py_compile scripts/release/domestic-record-filters-schema.py scripts/release/domestic-record-filters-verify.py scripts/release/package-record-filters.py scripts/release/test_record_filters_schema.py
stdout/stderr: (empty)
exit_code: 0
```

```text
命令：git diff --check
warning: in the working copy of 'docs/RECORDS-CLEANUP-RELEASE-20261022.md', CRLF will be replaced by LF the next time Git touches it
exit_code: 0
```

主 Agent 的真实恢复证据原文如下（不是本 reviewer 执行输出）：

```text
SAVED_REAL_PG_STATE_MATCH rows/schema/columns: PASS
FRESH_ISOLATED_POSTGRES_RESTORE: PASS
```

## 快照复核与交接

审查开始、测试/编译完成后 review-status 均返回相同 currentId：

```json
{"currentId":"a64ad7535479f10a2fa0bacebf9fd43fe83252d55d5842d6b98a20827e5e859d","reviewedId":"d8b96549500601afbecbdbf29b68cc3a1423bbeeff53581e185fd2dd677c281b","changedFiles":["scripts/release/domestic-record-filters-schema.py","scripts/release/domestic-record-filters-verify.py","scripts/release/package-record-filters.py","scripts/release/test_record_filters_schema.py"],"approved":false}
```

未发现代码漂移。主 Agent 同期仅追加普通 Markdown 现场证据，不影响受控快照。主 Agent 可使用本报告与同一 candidateId 登记两阶段 PASS，随后再次核对 review-status；本 reviewer 未写 clean 或批准状态。
