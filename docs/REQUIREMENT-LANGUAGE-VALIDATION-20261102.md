# 图需语言及归档六字段 · 验证记录

范围：docs/REQUIREMENT-LANGUAGE-20261102.md。用户已授权开发、提交及生产部署。

## 已完成的开发验证

- 前端最终448/448单测通过，0跳过；日志hengxin-smart-image/frontend/language-tests.log。typecheck退出0，language-typecheck.log。
- 正式0.2.59生产构建退出0，Vite 34.82秒；output/language-release/frontend-build.log。
- 最终生产dist在隔离vite preview3046上的requirement-language.browser.mjs通过；四语言创建/重提、必填空值、历史语言null/缺省、接口允许的历史TikTok Shop平台保留、归档六独立快照字段及未知值、1366/390px可见区裁切。日志output/language-release/browser-final.log及output/playwright/requirement-language截图。测试用受控API，不冒充生产写入验收。既有designer-only浏览器也已通过。
- 后端Windows全套：2615 passed、416 skipped、8 failed（476.71秒）。7项为safe open unavailable；1项为WinError1314符号链接权限。日志backend/language-regression.log。不能作为全后端绿的声明。
- Linux/PostgreSQL A批60模块：530 passed、2 failed（351.93秒）。Windows八项在Linux通过；新增语言HTTP及真实PG迁移通过。两失败为旧management/materials迁移快照漏新增language列，现只将预期追加NULL，并纳入B批复验；业务源码未因这两项修改。证据output/language-release/batch_a.stdout。
- 发布工具language62 + outon70：132 passed；独立reviewer另行复跑通过。
- 生产依赖审计critical 0，既有high39/moderate38/low5；本轮不改依赖，未声明解决历史漏洞。output/language-release/dependency-audit.json。

## 待完成

Linux B批75模块（原73+两个修正迁移模块）运行中；独立审查最终报告、Git提交、实际镜像安装验证、生产备份迁移与页面验收尚待完成。

## 最终回归补充

Linux B批75模块：1079 passed、1 failed、2 skipped（527.83秒），其中A批两修正迁移模块均已通过。唯一失败为旧studio material可见性迁移测试同样漏了Task.language新列；只补预期NULL，未改业务代码。随后在隔离Linux/PostgreSQL集中重跑三处旧迁移和新语言迁移共4模块：5 passed、0 skipped（37.53秒）。原始证据为batch_b.stdout及batch_repair.stdout；未将分批加修正复验声称为一次全套通过。

B批两项跳过对应Windows junction和需要可选私有STUDIO_INCIDENT_FIXTURE的历史事故输入。Windows junction在本机单独复验1 passed（0.40秒）。可选历史事故样本本轮未提供；本轮语言/归档/迁移必需用例无跳过。

最终代码快照a1eb4c2a58bd081efa0de3ee7027b5bbaca41a5f1c1960614f592bf77b7cfdc3，仅在上一轮审查后追加一处真实迁移NULL列断言，业务源码不变；最终独立差异复核报告见reviews/REQUIREMENT-LANGUAGE-FINAL-20261102.md。
