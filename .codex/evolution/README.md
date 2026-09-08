# 自进化运行状态

`signals.jsonl` 和 `proposals.md` 是本地状态，不上传 Git。SessionStart 自动补建缺失文件。

纠正信号由 UserPromptSubmit 收集；主 Agent 按 AGENTS.md 派发 evolution-runner，返回建议后由用户决定是否落地。可复用改进最终提交到 AGENTS.md、对应技能或 hook。
