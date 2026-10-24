import type { AnnotationMark } from "../hengxin/components/annotation/annotation-model";
import type { Draft, Material, Role, Task } from "./types";
export function requireRole(role: Role, expected: Role) {
  if (role !== expected)
    throw new Error(
      expected === "designer"
        ? "此操作需要海外设计权限"
        : "此操作需要海外运营权限",
    );
}
export function validateMaterial(file: Material) {
  const extension =
    file.kind === "requirement" ? /\.(pdf|docx?)$/i : /\.(xlsx?|csv)$/i;
  if (
    !extension.test(file.name) ||
    file.size <= 0 ||
    file.size > 20 * 1024 * 1024
  )
    throw new Error(
      "请选择有效资料文件，最大 20 MB；图需支持 PDF/DOC/DOCX，竞品支持 XLS/XLSX/CSV",
    );
}
export function validateDraft(d: Draft) {
  if (
    ![d.name, d.productName, d.brand, d.platform, d.market].every((s) =>
      s.trim(),
    )
  )
    throw new Error("请填写任务名称、品名、品牌、平台和目标站点");
  if (!d.skus.length || d.skus.some((s) => !s.code.trim()))
    throw new Error("请为每个 SKU 填写编码");
  if (
    new Set(d.skus.map((s) => s.code.trim().toLowerCase())).size !==
    d.skus.length
  )
    throw new Error("SKU 编码不能重复");
  if (!d.files.length)
    throw new Error("图片需求文件和竞品分析表格至少提供一份");
  d.files.forEach(validateMaterial);
}
export function log(task: Task, title: string) {
  task.events.unshift({ title, at: new Date().toISOString() });
}
export function createTask(draft: Draft, role: Role, id: string): Task {
  requireRole(role, "operator");
  validateDraft(draft);
  const task: Task = {
    ...draft,
    name: draft.name.trim(),
    productName: draft.productName.trim(),
    brand: draft.brand.trim(),
    files: draft.files.map((f) => ({ ...f })),
    skus: draft.skus.map((s) => ({
      code: s.code.trim(),
    })),
    id,
    status: "analyzing",
    createdAt: new Date().toISOString(),
    planVersion: 1,
    feedback: [],
    pictures: [],
    events: [],
  };
  log(task, "运营提交资料，开始模拟 AI 分析");
  return task;
}
export function reviewPlan(
  task: Task,
  role: Role,
  pass: boolean,
  note: string,
) {
  requireRole(role, "designer");
  if (task.status !== "plan") throw new Error("当前任务不在方案确认节点");
  if (!pass && !note.trim()) throw new Error("请填写方案修改意见后重新分析");
  if (!pass) {
    task.feedback.push(note.trim());
    task.planVersion++;
    task.status = "analyzing";
    log(task, `设计要求重新分析：${note.trim()}`);
  } else {
    task.status = "generating";
    log(task, `设计确认方案 v${task.planVersion}，开始模拟生图`);
  }
}
export function retry(task: Task, role: Role) {
  requireRole(role, "designer");
  if (task.status !== "analysisFailed" && task.status !== "generationFailed")
    throw new Error("当前任务无需重试");
  task.status = task.status === "analysisFailed" ? "analyzing" : "generating";
  log(task, "设计重试模拟 AI 处理");
}
export function approvePicture(task: Task, role: Role, id: string) {
  requireRole(role, "designer");
  const picture = task.pictures.find((p) => p.id === id);
  if (task.status !== "review" || !picture || picture.reworking)
    throw new Error("图片当前不可审核");
  picture.approved = !picture.approved;
  log(
    task,
    `${picture.sku} / ${picture.title}：${picture.approved ? "审核通过" : "撤回通过"}`,
  );
}
export function startRevision(
  task: Task,
  role: Role,
  id: string,
  version: number,
  note: string,
  marks: AnnotationMark[],
) {
  requireRole(role, "designer");
  const picture = task.pictures.find((p) => p.id === id);
  if (
    task.status !== "review" ||
    !picture ||
    picture.reworking ||
    picture.version !== version
  )
    throw new Error("图片状态已变化，请重新打开");
  if ((!note.trim() && !marks.length) || marks.some((m) => !m.note.trim()))
    throw new Error("请填写每处标注意见，或提供整体修改要求");
  picture.approved = false;
  picture.reworking = true;
  picture.history.push({
    version,
    note: note.trim(),
    marks: marks.map((m) => ({
      ...m,
      points: m.points.map((p) => ({ ...p })),
    })),
  });
  log(task, `${picture.sku} / ${picture.title} 提交单图返工`);
  return picture;
}
export function archive(task: Task, role: Role) {
  requireRole(role, "designer");
  if (
    task.status !== "review" ||
    !task.pictures.length ||
    task.pictures.some((p) => !p.approved || p.reworking)
  )
    throw new Error("请先通过全部 SKU 图片审核");
  task.status = "archived";
  log(task, "整套成品已按品名 → 品牌 → SKU 归档");
}
export function removeArchive(task: Task, role: Role) {
  requireRole(role, "designer");
  if (task.status !== "archived") throw new Error("该任务尚未归档");
  task.status = "review";
  log(task, "移除整套归档，保留图片与审核状态");
}
export function canDelete(task: Task, role: Role) {
  requireRole(role, "operator");
  if (task.status === "archived")
    throw new Error("请先由设计从成品库移除整套归档");
}
