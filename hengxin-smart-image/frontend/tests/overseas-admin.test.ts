import { test } from "node:test";
import assert from "node:assert/strict";
import {
  members,
  skills,
  settings,
  saveMember,
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
test("海外 Skill 预览仅承接只读目录且退出清空，不写固定安装数量", () => {
  resetOverseasManagement(); assert.equal(skills.length, 0);
  skills.push({ id: "preview-skill", name: "preview", displayName: "预览目录", description: "完整描述" });
  assert.equal(skills[0].description, "完整描述");
  resetOverseasManagement(); assert.equal(skills.length, 0);
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
