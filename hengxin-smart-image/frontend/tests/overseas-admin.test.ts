import { test } from "node:test";
import assert from "node:assert/strict";
import {
  members,
  skills,
  settings,
  saveMember,
  saveSkill,
  saveSettings,
  removeRecord,
  resetOverseasManagement,
  taskSummary,
} from "../src/views/overseas/admin/management-adapter";
import { createTask } from "../src/views/overseas/workflow";
import { exampleDraft } from "../src/views/overseas/preview-adapter";

test("海外成员独立新增编辑禁用删除与重复校验", () => {
  resetOverseasManagement();
  assert.throws(() =>
    saveMember({
      id: "",
      name: " ",
      department: "海外",
      role: "operator",
      enabled: true,
    }),
  );
  saveMember({
    id: "",
    name: "成员",
    department: "海外",
    role: "operator",
    enabled: true,
  });
  assert.equal(members.length, 1);
  assert.throws(() => saveMember({ ...members[0], id: "" }), /同名/);
  saveMember({ ...members[0], role: "admin", enabled: false });
  assert.equal(members[0].role, "admin");
  assert.equal(members[0].enabled, false);
  removeRecord(members, members[0].id);
  assert.equal(members.length, 0);
});
test("海外 Skill 内容必填、唯一名称、更新及删除", () => {
  resetOverseasManagement();
  assert.throws(() =>
    saveSkill({
      id: "",
      name: "排版",
      stage: "analysis",
      content: " ",
      enabled: true,
    }),
  );
  saveSkill({
    id: "",
    name: "排版",
    stage: "analysis",
    content: "按提供资料分析",
    enabled: true,
  });
  assert.throws(() => saveSkill({ ...skills[0], id: "" }), /重复/);
  saveSkill({ ...skills[0], content: "更新指令", enabled: false });
  assert.equal(skills[0].content, "更新指令");
  assert.equal(skills[0].enabled, false);
  removeRecord(skills, skills[0].id);
  assert.equal(skills.length, 0);
});
test("系统配置阻止无效数字，保存与退出重置独立内存", () => {
  resetOverseasManagement();
  for (const concurrency of [0, 21, NaN, 1.5])
    assert.throws(() => saveSettings({ ...settings, concurrency }));
  assert.throws(() => saveSettings({ ...settings, name: " " }));
  saveSettings({ name: "海外配置", concurrency: 4, timeout: 60, retention: 7 });
  assert.equal(settings.concurrency, 4);
  resetOverseasManagement();
  assert.equal(settings.concurrency, 3);
});
test("任务统计仅基于当前任务，排版占位图不计产出，返工与失败单独计数", () => {
  assert.equal(taskSummary([]).tasks, 0);
  const task = createTask(exampleDraft(), "operator", "admin-stat-task");
  task.pictures = [
    {
      id: "p",
      sku: "sku",
      title: "图",
      url: "",
      version: 1,
      approved: false,
      reworking: false,
      history: [],
    },
  ];
  task.status = "plan";
  assert.equal(taskSummary([task]).pictures, 0);
  task.status = "review";
  task.pictures[0].reworking = true;
  const summary = taskSummary([task]);
  assert.equal(summary.pictures, 1);
  assert.equal(summary.running, 1);
  assert.equal(summary.reworking, 1);
  task.status = "generationFailed";
  assert.equal(taskSummary([task]).failed, 1);
  assert.equal(taskSummary([task]).pictures, 0);
});
