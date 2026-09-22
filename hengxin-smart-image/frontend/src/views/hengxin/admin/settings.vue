<template>
  <div class="hx-page"><div class="hx-heading"><div><span class="hx-eyebrow">SYSTEM SETTINGS</span><h1>系统配置</h1><p>配置仅影响后续轮次，保存记录版本和实际操作者。</p></div><ElButton :loading="loading" :disabled="saving" @click="load">重新读取</ElButton></div><AdminPreview />
    <ElAlert v-if="error" :title="error" type="error" :closable="false"><ElButton text :disabled="loading || saving" @click="load">重试加载</ElButton></ElAlert>
    <ElAlert v-if="saveError" :title="saveError" type="warning" :closable="false" />
    <ElCard v-if="loading && !data" class="art-card hx-section"><p role="status">正在读取系统配置…</p><ElSkeleton :rows="5" animated /></ElCard>
    <ElEmpty v-else-if="!data && !error" description="暂无系统配置" />
    <ElAlert v-if="data && data.timeoutCapacity < 60" title="部署超时上限低于60秒，请先调整部署配置" type="warning" :closable="false" />
    <div v-if="form && data" class="hx-stack">
      <ElCard class="art-card hx-section"><h2>执行与上传 · 配置 v{{data.version}}</h2><ElForm label-position="top" class="hx-gap" :disabled="saving || loading || !!error || data.timeoutCapacity < 60">
        <div class="hx-template-options"><ElFormItem label="执行并发"><ElInputNumber v-model="form.concurrency" :min="1" :max="data.capacity" :precision="0" aria-label="执行并发" /></ElFormItem><ElFormItem label="执行超时（秒）"><span v-if="data.timeoutCapacity < 60">{{ data.timeoutSeconds }} 秒（只读）</span><ElInputNumber v-else v-model="form.timeoutSeconds" :min="60" :max="data.timeoutCapacity" :precision="0" aria-label="执行超时" /></ElFormItem><ElFormItem label="单张上传上限（MiB）"><ElInputNumber v-model="uploadMiB" :min="1" :max="10" :precision="0" aria-label="单张上传上限" /></ElFormItem></div>
        <div class="hx-template-options"><ElFormItem v-for="(label,key) in labels" :key="key" :label="`${label}默认 Skill`"><ElSelect v-model="form.defaultSkillIds[key]" clearable :aria-label="`${label}默认 Skill`"><ElOption v-for="skill in skills.filter(s=>s.mode===key&&s.status==='available')" :key="skill.id" :value="skill.id" :label="skill.name" /></ElSelect></ElFormItem></div>
        <p class="hx-footnote">并发 1–{{ data.capacity }}，部署容量上限 {{ data.capacity }}；调整配置不会增加执行节点。<template v-if="data.timeoutCapacity >= 60">超时 60–{{ data.timeoutCapacity }} 秒</template><template v-else>部署超时上限 {{ data.timeoutCapacity }} 秒</template>、单张 1–10 MiB。</p>
        <h2 class="hx-gap">钉钉接入</h2><p class="hx-muted">配置状态：{{dingStates[data.dingtalk.state]}}，不代表真实登录已验证。钉钉接入由部署环境管理，网页只读；AppSecret 和 CLI 凭据不在网页输入或回传。</p>
        <div class="hx-template-options"><ElFormItem label="企业 CorpId"><ElInput :model-value="data.dingtalk.corpId" readonly aria-label="企业 CorpId" /></ElFormItem><ElFormItem label="应用 App 标识"><ElInput :model-value="data.dingtalk.appId" readonly aria-label="应用 App 标识" /></ElFormItem><ElFormItem label="HTTPS 回调域名"><ElInput :model-value="data.dingtalk.callbackDomain" readonly aria-label="HTTPS 回调域名" /></ElFormItem></div>
      </ElForm><div class="hx-save-row"><span class="hx-muted" role="status">{{ dirty ? '有未保存的修改' : '当前配置已保存' }}</span><ElButton type="primary" :loading="saving" :disabled="loading || !!error || data.timeoutCapacity < 60 || !dirty" @click="save">保存配置</ElButton></div></ElCard>
      <ElCard class="art-card hx-section"><h2>配置变更记录（最近 100 条）</h2><ArtTable height="auto" empty-height="340px" :show-table-header="false" :data="data.audit" :columns="columns" :show-pagination="false" empty-text="尚无配置变更"><template #changedAt="{row}">{{new Date(row.changedAt).toLocaleString('zh-CN')}}</template><template #fields="{row}">{{row.fields.map((field: string)=>fieldLabels[field] || field).join('、')}}</template></ArtTable></ElCard>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getSettings,saveSettings,listManagedCatalog } from '@/api/management'
import type { CatalogSkill } from '@/types/management'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import { labels } from '../model'
import AdminPreview from './AdminPreview.vue'
import { useAdminQuery } from './use-admin-query'
import { useSettingsEditor } from './settings-editor'
const skills=ref<CatalogSkill[]>([])
const {data,loading,error,load}=useAdminQuery(async()=>{const [settings,versions]=await Promise.all([getSettings(),listManagedCatalog()]);skills.value=versions;return settings})
const {form,uploadMiB,saving,saveError,dirty,save: persist}=useSettingsEditor({data,loading,error,load},saveSettings)
const fieldLabels:Record<string,string>={concurrency:'执行并发',timeoutSeconds:'执行超时',maxUploadBytes:'上传限制',defaultSkillIds:'默认 Skill',dingtalk:'钉钉配置'}
const dingStates={unconfigured:'未配置',ready:'配置完整',error:'配置异常'}
async function save(){if(await persist())ElMessage.success('配置已保存，仅影响后续轮次')}
const columns=[{prop:'version',label:'版本',width:90},{prop:'operatorName',label:'操作者',minWidth:140},{prop:'changedAt',label:'变更时间',minWidth:190,useSlot:true},{prop:'fields',label:'变更字段',minWidth:200,useSlot:true}]
</script>
<style scoped>
.hx-save-row { display:flex; align-items:center; justify-content:space-between; gap:16px; margin-top:16px; }
</style>
