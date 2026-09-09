<template>
  <div class="hx-page"><div class="hx-heading"><div><span class="hx-eyebrow">SYSTEM SETTINGS</span><h1>系统配置</h1><p>配置仅影响后续轮次，保存记录版本和实际操作者。</p></div><ElButton :loading="loading" :disabled="saving" @click="load">重新读取</ElButton></div><AdminPreview />
    <ElAlert v-if="error" :title="error" type="error" :closable="false"><ElButton text @click="load">重试加载</ElButton></ElAlert>
    <div v-if="form && data" class="hx-stack">
      <ElCard class="art-card hx-section"><h2>执行与上传 · 配置 v{{data.version}}</h2><ElForm label-position="top" class="hx-gap" :disabled="saving">
        <div class="hx-template-options"><ElFormItem label="执行并发"><ElInputNumber v-model="form.concurrency" :min="1" :max="10" :precision="0" aria-label="执行并发" /></ElFormItem><ElFormItem label="执行超时（秒）"><ElInputNumber v-model="form.timeoutSeconds" :min="60" :max="7200" :precision="0" aria-label="执行超时" /></ElFormItem><ElFormItem label="单张上传上限（MiB）"><ElInputNumber v-model="uploadMiB" :min="1" :max="10" :precision="0" aria-label="单张上传上限" /></ElFormItem></div>
        <div class="hx-template-options"><ElFormItem v-for="(label,key) in labels" :key="key" :label="`${label}默认 Skill`"><ElSelect v-model="form.defaultSkillIds[key]" clearable :aria-label="`${label}默认 Skill`"><ElOption v-for="skill in skills.filter(s=>s.mode===key&&s.status==='available')" :key="skill.id" :value="skill.id" :label="`${skill.name} · ${skill.version}`" /></ElSelect></ElFormItem></div>
        <p class="hx-footnote">前端预览范围：并发 1–10、超时 60–7200 秒、单张 1–10 MiB；真实容量与后台校验在后端阶段确认。</p>
        <h2 class="hx-gap">钉钉接入</h2><p class="hx-muted">检测状态：{{dingStates[data.dingtalk.state]}}。AppSecret 和 CLI 凭据保留部署环境，不在网页输入或回传。</p>
        <div class="hx-template-options"><ElFormItem label="企业 CorpId"><ElInput v-model="form.dingtalk.corpId" maxlength="120" aria-label="企业 CorpId" /></ElFormItem><ElFormItem label="应用 App 标识"><ElInput v-model="form.dingtalk.appId" maxlength="120" aria-label="应用 App 标识" /></ElFormItem><ElFormItem label="HTTPS 回调域名"><ElInput v-model="form.dingtalk.callbackDomain" placeholder="https://image.example.com" aria-label="HTTPS 回调域名" /></ElFormItem></div>
      </ElForm><ElAlert v-if="saveError" :title="saveError" type="error" :closable="false" /><ElButton class="hx-gap" type="primary" :loading="saving" :disabled="loading" @click="save">保存配置</ElButton></ElCard>
      <ElCard class="art-card hx-section"><h2>配置变更记录</h2><ArtTable :data="data.audit" :columns="columns" :show-pagination="false" empty-text="尚无配置变更"><template #changedAt="{row}">{{new Date(row.changedAt).toLocaleString('zh-CN')}}</template><template #fields="{row}">{{row.fields.map((field: string)=>fieldLabels[field] || field).join('、')}}</template></ArtTable></ElCard>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getSettings,saveSettings,listManagedSkills } from '@/api/management'
import type { ManagedSkill, SettingsInput } from '@/types/management'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import { labels } from '../model'
import AdminPreview from './AdminPreview.vue'
import { useAdminQuery } from './use-admin-query'
const skills=ref<ManagedSkill[]>([])
const {data,loading,error,load}=useAdminQuery(async()=>{const [settings,versions]=await Promise.all([getSettings(),listManagedSkills()]);skills.value=versions;return settings})
const form=ref<SettingsInput>(),uploadMiB=ref(10),saving=ref(false),saveError=ref('')
watch(data,value=>{form.value=value?JSON.parse(JSON.stringify(value)) as SettingsInput:undefined;if(value)uploadMiB.value=value.maxUploadBytes/1024**2})
const fieldLabels:Record<string,string>={concurrency:'执行并发',timeoutSeconds:'执行超时',maxUploadBytes:'上传限制',defaultSkillIds:'默认 Skill',dingtalk:'钉钉配置'}
const dingStates={unconfigured:'未配置',ready:'已就绪',error:'配置异常'}
async function save(){if(!form.value||saving.value)return;saving.value=true;saveError.value='';try{const input:SettingsInput={version:form.value.version,concurrency:form.value.concurrency,timeoutSeconds:form.value.timeoutSeconds,maxUploadBytes:uploadMiB.value*1024**2,defaultSkillIds:{...form.value.defaultSkillIds},dingtalk:{corpId:form.value.dingtalk.corpId,appId:form.value.dingtalk.appId,callbackDomain:form.value.dingtalk.callbackDomain}};for(const key of ['wallpaper','product','text'] as const)input.defaultSkillIds[key]||=null;data.value=await saveSettings(input);ElMessage.success('配置已保存，仅影响后续轮次')}catch(e){saveError.value=e instanceof Error?e.message:'保存失败，请重试'}finally{saving.value=false}}
const columns=[{prop:'version',label:'版本',width:90},{prop:'operatorName',label:'操作者',minWidth:140},{prop:'changedAt',label:'变更时间',minWidth:190,useSlot:true},{prop:'fields',label:'变更字段',minWidth:200,useSlot:true}]
</script>
