<template>
  <ElDialog v-model="visible" :title="templateId ? '配置模板' : '新建套图模板'" width="680px" destroy-on-close
    :show-close="!busy" :close-on-click-modal="!busy" :close-on-press-escape="!busy" :before-close="beforeClose" @closed="emit('close')">
    <ElAlert v-if="loadError" :title="loadError" type="error" :closable="false" show-icon>
      <ElButton text type="primary" :disabled="loading" @click="initialize">重试加载模板</ElButton>
    </ElAlert>
    <ElForm v-if="!loadError" v-loading="loading" label-position="top" :disabled="busy">
      <ElFormItem label="模板名称" required><ElInput v-model="name" maxlength="60" placeholder="给这套模板起个容易找到的名字" /></ElFormItem>
      <ElFormItem label="适用功能" required>
        <ElRadioGroup v-model="formMode" @change="changeMode"><ElRadioButton value="wallpaper">替换壁纸</ElRadioButton><ElRadioButton value="product">替换商品</ElRadioButton></ElRadioGroup>
      </ElFormItem>
      <ElFormItem label="处理 Skill">
        <ElSelect v-model="skillId" clearable placeholder="使用模块默认 Skill" :loading="skillsLoading" :disabled="busy || skillsLoading" @change="changeSkill">
          <ElOption v-if="unavailableBinding" :value="skillId" :label="`${originalSkill || skillId}（原绑定版本不可用）`" disabled />
          <ElOption v-for="skill in availableSkills" :key="skill.id" :value="skill.id" :label="`${skill.name} · v${skill.version}${skill.isDefault ? '（默认）' : ''}`" />
        </ElSelect>
        <p v-if="skillsError" class="hx-muted">{{ skillsError }} <ElButton text type="primary" :disabled="busy || skillsLoading" @click="loadSkills">重试加载 Skill</ElButton></p>
        <p v-else-if="unavailableBinding" class="hx-muted">原专用版本不可用，可保留绑定存草稿；选择可用版本或清空后使用模块默认。</p>
        <p v-else-if="!skillId" class="hx-muted">{{ effectiveSkill ? `保存时使用模块默认：${effectiveSkill.name} · v${effectiveSkill.version}` : '模块暂无可用默认 Skill，可先保存草稿。' }}</p>
      </ElFormItem>
      <ElFormItem label="模板图片" required><ImageUpload v-if="!loading" v-model="pictures" :mode="formMode" :disabled="saving" label="模板图片" sortable :example-count="4" example-label="使用示例套图" @blocked="uploadBlocked = $event" /></ElFormItem>
      <ElFormItem label="备注"><ElInput v-model="notes" type="textarea" :rows="2" maxlength="1000" show-word-limit placeholder="可选，补充这套模板的使用说明" /></ElFormItem>
      <ElFormItem label="模板状态"><ElSwitch v-model="enabled" active-text="可使用" inactive-text="停用 / 草稿" :disabled="busy || !validSkill" /></ElFormItem>
      <p class="hx-muted">保存时固定实际 Skill 版本和图片顺序；缺少可用 Skill 时保存为草稿。</p>
    </ElForm>
    <ElAlert v-if="saveError" :title="saveError" type="error" :closable="false" show-icon />
    <template #footer>
      <ElButton :disabled="busy" @click="visible = false">取消</ElButton>
      <ElButton type="primary" :loading="saving" :disabled="busy || !!loadError || uploadBlocked || skillsLoading || !!skillsError" @click="save">{{ validSkill ? '保存模板' : '保存草稿' }}</ElButton>
    </template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getTemplate, saveTemplate } from '@/api/templates'
import { listSkills } from '@/api/skills'
import { isMockMode } from '@/api/hengxin/client'
import type { Mode, Picture, SkillVersion } from '@/types/hengxin'
import ImageUpload from './ImageUpload.vue'

const props = defineProps<{ templateId?: string }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const visible = ref(true), loading = ref(false), saving = ref(false), skillsLoading = ref(false)
const loadError = ref(''), saveError = ref(''), skillsError = ref(''), uploadBlocked = ref(false)
const name = ref(''), formMode = ref<Mode>('wallpaper'), skillId = ref(''), originalSkill = ref(''), notes = ref('')
const pictures = ref<Picture[]>([]), enabled = ref(true), version = ref<number>()
const skillVersions = ref<SkillVersion[]>([])
const busy = computed(() => loading.value || saving.value)
const availableSkills = computed(() => skillVersions.value.filter(skill => skill.mode === formMode.value && skill.status === 'available'))
const effectiveSkill = computed(() => availableSkills.value.find(skill => skillId.value ? skill.id === skillId.value : skill.isDefault))
const validSkill = computed(() => !!effectiveSkill.value)
const unavailableBinding = computed(() => !!skillId.value && !skillsLoading.value && !validSkill.value)
let alive = true
onBeforeUnmount(() => { alive = false })
function errorMessage(reason: unknown, fallback: string) { return reason instanceof Error ? reason.message : fallback }
function beforeClose(done: () => void) { if (!busy.value) done() }
function changeMode() { skillId.value = ''; originalSkill.value = ''; enabled.value = validSkill.value }
function changeSkill() { enabled.value = validSkill.value }
async function loadSkills() {
  skillsLoading.value = true
  skillsError.value = ''
  try { const result = await listSkills(); if (alive) skillVersions.value = result }
  catch (reason) { if (alive) { skillVersions.value = []; skillsError.value = errorMessage(reason, 'Skill 加载失败，请重试') } }
  finally { if (alive) skillsLoading.value = false }
}
async function initialize() {
  if (loading.value) return
  loading.value = true
  loadError.value = ''
  const skillRequest = loadSkills()
  try {
    if (props.templateId) {
      const template = await getTemplate(props.templateId)
      if (!alive) return
      name.value = template.name; formMode.value = template.mode; notes.value = template.notes
      pictures.value = template.images.map(picture => ({ ...picture }))
      skillId.value = template.skillBinding === 'module_default' ? '' : template.skillVersionId || ''; originalSkill.value = template.skill
      enabled.value = template.active; version.value = template.version
    }
    await skillRequest
    if (alive && !props.templateId) {
      enabled.value = validSkill.value
    }
  } catch (reason) { if (alive) loadError.value = errorMessage(reason, '模板加载失败，请重试') }
  finally { await skillRequest; if (alive) loading.value = false }
}
async function save() {
  if (busy.value || uploadBlocked.value || skillsLoading.value || skillsError.value || loadError.value) return
  saveError.value = ''
  if (!name.value.trim() || !pictures.value.length) { saveError.value = '请填写模板名称并添加图片'; return }
  if (pictures.value.length > 20) { saveError.value = '每组模板最多 20 张图片'; return }
  saving.value = true
  try {
    await saveTemplate({ id: props.templateId, name: name.value.trim(), mode: formMode.value,
      images: pictures.value.map(picture => ({ ...picture })), skillVersionId: skillId.value || null,
      active: validSkill.value && enabled.value, notes: notes.value.trim(), expectedVersion: version.value })
    ElMessage.success(isMockMode ? '模板已保存到模拟工作区' : '模板已保存')
    emit('saved')
  } catch (reason) { saveError.value = errorMessage(reason, '保存失败，表单已保留，请重试') }
  finally { saving.value = false }
}
void initialize()
</script>
