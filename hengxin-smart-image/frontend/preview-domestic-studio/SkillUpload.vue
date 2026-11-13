<template>
  <ElDialog :model-value="true" title="上传 Skill 文件夹" width="min(760px,94vw)" :close-on-click-modal="false" :show-close="!scanning" :close-on-press-escape="!scanning" @close="$emit('close')">
    <p>一次拖入一个完整文件夹，包含根目录 SKILL.md。新增默认关闭且未绑定工作台；同名更新保留绑定和开关。</p>
    <div class="skills-folder-drop" :aria-busy="scanning" @dragover.prevent @drop.prevent="drop">{{ scanning ? `正在完整扫描 · ${scanned} 项` : '将完整 Skill 文件夹拖到这里（包含空目录）' }}</div>
    <p class="skills-muted">单文件 64 MiB，整包 256 MiB，最多 1000 个文件、2000 个目录及文件条目。</p>
    <ElAlert v-if="error" :title="error" type="error" :closable="false" />
    <template v-if="folder"><p class="skills-upload-name"><strong>{{ folder.displayName }}</strong> · {{ folder.name }}</p><p>{{ folder.description }}</p><p class="skills-muted">{{ folder.files.size }} 个文件 · {{ Object.keys(folder.entries).length - folder.files.size }} 个目录 · {{ (folder.totalBytes / 1024 / 1024).toFixed(2) }} MiB</p><div class="skills-upload-tree"><ElTree :data="folderTree(folder)" node-key="path" :default-expanded-keys="['']" /></div>
      <ElAlert v-if="identical" title="同名同内容，无需重复导入" type="success" :closable="false" />
      <template v-else-if="existing"><ElAlert title="同名 Skill 内容不同，请核对差异后确认更新。" type="warning" :closable="false" /><div v-for="section in differences" :key="section.label" class="skills-upload-diff"><strong>{{ section.label }}（{{ section.paths.length }}）</strong><p v-for="path in section.paths" :key="path">{{ path }}</p></div></template>
    </template>
    <p class="skills-muted">本地交互预览，文件仅保留在当前页面内存，尚未安装到真实执行器。</p>
    <template #footer><ElButton :disabled="scanning" @click="$emit('close')">关闭</ElButton><ElButton v-if="folder" type="primary" :disabled="scanning || identical" @click="install">{{ existing ? '确认更新同名 Skill' : '导入 Skill（默认关闭）' }}</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { droppedRoot, scanFolder, folderTree, sha256, type ScannedFolder } from '@/views/overseas/admin/skill-folder-read'
import { skills, saveSkill, type DomesticSkill } from './skills-state'
const emit = defineEmits<{ close: []; saved: [] }>()
const scanning = ref(false), scanned = ref(0), error = ref(''), folder = ref<ScannedFolder>(), existing = ref<DomesticSkill>()
const added = ref<string[]>([]), modified = ref<string[]>([]), removed = ref<string[]>([])
const differences = computed(() => [{ label: '新增', paths: added.value }, { label: '修改', paths: modified.value }, { label: '删除', paths: removed.value }])
const identical = computed(() => !!existing.value && !added.value.length && !modified.value.length && !removed.value.length)
async function drop(event: DragEvent) {
  if (scanning.value || !event.dataTransfer) return
  scanning.value = true; scanned.value = 0; error.value = ''; folder.value = undefined; existing.value = undefined
  try {
    const value = await scanFolder(droppedRoot(event.dataTransfer))
    const found = skills.find(skill => skill.name === value.name)
    added.value = []; modified.value = []; removed.value = []
    if (found) {
      const originals = new Map(found.files.map(file => [file.path, file.blob]))
      for (const [path, entry] of Object.entries(value.entries)) {
        if (!originals.has(path)) added.value.push(path)
        else if ('sha256' in entry) { const old = originals.get(path); if (!old || await sha256(await old.arrayBuffer()) !== entry.sha256) modified.value.push(path) }
      }
      removed.value = found.files.filter(file => !(file.path in value.entries)).map(file => file.path)
    }
    existing.value = found; folder.value = value
  } catch (reason) { error.value = reason instanceof Error ? reason.message : '文件夹读取失败' }
  finally { scanning.value = false }
}
async function install() {
  if (!folder.value || scanning.value || identical.value) return
  scanning.value = true
  try { const source = await folder.value.files.get('SKILL.md')!.text(); saveSkill(existing.value?.id, source, Object.keys(folder.value.entries).map(path => ({ path, blob: folder.value!.files.get(path) }))); ElMessage.success(existing.value ? 'Skill 已更新，保留原绑定与开关' : 'Skill 已导入，默认关闭'); emit('saved') }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '导入失败' }
  finally { scanning.value = false }
}
</script>
