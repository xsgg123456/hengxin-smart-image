<template>
  <ElButton text @click="$emit('back')">← 返回工作流任务</ElButton>
  <div class="hx-heading">
    <div>
      <h1>{{ task.name }}</h1>
      <p>
        {{ task.productName }} · {{ task.brand }} · {{ task.platform }} ·
        {{ task.market }}
      </p>
    </div>
    <ElTag>{{ STATUS_LABELS[task.status] }}</ElTag>
  </div>
  <ElCard class="art-card hx-section" shadow="never"
    ><div class="steps-scroll">
      <ElSteps :active="STATUS_STEP[task.status]" finish-status="success"
        ><ElStep v-for="stage in STAGES" :key="stage" :title="stage"
      /></ElSteps></div
  ></ElCard>
  <div class="hx-create-grid hx-gap">
    <ElCard class="art-card hx-section" shadow="never">
      <template v-if="['analyzing', 'generating'].includes(task.status)"
        ><h2>
          {{
            task.status === "analyzing" ? "AI 正在分析图需" : "AI 正在生成图片"
          }}
        </h2>
        <ElProgress
          :percentage="50"
          :indeterminate="true"
          :show-text="false"
          :duration="2"
          class="hx-gap"
        />
        <p class="hx-muted hx-gap">
          模拟处理中，完成后自动进入下一节点。未调用真实 AI。
        </p></template
      >
      <ElResult
        v-else-if="['analysisFailed', 'generationFailed'].includes(task.status)"
        icon="error"
        title="模拟处理失败"
        sub-title="此为预览故障演示，资料和修改意见已保留。"
        ><template #extra
          ><ElButton
            type="primary"
            :disabled="role !== 'designer'"
            @click="
              act(() => {
                retry(task, role);
                simulate(task);
              })
            "
            >重试处理</ElButton
          ></template
        ></ElResult
      >
      <template v-else>
        <div class="hx-section-title">
          <h2>
            {{
              task.status === "plan"
                ? "确认图片排版方案"
                : task.status === "archived"
                  ? "整套成品已归档"
                  : "逐张审核图片"
            }}
          </h2>
          <ElTag>{{
            task.status === "plan"
              ? `方案 v${task.planVersion}`
              : `${approved} / ${task.pictures.length} 张通过`
          }}</ElTag>
        </div>
        <ElAlert
          v-if="task.feedback.length"
          title="最新方案修改意见"
          :description="task.feedback.at(-1)"
          type="info"
          :closable="false"
        />
        <ElTabs v-model="sku"
          ><ElTabPane
            v-for="s in task.skus"
            :key="s.code"
            :label="s.code"
            :name="s.code"
        /></ElTabs>
        <template v-if="task.status === 'plan'">
          <article
            v-for="(picture, i) in pictures"
            :key="picture.id"
            class="plan-row"
          >
            <span class="hx-number">{{ i + 1 }}</span>
            <div>
              <h3>{{ picture.title }}</h3>
              <p>
                设计目标：清晰表达{{ task.productName }}的{{ picture.title }}。
              </p>
              <p>
                排版建议：产品主体居中、文案位于留白区域，统一品牌视觉与
                {{ task.market }} 文案。
              </p>
              <p v-if="task.feedback.length">
                修订关注：{{ task.feedback.at(-1) }}
              </p>
              <ElTag size="small" type="info">模拟排版建议</ElTag>
            </div>
          </article>
          <p class="hx-footnote">
            当前每 SKU
            {{ pictures.length }}
            张仅为预览样例。真实张数以确认方案为准；确认对全部 SKU 生效。
          </p>
          <ElInput
            v-model="opinion"
            aria-label="方案修改意见"
            type="textarea"
            :rows="3"
            maxlength="1000"
            placeholder="不通过时请填写方案修改意见"
            :disabled="role !== 'designer'"
          />
          <div class="actions hx-gap">
            <ElCheckbox v-model="fail" :disabled="role !== 'designer'"
              >演示下一次 AI 处理失败</ElCheckbox
            ><ElButton :disabled="role !== 'designer'" @click="plan(false)"
              >不通过，重新分析</ElButton
            ><ElButton
              type="primary"
              :disabled="role !== 'designer'"
              @click="plan(true)"
              >确认方案，开始生图</ElButton
            >
          </div>
        </template>
        <template v-else>
          <p class="hx-footnote">
            所有图片为内置示例；模拟返工只递增版本，不代表真实 AI 修改画面。
          </p>
          <OverseasPictures
            :task="task"
            :role="role"
            :pictures="pictures"
            :approved="approved"
            @approve="(id) => act(() => approvePicture(task, role, id))"
            @edit="editing = $event"
            @archive="saveArchive"
          />
        </template>
      </template>
      <ElAlert
        v-if="error"
        class="hx-gap"
        :title="error"
        type="error"
        :closable="false"
      />
      <p v-if="role !== 'designer'" class="hx-footnote">
        当前为运营视角；方案确认、图片审核与归档由海外设计负责。
      </p>
    </ElCard>
    <OverseasTaskInfo :task="task"><template #materials><ElDivider /><h3>原始图需资料</h3><ElButton text type="primary" @click="materialPreview = true">预览图需资料</ElButton><p v-for="f in task.files" :key="f.kind" class="hx-footnote">{{ f.name }} · {{ f.sample ? '示例资料' : '仅记录文件名，未解析' }}</p><OverseasMaterialPreview v-model="materialPreview" :files="task.files" /></template></OverseasTaskInfo>
  </div>
  <OverseasAnnotation
    v-if="editing"
    :key="editing.id"
    :picture="editing"
    :role="role"
    @close="editing = undefined"
    @submit="revise"
  />
