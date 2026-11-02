<template>
  <ElDialog :model-value="true" :title="mode === 'add' ? `添加 Skill 到 ${platform}` : ids.length > 1 ? `批量设置平台 · ${ids.length} 个 Skill` : '编辑适用平台'" width="min(700px,94vw)" append-to-body :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving" @close="!saving && $emit('close')">
    <ElAlert v-if="error" :title="error" type="error" :closable="false" />
    <template v-if="mode === 'add'">
      <p class="dialog-note">选择已安装的 Skill 加入当前平台，已有的其他平台归属保留。</p>
      <ElInput v-model="search" placeholder="搜索要添加的 Skill" aria-label="搜索待添加 Skill" clearable />
      <ElCheckboxGroup v-model="additions" class="add-list" :disabled="saving">
        <ElCheckbox v-for="skill in candidates" :key="skill.id" :value="skill.id"><span>{{ skill.displayName }}</span><small>{{ skill.platforms.length ? `已属于：${skill.platforms.join('、')}` : '未分组' }} · {{ skill.enabled ? '已开启' : '已关闭' }}</small></ElCheckbox>
      </ElCheckboxGroup>
      <ElEmpty v-if="!candidates.length" description="暂无可添加的 Skill" :image-size="60" />
      <p v-if="hiddenAdditions" class="dialog-note">另有 {{ hiddenAdditions }} 个已选 Skill 被搜索隐藏，仍会一并添加。</p>
    </template>
    <template v-else>
      <p class="dialog-skill">{{ ids.length === 1 ? skills.find(s => s.id === ids[0])?.displayName : '保存后，所选 Skill 将统一使用下面的平台归属。' }}</p>
      <p class="dialog-note">可同时选择多个平台。未选择平台时，Skill 归入“未分组”，不出现在工作台。</p>
      <ElCheckboxGroup v-model="draftPlatforms" class="platform-checks" :disabled="saving"><ElCheckbox v-for="p in platforms" :key="p.value" :value="p.value" border>{{ p.label }}</ElCheckbox></ElCheckboxGroup>
      <div class="dialog-link-row"><ElButton text size="small" :disabled="saving" @click="draftPlatforms = platforms.map(p => p.value)">选择全部平台</ElButton><ElButton text size="small" :disabled="saving" @click="draftPlatforms = []">清空选择</ElButton></div>
      <p class="dialog-note">只调整平台归属，不修改 Skill 内容、字体和执行逻辑。</p>
    </template>
    <template #footer><ElButton v-if="!canManage && refreshPlatforms" :loading="saving" @click="refresh">刷新最新目录</ElButton><ElButton :disabled="saving" @click="$emit('close')">取消</ElButton><ElButton type="primary" :loading="saving" :disabled="!canManage || (mode === 'add' && !additions.length)" @click="save">{{ mode === 'add' ? `添加到 ${platform}（${additions.length}）` : '保存平台设置' }}</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { OVERSEAS_PLATFORMS as platforms } from '../platforms'
import type { ManagedSkill, SkillPlatformUpdate } from '@/api/overseas/management'
const props = defineProps<{ skills: ManagedSkill[]; ids: string[]; mode: 'edit' | 'add'; platform: string; canManage: boolean; savePlatforms: (items: SkillPlatformUpdate[]) => Promise<boolean>; error: string; refreshPlatforms?: () => Promise<void> }>()
const emit = defineEmits<{ close: [] }>()
const search = ref(''), additions = ref<string[]>([]), saving = ref(false)
const draftPlatforms = ref(props.ids.length === 1 ? [...(props.skills.find(s => s.id === props.ids[0])?.platforms || [])] : [])
let versions = new Map(props.skills.map(s => [s.id, s.version]))
const candidates = computed(() => props.skills.filter(s => !s.platforms.includes(props.platform) && `${s.displayName} ${s.name} ${s.description}`.toLowerCase().includes(search.value.trim().toLowerCase())))
const hiddenAdditions = computed(() => additions.value.filter(id => !candidates.value.some(s => s.id === id)).length)
async function refresh() {
  if (saving.value || !props.refreshPlatforms) return
  saving.value = true
  try { await props.refreshPlatforms(); await nextTick(); versions = new Map(props.skills.map(s => [s.id, s.version])) }
  finally { saving.value = false }
}
async function save() {
  if (saving.value || !props.canManage) return
  const chosen = props.mode === 'add' ? additions.value : props.ids
  if (!chosen.length) return
  const items = chosen.map(id => {
    const skill = props.skills.find(s => s.id === id)
    return { id, version: versions.get(id) || 0, platforms: props.mode === 'add' ? Array.from(new Set([...(skill?.platforms || []), props.platform])) : [...draftPlatforms.value] }
  })
  saving.value = true
  try {
    if (await props.savePlatforms(items)) emit('close')
    else versions = new Map(props.skills.map(s => [s.id, s.version]))
  } finally { saving.value = false }
}
</script>
<style scoped>
.dialog-note { font-size:12px; color:var(--art-gray-500); line-height:1.8; }
.dialog-skill { font-weight:600; line-height:1.7; margin:0 0 12px; }
.platform-checks { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; margin-top:20px; }
.platform-checks .el-checkbox { margin:0; height:46px; width:100%; }
.dialog-link-row { display:flex; gap:12px; margin:10px 0 20px; }
.add-list { display:flex; flex-direction:column; max-height:360px; overflow:auto; margin-top:14px; }
.add-list .el-checkbox { height:auto; min-height:62px; padding:12px 0; margin:0; border-bottom:1px solid var(--default-border); }
.add-list :deep(.el-checkbox__label) { white-space:normal; overflow-wrap:anywhere; }
.add-list small { display:block; margin-top:6px; color:var(--art-gray-500); }
@media(max-width:640px) { .platform-checks { grid-template-columns:1fr; } }
</style>
