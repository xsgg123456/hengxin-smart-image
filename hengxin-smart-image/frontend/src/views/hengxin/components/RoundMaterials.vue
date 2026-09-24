<template>
  <section class="round-materials" aria-label="本轮执行材料">
    <ElAlert
      v-if="isMockMode"
      title="演示模式未执行真实模型，不提供真实提示词与输入材料记录。"
      type="info"
      :closable="false"
    />
    <template v-else>
      <div class="materials-heading">
        <strong>本轮执行材料</strong
        ><ElButton text type="primary" :loading="loading" @click="load">刷新材料</ElButton>
      </div>
      <p v-if="running" class="hx-footnote">
        本轮尚在执行，可刷新查看已采集的提示词与图片；结果以本轮完成记录为准。
      </p>
      <p v-if="loading" role="status">正在读取本轮执行材料…</p>
      <ElAlert v-if="error" :title="error" type="error" :closable="false"
        ><ElButton text @click="load">重试读取材料</ElButton></ElAlert
      >
      <template v-if="data">
        <ElAlert
          v-for="(notice, index) in data.notices"
          :key="index"
          :title="notice"
          type="info"
          :closable="false"
          class="material-notice"
        />
        <h4>本轮输入图片</h4>
        <MaterialPictures v-if="data.inputs.length" :items="data.inputs" />
        <p v-else class="hx-muted">本轮尚无可核实的输入图片记录。</p>
        <ElCollapse class="hx-gap">
          <ElCollapseItem title="完整任务提示词 · 系统交给 CLI" name="system">
            <p v-if="!data.systemPrompts.length" class="hx-muted">
              本轮未采集到完整任务提示词，历史原文不可用。
            </p>
            <article
              v-for="(prompt, index) in data.systemPrompts"
              :key="index"
              class="prompt-block"
            >
              <strong>{{ prompt.label }}</strong>
              <pre tabindex="0" :aria-label="`完整任务提示词 ${index + 1}`">{{ prompt.text }}</pre>
            </article>
          </ElCollapseItem>
          <ElCollapseItem
            :title="`实际生图提示词 · ${data.toolCalls.length} 次已记录调用`"
            name="tools"
          >
            <p class="hx-footnote">
              这是 CLI 记录的生图工具调用指令，与任务提示词分别展示；存在调用记录不代表生成成功。
            </p>
            <p v-if="!data.toolCalls.length" class="hx-muted">
              本轮尚未采集到可完整核实的生图工具调用记录。
            </p>
            <article v-for="(call, index) in data.toolCalls" :key="index" class="prompt-block">
              <strong>{{ call.label }}</strong>
              <pre tabindex="0" :aria-label="`实际生图提示词 ${index + 1}`">{{ call.prompt }}</pre>
              <p v-if="call.images.length" class="hx-footnote">本次调用的图片引用</p>
              <ul v-if="call.images.length">
                <li v-for="(path, i) in call.images" :key="i">{{ path }}</li>
              </ul>
              <p v-else class="hx-footnote">该调用未保留可展示的图片引用清单。</p>
            </article>
          </ElCollapseItem>
        </ElCollapse>
        <h4>本轮生成结果</h4>
        <MaterialPictures v-if="data.outputs.length" :items="data.outputs" />
        <p v-else class="hx-muted">
          {{
            running
              ? '本轮尚未发布新结果，原版本保留。'
              : '本轮没有已发布的结果记录，未用其他轮次结果替代。'
          }}
        </p>
      </template>
    </template>
  </section>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { isMockMode } from '@/api/hengxin/client'
import { createRoundMaterialsApi, type RoundMaterials } from '@/api/hengxin/round-materials'
import MaterialPictures from './MaterialPictures.vue'
const props = defineProps<{ taskId: string; roundId: string; state: string }>()
const data = ref<RoundMaterials>(),
  loading = ref(false),
  error = ref('')
const read = createRoundMaterialsApi(import.meta.env.VITE_API_URL || '/api/v1')
const running = computed(() => ['排队中', '执行中'].includes(props.state))
let sequence = 0
async function load() {
  if (isMockMode) return
  const token = ++sequence
  loading.value = true
  error.value = ''
  data.value = undefined
  try {
    const result = await read(props.taskId, props.roundId)
    if (token === sequence) data.value = result
  } catch (reason) {
    if (token === sequence)
      error.value = reason instanceof Error ? reason.message : '执行材料读取失败'
  } finally {
    if (token === sequence) loading.value = false
  }
}
watch(
  [() => props.taskId, () => props.roundId],
  () => {
    void load()
  },
  { immediate: true },
)
watch(
  () => props.state,
  () => {
    void load()
  },
)
onBeforeUnmount(() => {
  sequence++
})
</script>
<style scoped>
.round-materials {
  margin-top: 16px;
}
.materials-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.material-notice {
  margin: 10px 0;
}
h4 {
  margin: 20px 0 12px;
  font-weight: 500;
}
.prompt-block {
  min-width: 0;
  margin: 12px 0;
}
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 360px;
  overflow: auto;
  padding: 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-light);
  font: inherit;
  line-height: 1.7;
}
li {
  overflow-wrap: anywhere;
}
</style>
