import test from "node:test";
import assert from "node:assert/strict";
import {
  approvePicture,
  archive,
  canDelete,
  createTask,
  removeArchive,
  retry,
  reviewPlan,
  startRevision,
  validateDraft,
  validateMaterial,
} from "../src/views/overseas/workflow";
import { exampleDraft, overseasTasks, resetOverseasPreview, selectedOverseasTaskId, simulate } from "../src/views/overseas/preview-adapter";
import type { Task } from "../src/views/overseas/types";
function fixture(): Task {
  const t = createTask(exampleDraft(), "operator", "OS-test");
  t.status = "review";
  t.pictures = t.skus.map((s) => ({
    id: s.code,
    sku: s.code,
    title: "示例",
    url: "/demo-images/sample-1.jpg",
    version: 1,
    approved: false,
    reworking: false,
    history: [],
  }));
  return t;
}
test("提交校验资料、重复及空 SKU、角色，提交即分析且复制数据", () => {
  const d = exampleDraft();
  assert.equal(createTask(d, "operator", "a").status, "analyzing");
  assert.throws(() => createTask(d, "designer", "a"), /运营权限/);
  assert.throws(() => validateDraft({ ...d, files: [] }), /至少提供一份/);
  assert.throws(
    () =>
      validateDraft({
        ...d,
        skus: [
          { code: " x " },
          { code: "X" },
        ],
      }),
    /不能重复/,
  );
  assert.throws(
    () => validateDraft({ ...d, skus: [{ code: "  " }] }),
    /填写编码/,
  );
  assert.throws(() => validateDraft({ ...d, skus: [] }), /填写编码/);
  assert.deepEqual(
    createTask({ ...d, skus: [{ code: " X " }] }, "operator", "sku-only").skus,
    [{ code: "X" }],
  );
  assert.throws(
    () =>
      validateMaterial({
        name: "bad.exe",
        kind: "requirement",
        sample: false,
        size: 10,
      }),
    /有效资料/,
  );
  const t = createTask(d, "operator", "b");
  d.skus[0].code = "changed";
  assert.notEqual(t.skus[0].code, "changed");
});
test("方案仅设计可处理，重分析必填意见且版本递增，失败可重试", () => {
  const t = fixture();
  t.status = "plan";
  assert.throws(() => reviewPlan(t, "operator", true, ""), /设计权限/);
  assert.throws(() => reviewPlan(t, "designer", false, "  "), /修改意见/);
  reviewPlan(t, "designer", false, "减少文案");
  assert.equal(t.status, "analyzing");
  assert.equal(t.planVersion, 2);
  t.status = "analysisFailed";
  retry(t, "designer");
  assert.equal(t.status, "analyzing");
  t.status = "plan";
  reviewPlan(t, "designer", true, "");
  assert.equal(t.status, "generating");
});
test("单图返工只影响当前图片，旧版本及无意见拒绝，归档要求整套通过", () => {
  const t = fixture();
  t.pictures.forEach((p) => {
    p.approved = true;
  });
  const untouched = structuredClone(t.pictures[1]);
  assert.throws(
    () => startRevision(t, "operator", t.pictures[0].id, 1, "修改", []),
    /设计权限/,
  );
  assert.throws(
    () => startRevision(t, "designer", t.pictures[0].id, 2, "修改", []),
    /状态已变化/,
  );
  assert.throws(
    () => startRevision(t, "designer", t.pictures[0].id, 1, "", []),
    /修改要求/,
  );
  startRevision(t, "designer", t.pictures[0].id, 1, "减少文字", []);
  assert.deepEqual(t.pictures[1], untouched);
  assert.equal(t.pictures[0].approved, false);
  assert.throws(
    () => approvePicture(t, "designer", t.pictures[0].id),
    /不可审核/,
  );
  assert.throws(() => archive(t, "designer"), /全部 SKU/);
  t.pictures[0].reworking = false;
  t.pictures[0].version++;
  approvePicture(t, "designer", t.pictures[0].id);
  archive(t, "designer");
  assert.equal(t.status, "archived");
  assert.throws(() => canDelete(t, "operator"), /移除/);
  assert.throws(() => removeArchive(t, "operator"), /设计权限/);
  removeArchive(t, "designer");
  assert.equal(t.status, "review");
  assert.ok(t.pictures.every((p) => p.approved));
  canDelete(t, "operator");
});

test("模拟适配器完成分析、保留失败任务并可重试；重置会清空独立状态", async () => {
  resetOverseasPreview()
  overseasTasks.push(createTask(exampleDraft(), 'operator', 'OS-adapter'))
  const task = overseasTasks[0]
  selectedOverseasTaskId.value = task.id
  simulate(task, true)
  await new Promise(resolve => setTimeout(resolve, 1600))
  assert.equal(task.status, 'analysisFailed')
  retry(task, 'designer'); simulate(task)
  await new Promise(resolve => setTimeout(resolve, 1600))
  assert.equal(task.status, 'plan')
  assert.equal(task.pictures.length, 6)
  reviewPlan(task, 'designer', true, '')
  simulate(task)
  resetOverseasPreview()
  await new Promise(resolve => setTimeout(resolve, 1600))
  assert.equal(overseasTasks.length, 0)
  assert.equal(selectedOverseasTaskId.value, '')
  assert.equal(task.status, 'generating')
})
