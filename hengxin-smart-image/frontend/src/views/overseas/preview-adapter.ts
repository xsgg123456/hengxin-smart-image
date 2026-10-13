import { reactive, ref } from "vue";
import type { Draft, Task } from "./types";
import { log } from "./workflow";
// 海外预览专属内存。无 API、身份存储或持久化依赖。
export const selectedOverseasTaskId = ref("");
export const overseasTasks = reactive<Task[]>([]);
const timers = new Set<ReturnType<typeof setTimeout>>();
export function schedule(callback: () => void) {
  const timer = setTimeout(() => {
    timers.delete(timer);
    callback();
  }, 1500);
  timers.add(timer);
}
export function resetOverseasPreview() {
  selectedOverseasTaskId.value = "";
  timers.forEach(clearTimeout);
  timers.clear();
  overseasTasks.splice(0);
}
export function simulate(task: Task, fail = false) {
  const status = task.status;
  if (status !== "analyzing" && status !== "generating") return;
  schedule(() => {
    if (!overseasTasks.includes(task) || task.status !== status) return;
    if (fail) {
      task.status =
        status === "analyzing" ? "analysisFailed" : "generationFailed";
      log(task, "模拟 AI 处理失败，可由设计重试");
      return;
    }
    if (status === "analyzing") {
      task.status = "plan";
      // 仅预览样例：真实图片数量必须来自后续分析方案。
      task.pictures = task.skus.flatMap((sku) =>
        ["产品全貌", "卖点细节", "使用场景"].map((title, i) => ({
          id: `${sku.code}-${i}`,
          sku: sku.code,
          title,
          url: `/demo-images/sample-${i + 1}.jpg`,
          version: 1,
          approved: false,
          reworking: false,
          history: [],
        })),
      );
      log(task, `模拟排版方案 v${task.planVersion} 已就绪`);
    } else {
      task.status = "review";
      log(task, "模拟图片生成完成，等待逐图审核");
    }
  });
}
export const emptyDraft = (): Draft => ({
  name: "",
  productName: "",
  brand: "HENGXIN",
  platform: "Amazon",
  market: "美国站 · 英语",
  skus: [{ code: "" }],
  remarks: "",
  files: [],
});
export const exampleDraft = (): Draft => ({
  ...emptyDraft(),
  name: "透明磁吸保护壳 · Amazon 美国站",
  productName: "透明磁吸保护壳",
  skus: [
    { code: "HX-MAG-01" },
    { code: "HX-MAG-02" },
  ],
  remarks: "突出清透、轻薄与磁吸体验。",
  files: [
    { name: "图片需求示例.pdf", size: 2048, kind: "requirement", sample: true },
  ],
});
