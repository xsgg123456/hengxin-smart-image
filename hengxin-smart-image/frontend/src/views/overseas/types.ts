import type { AnnotationMark } from "../hengxin/components/annotation/annotation-model";
export type Role = "operator" | "designer";
export type Page = "create" | "tasks" | "archive";
export type Status =
  | "pending_review"
  | "returned"
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
  "设计人工审核",
  "AI 排版分析",
  "设计确认方案",
  "AI 生成图片",
  "设计逐图审核",
  "归档成品库",
];
export const STUDIO_STAGES = ['运营提交图需', '设计人工审核', 'AI 设计工作台', '归档成品库'];
export const STUDIO_DESCRIPTIONS = ['运营核对品名、品牌与 SKU', '核对需求是否清晰、资料是否完整', '设计上传素材、选择 Skill，与 Codex 协作出图', '选择满意图片按 SKU 归档，全部完成后结束任务'];
export const STATUS_LABELS: Record<Status, string> = {
  pending_review: "待设计审核",
  returned: "退回运营",
  analyzing: "分析中",
  analysisFailed: "分析失败",
  plan: "方案待审",
  generating: "生成中",
  generationFailed: "生成失败",
  review: "图片待审",
  archived: "已归档",
};
export const STATUS_STEP: Record<Status, number> = {
  pending_review: 1,
  returned: 0,
  analyzing: 2,
  analysisFailed: 2,
  plan: 3,
  generating: 4,
  generationFailed: 4,
  review: 5,
  archived: 6,
};
