import { reactive } from "vue";
import type { Task } from "../types";
import type { Skill } from "../../../api/overseas/management";

export type ManagementPage =
  | "usage"
  | "monitor"
  | "users"
  | "skills"
  | "settings";
export const roles = { operator: "运营", designer: "设计", admin: "管理员" };
export interface Member {
  id: string;
  name: string;
  department: string;
  role: keyof typeof roles;
  enabled: boolean;
}
export const members = reactive<Member[]>([]);
export const skills = reactive<Skill[]>([]);
export const defaultSettings = () => ({
  name: "海外生图",
  concurrency: 3,
  timeout: 300,
  retention: 30,
});
export const settings = reactive(defaultSettings());

export function saveMember(input: Member) {
  const value = {
    ...input,
    name: input.name.trim(),
    department: input.department.trim(),
  };
  if (
    !value.name ||
    value.name.length > 40 ||
    value.department.length > 60
  )
    throw new Error("请填写姓名（1–40 字）");
  if (!(value.role in roles)) throw new Error("请选择海外业务角色");
  if (
    members.some(
      (m) =>
        m.id !== value.id &&
        m.name.toLowerCase() === value.name.toLowerCase() &&
        m.department.toLowerCase() === value.department.toLowerCase(),
    )
  )
    throw new Error("同部门已存在同名成员");
  upsert(members, value);
}
function upsert<T extends { id: string }>(list: T[], value: T) {
  if (!value.id) {
    list.push({ ...value, id: crypto.randomUUID() });
    return;
  }
  const index = list.findIndex((item) => item.id === value.id);
  if (index < 0) throw new Error("记录已不存在，请重新打开");
  list.splice(index, 1, value);
}
export function removeRecord(list: { id: string }[], id: string) {
  const index = list.findIndex((item) => item.id === id);
  if (index >= 0) list.splice(index, 1);
}
export function saveSettings(value: ReturnType<typeof defaultSettings>) {
  if (!value.name.trim() || value.name.trim().length > 40)
    throw new Error("请填写系统名称（1–40 字）");
  for (const [n, min, max] of [
    [value.concurrency, 1, 20],
    [value.timeout, 30, 3600],
    [value.retention, 1, 365],
  ]) {
    if (!Number.isInteger(n) || n < min || n > max)
      throw new Error(
        "并发须为 1–20、时限为 30–3600 秒、保留为 1–365 天的整数",
      );
  }
  Object.assign(settings, value, { name: value.name.trim() });
}
export function taskSummary(tasks: Task[]) {
  return {
    tasks: tasks.length,
    pictures: tasks
      .filter((t) => ["review", "archived"].includes(t.status))
      .reduce((n, t) => n + t.pictures.length, 0),
    archived: tasks.filter((t) => t.status === "archived").length,
    events: tasks.reduce((n, t) => n + t.events.length, 0),
    running: tasks.filter(
      (t) =>
        ["analyzing", "generating"].includes(t.status) ||
        t.pictures.some((p) => p.reworking),
    ).length,
    failed: tasks.filter((t) =>
      ["analysisFailed", "generationFailed"].includes(t.status),
    ).length,
    pending: tasks.filter((t) => ["plan", "review"].includes(t.status)).length,
    reworking: tasks.reduce(
      (n, t) => n + t.pictures.filter((p) => p.reworking).length,
      0,
    ),
  };
}
export function resetOverseasManagement() {
  members.splice(0);
  skills.splice(0);
  Object.assign(settings, defaultSettings());
}
