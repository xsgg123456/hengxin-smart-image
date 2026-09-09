<template>
  <ElCard class="art-card hx-section">
    <h3>模块默认 Skill</h3><p class="hx-muted">模板未指定专用版本时使用此默认值。切换默认不改变已保存的模板；重新保存时才采用新默认。</p>
    <ElAlert v-if="error" :title="error" type="error" :closable="false"><ElButton text :disabled="loading || saving" @click="load">重新加载</ElButton></ElAlert>
    <ElForm v-loading="loading" label-position="top" :disabled="loading || saving || !ready">
      <ElFormItem v-for="(label, mode) in labels" :key="mode" :label="label">
        <ElSelect v-model="values[mode]" clearable :aria-label="`${label}默认 Skill`" placeholder="不设置默认版本" @clear="values[mode] = null">
          <ElOption v-if="unavailable(mode)" :value="values[mode]!" label="原默认版本已不可用，请重新选择或清空" disabled />
          <ElOption v-for="skill in available(mode)" :key="skill.id" :value="skill.id" :label="`${skill.name} · v${skill.version}`" />
        </ElSelect>
      </ElFormItem>
      <ElButton type="primary" :loading="saving" :disabled="!ready || loading" @click="save">保存默认绑定</ElButton>
    </ElForm>
  </ElCard>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getSkillDefaults, saveSkillDefaults } from '@/api/management'
import type { Mode, SystemConfig } from '@/types/hengxin'
import type { ManagedSkill } from '@/types/management'
import { labels } from '../model'
const props = defineProps<{ skills: ManagedSkill[] }>()
const emit = defineEmits<{ saved: [] }>()
const values = ref<SystemConfig['defaultSkillIds']>({ wallpaper: null, product: null, text: null })
const loading = ref(false), saving = ref(false), ready = ref(false), error = ref('')
let alive = true
onBeforeUnmount(() => { alive = false })
const available = (mode: Mode) => props.skills.filter(s => s.mode === mode && s.status === 'available')
const unavailable = (mode: Mode) => !!values.value[mode] && !available(mode).some(s => s.id === values.value[mode])
async function load() {
  if (loading.value || saving.value) return
  loading.value = true; error.value = ''; ready.value = false
  try { const result = await getSkillDefaults(); if (alive) { values.value = result; ready.value = true } }
  catch (reason) { if (alive) error.value = reason instanceof Error ? reason.message : '默认绑定加载失败' }
  finally { if (alive) loading.value = false }
}
async function save() {
  if (!ready.value || loading.value || saving.value) return
  saving.value = true; error.value = ''
  try {
    const input = { wallpaper: values.value.wallpaper || null, product: values.value.product || null, text: values.value.text || null }
    const result = await saveSkillDefaults(input)
    if (alive) { values.value = result; ElMessage.success('模块默认已保存'); emit('saved') }
  } catch (reason) { if (alive) error.value = reason instanceof Error ? reason.message : '保存失败，请重试' }
  finally { if (alive) saving.value = false }
}
void load()
</script>
