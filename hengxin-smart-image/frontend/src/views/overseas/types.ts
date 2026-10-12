import type { AnnotationMark } from "../hengxin/components/annotation/annotation-model";
export type Role = "operator" | "designer";
export type Page = "create" | "tasks" | "archive";
export type Status =
  | "analyzing"
  | "analysisFailed"
  | "plan"
  | "generating"
  | "generationFailed"
  | "review"
  | "archived";
export interface Sku {
  code: string;
}
export interface Material {
  name: string;
  size: number;
  kind: "requirement" | "competitor";
  sample: boolean;
}
export interface Draft {
  name: string;
  productName: string;
  brand: string;
  platform: string;
  market: string;
  skus: Sku[];
  remarks: string;
  files: Material[];
}
export interface Picture {
  id: string;
  sku: string;
  title: string;
  url: string;
  version: number;
  approved: boolean;
  reworking: boolean;
  history: { version: number; note: string; marks: AnnotationMark[] }[];
}
export interface Task extends Draft {
  id: string;
  status: Status;
  createdAt: string;
  planVersion: number;
  feedback: string[];
  pictures: Picture[];
  events: { title: string; at: string }[];
}
export const STAGES = [
  "运营提交图需",
  "AI 排版分析",
  "设计确认方案",
  "AI 生成图片",
  "设计逐图审核",
  "归档成品库",
];
export const STATUS_LABELS: Record<Status, string> = {
  analyzing: "分析中",
  analysisFailed: "分析失败",
  plan: "方案待审",
  generating: "生成中",
  generationFailed: "生成失败",
  review: "图片待审",
  archived: "已归档",
};
export const STATUS_STEP: Record<Status, number> = {
  analyzing: 1,
  analysisFailed: 1,
  plan: 2,
  generating: 3,
  generationFailed: 3,
  review: 4,
  archived: 5,
};