</template>
<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessageBox } from "element-plus";
import type { AnnotationMark } from "../hengxin/components/annotation/annotation-model";
import OverseasTaskInfo from "./OverseasTaskInfo.vue";
import OverseasMaterialPreview from "./OverseasMaterialPreview.vue";
const materialPreview = ref(false);
import OverseasPictures from "./OverseasPictures.vue";
import OverseasAnnotation from "./OverseasAnnotation.vue";
import type { Picture, Role, Task } from "./types";
import { STAGES, STATUS_LABELS, STATUS_STEP } from "./types";
import {
  approvePicture,
  archive,
  log,
  retry,
  reviewPlan,
  startRevision,
} from "./workflow";
import { overseasTasks, schedule, simulate } from "./preview-adapter";
const props = defineProps<{ task: Task; role: Role }>();
const emit = defineEmits<{ back: []; archived: [] }>();
const sku = ref(props.task.skus[0]?.code ?? ""),
  opinion = ref(""),
  error = ref(""),
  fail = ref(false),
  editing = ref<Picture>();
const pictures = computed(() =>
  props.task.pictures.filter((p) => p.sku === sku.value),
);
const approved = computed(
  () => props.task.pictures.filter((p) => p.approved).length,
);
function act(fn: () => void) {
  error.value = "";
  try {
    fn();
  } catch (e) {
    error.value = (e as Error).message;
  }
}
function plan(pass: boolean) {
  act(() => {
    reviewPlan(props.task, props.role, pass, opinion.value);
    opinion.value = "";
    simulate(props.task, fail.value);
    fail.value = false;
  });
}
async function saveArchive() {
  try {
    await ElMessageBox.confirm(
      `将「${props.task.productName} / ${props.task.brand}」下全部 ${props.task.skus.length} 个 SKU、${props.task.pictures.length} 张图片归档？`,
      "归档到成品库",
      { confirmButtonText: "确认归档", cancelButtonText: "取消" },
    );
    archive(props.task, props.role);
    emit("archived");
  } catch (e) {
    if (e instanceof Error) error.value = e.message;
  }
}
function revise(version: number, note: string, marks: AnnotationMark[]) {
  act(() => {
    if (!editing.value) return;
    const task = props.task;
    const picture = startRevision(
      task,
      props.role,
      editing.value.id,
      version,
      note,
      marks,
    );
    editing.value = undefined;
    schedule(() => {
      if (!overseasTasks.includes(task)) return;
      picture.version++;
      picture.reworking = false;
      log(
        task,
        `${picture.sku} / ${picture.title} 模拟返工完成 v${picture.version}，等待重新审核`,
      );
    });
  });
}
</script>
<style scoped>
.steps-scroll {
  overflow: auto;
  padding-bottom: 8px;
}
.steps-scroll > .el-steps {
  min-width: 760px;
}
.plan-row {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding: 18px 0;
}
.plan-row > div {
  min-width: 0;
}
.plan-row p {
  font-size: 13px;
  line-height: 1.8;
  overflow-wrap: anywhere;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.actions {
  justify-content: flex-end;
}
h2 {
  font-size: 16px;
}
h3 {
  font-size: 14px;
}
</style>
