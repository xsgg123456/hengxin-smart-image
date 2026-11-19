# 国内通用新品与任务共享查看

本次国内专项增加第七个新品工作台，业务标识为 `general`；其余十个工作台继续使用原标识。任务列表允许查看当前业务其他成员的任务，编辑仍校验创建人。API 换套图限超级管理员使用。

## 维护与恢复

用户已授权更新内网发布工具，并在国内任务排空后短暂停用国内工作台及同组 API 换套图。维护目标为 `hengxin-ai-245`。进入生产操作前核实国内前后端基线 `3247094`、国内数据库 0045、五个工作台约束和空闲台账。国内钉钉登录回跳代码按审查过的文件摘要随国内包加载。

从已审 Git 提交用 `package_release.py --scope domestic` 打包。核对包摘要，通过 `stage.py` 暂存。执行当前内网工具的 `release.py general-prepare --scope domestic --mode full --release <已暂存目录>`，再执行 `general-deploy --scope domestic --mode full` 和 `verify`。专项对照基线和候选后端文件摘要，校验国内备份、迁移前后 19 张工作台表的计数及行摘要、五个 CHECK 的完整枚举和非目标组运行标识，再推进两版台账。

排空失败时恢复接入。发布中断时使用 `release.py general-recover --scope domestic --mode full`。迁移提交前可恢复旧版；0046 已提交时只向前恢复同一候选。后续发布遵循实际 schema 和已审版本的兼容性。
