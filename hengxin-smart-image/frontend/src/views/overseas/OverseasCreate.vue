<template>
  <div class="hx-heading">
    <div>
      <h1>{{ editing ? '修改图需' : '提交图需' }}</h1>
      <p>{{ editing ? '按设计反馈补充资料，修改完成后重新提交设计审核。' : preview ? '填写品名与 SKU，提供图需资料以体验模拟流程。' : '填写商品信息、SKU 并指定负责设计，提交后由设计先审核资料。' }}</p>
    </div>
    <ElButton :disabled="busy" @click="$emit('back')">返回任务列表</ElButton>
  </div>
  <ElAlert
    v-if="!allowed"
    title="暂无提交图需权限。"
    type="warning"
    :closable="false"
  />
  <div class="hx-create-grid">
    <div class="hx-stack">
      <ElCard class="art-card hx-section" shadow="never">
        <div class="hx-section-title">
          <h2><span class="hx-number">01</span>基本信息</h2>
          <slot name="example" />
        </div>
        <ElForm label-position="top" :disabled="!allowed || busy">
          <ElFormItem label="任务名称" required
            ><ElInput
              v-model="draft.name"
              maxlength="80"
              placeholder="例如：透明磁吸保护壳 · Amazon 美国站"
          /></ElFormItem>
          <div class="form-grid">
            <ElFormItem label="品名" required
              ><ElInput
                v-model="draft.productName"
                maxlength="80" /></ElFormItem
            ><ElFormItem label="目标平台" required
              ><ElSelect v-model="draft.platform"
                ><ElOption
                  v-for="p in [
                    'Amazon',
                    'TikTok Shop',
                    'Shopee',
                    'Lazada',
                    '其他',
                  ]"
                  :key="p"
                  :value="p" /></ElSelect></ElFormItem
            ><ElFormItem label="品牌" required
              ><ElInput v-model="draft.brand" maxlength="60" /></ElFormItem
            ><ElFormItem label="目标站点 / 语言" required
              ><ElInput v-model="draft.market" maxlength="60"
            /></ElFormItem>
          </div>
          <div class="hx-section-title">
            <h2>商品 SKU</h2>
            <ElButton :disabled="draft.skus.length >= 100" @click="draft.skus.push({ code: '' })"
              >添加 SKU</ElButton
            >
          </div>
          <div v-for="(sku, i) in draft.skus" :key="i" class="sku-row">
            <ElFormItem :label="`SKU ${i + 1}`" required
              ><ElInput
                v-model="sku.code"
                :aria-label="`SKU ${i + 1} 编码`"
                maxlength="80" /></ElFormItem
            ><ElButton
              type="danger"
              text
              :disabled="draft.skus.length === 1"
              @click="draft.skus.splice(i, 1)"
              >移除</ElButton
            >
          </div>
          <ElFormItem label="补充说明"
            ><ElInput
              v-model="draft.remarks"
              type="textarea"
              :rows="3"
              maxlength="1000"
          /></ElFormItem>
          <slot name="designer" />
        </ElForm>
      </ElCard>
      <slot name="after" />
    </div>
    <ElCard class="art-card hx-summary" shadow="never"
      ><h2>这套图如何完成</h2>
      <ElSteps direction="vertical" :active="0" :space="85"
        ><ElStep
          v-for="(step, i) in STAGES"
          :key="step"
          :title="step"
          :description="
            i === 0
              ? '运营核对品名、品牌与 SKU'
              : i === STAGES.length - 1
                ? '全部 SKU 通过后整套归档'
                : i === 1 ? '核对需求是否清晰、资料是否完整' : preview ? '设计跟进 · AI 模拟执行' : '审核通过后继续处理'
          " /></ElSteps
    ></ElCard>
  </div>
</template>
<script setup lang="ts">
import { STAGES } from './types'
interface Fields { name: string; productName: string; brand: string; platform: string; market: string; remarks: string; skus: { code: string }[] }
const draft = defineModel<Fields>({ required: true })
defineProps<{ allowed: boolean; busy?: boolean; preview?: boolean; editing?: boolean }>()
defineEmits<{ back: [] }>()
</script>
<style scoped>
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}
.sku-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
}
.actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  flex-wrap: wrap;
}
.file-row {
  overflow-wrap: anywhere;
  font-size: 13px;
}
.hx-summary h2 {
  margin-bottom: 24px;
  font-size: 16px;
}
h3 {
  font-size: 14px;
  margin-bottom: 12px;
}
.el-select {
  width: 100%;
}
@media (max-width: 600px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
  .actions > .el-button {
    margin-left: 0;
  }
  .sku-row {
    gap: 6px;
  }
}
</style>
