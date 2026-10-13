<template>
  <div>
    <OverseasCreate v-if="creating && canCreate" v-model="draft" :allowed="canCreate" :busy="saving" @back="router.push('/overseas/tasks')">
      <template #designer><ElFormItem label="负责设计" required><DesignerPicker :api="api" v-model="draft.designerId" :disabled="saving" @failure="failure" /></ElFormItem></template>
      <template #after><OverseasMaterialsPanel :key="panelEpoch" v-model="materials" :api="materialsApi" :editable="canCreate" :disabled="saving" @busy="materialsBusy = $event" @failure="failure" /><ElAlert v-if="error" :title="error" type="error" :closable="false" /><div class="hx-filter"><ElButton type="primary" :loading="saving" :disabled="!ready || materialsBusy" @click="create">提交图需</ElButton></div></template>
    </OverseasCreate>
    <template v-else-if="detailId">
      <div v-if="!editingRequirements" class="hx-heading"><div><h1>{{ preReview ? '图需审核' : detail?.name || '任务详情' }}</h1><p v-if="detail">{{ taskStatuses[detail.status] }}</p></div><ElButton @click="router.push('/overseas/tasks')">返回任务列表</ElButton></div>
      <p v-if="busy" role="status">正在加载任务…</p>
      <ElAlert v-if="error" :title="error" type="error" :closable="false" />
      <ElButton v-if="!editingRequirements" :loading="busy" @click="load">刷新任务详情</ElButton>
      <OverseasRequirementsResubmit v-if="detail && preReview && editingRequirements" :key="detail.id" :task="detail" :materials="materials" :api="api" :materials-api="materialsApi" @failure="failure" @refresh="refreshDetail" @close="editingRequirements = false" @changed="requirementsChanged" />
      <OverseasRequirementsReview v-else-if="detail && preReview" :key="detail.id" :task="detail" :files="materials" :api="api" :materials-api="materialsApi" @failure="failure" @refresh="refreshDetail" @edit="editingRequirements = true" @changed="requirementsChanged">
        <template #assignment>
          <div v-if="detail.capabilities.includes('task.reassign')" class="hx-gap">
            <ElButton v-if="!assigning" @click="assigning = true">改派设计</ElButton>
            <template v-else><DesignerPicker :api="api" v-model="designerId" :disabled="saving" @failure="failure" /><div class="hx-filter hx-gap"><ElButton type="primary" :disabled="!designerId || designerId === detail.designer.id" :loading="saving" @click="assign">确认改派</ElButton><ElButton :disabled="saving" @click="assigning = false">取消</ElButton></div></template>
          </div>
        </template>
      </OverseasRequirementsReview>
      <OverseasTaskInfo v-if="detail && !preReview" :task="detail" class="hx-gap">
        <template #assignment>
          <div v-if="detail.capabilities.includes('task.reassign')" class="hx-gap">
            <ElButton v-if="!assigning" @click="assigning = true">改派设计</ElButton>
            <template v-else><h3>改派负责设计</h3><DesignerPicker :key="detail.version" :api="api" v-model="designerId" :disabled="saving" @failure="failure" /><div class="hx-filter hx-gap"><ElButton type="primary" :disabled="!designerId || designerId === detail.designer.id" :loading="saving" @click="assign">确认改派</ElButton><ElButton :disabled="saving" @click="assigning = false">取消</ElButton></div></template>
          </div>
        </template>
        <template #materials>
          <OverseasMaterialsPanel :key="`${detail.id}-${detail.version}`" v-model="materials" :api="materialsApi" :editable="detail.status === 'created' && detail.capabilities.includes('task.materials.submit')" :disabled="saving" @busy="materialsBusy = $event" @failure="failure" />
          <ElButton v-if="detail.status === 'created' && detail.capabilities.includes('task.materials.submit')" class="hx-gap" type="primary" :loading="saving" :disabled="!ready || materialsBusy" @click="submitMaterials">提交补充资料</ElButton>
        </template>
      </OverseasTaskInfo>
      <OverseasPlans v-if="detail && !preReview" :key="detail.id" :task="detail" :refresh="plansRefresh" @failure="failure" @changed="updateDetail" @refresh="refreshDetail" />
      <OverseasPictureResults v-if="detail && !preReview" :key="detail.id" :task="detail" :refresh="plansRefresh" @failure="failure" @changed="updateDetail" @refresh="refreshDetail" />
      <OverseasExecution v-if="detail && !preReview" :key="detail.id" :task-id="detail.id" :can-cancel="detail.capabilities.includes('task.design')" @failure="failure" @changed="refreshDetail" />
    </template>
    <OverseasWorkspace v-else-if="!creating && canRead" v-model:query="search" v-model:status="status" v-model:scope="scope" :tasks="tasks" :allowed="canCreate" :total="total" :busy="busy" @create="router.push('/overseas/create')" @open="router.push(`/overseas/tasks/${$event}`)" @refresh="load">
      <template #feedback><p v-if="busy" role="status">正在加载任务…</p><ElAlert v-if="error" :title="error" type="error" :closable="false" /></template>
      <template #pagination><ElPagination v-if="!busy && !error" class="hx-gap" layout="prev, pager, next" :current-page="page" :page-size="20" :total="total" :disabled="busy" @current-change="page = $event" /></template>
    </OverseasWorkspace>
    <ElAlert v-else title="暂无此功能权限" type="warning" :closable="false" />
  </div>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IdentityError } from '@/api/identity/request'
import { cleanDraft, createRequestKeys, emptyTaskDraft, taskError, taskStatuses, validateDraft, type TaskDetail, type TaskSummary, type TasksApi } from '@/api/overseas/tasks'
import OverseasRequirementsReview from './OverseasRequirementsReview.vue'
import OverseasRequirementsResubmit from './OverseasRequirementsResubmit.vue'
import OverseasCreate from './OverseasCreate.vue'
import OverseasWorkspace from './OverseasWorkspace.vue'
import OverseasTaskInfo from './OverseasTaskInfo.vue'
import OverseasExecution from './OverseasExecution.vue'
import OverseasPlans from './OverseasPlans.vue'
import OverseasPictureResults from './OverseasPictureResults.vue'
import DesignerPicker from './DesignerPicker.vue'
import OverseasMaterialsPanel from './OverseasMaterialsPanel.vue'
import { readyMaterialIds, type Material, type MaterialsApi } from '@/api/overseas/materials'
const props = defineProps<{ api: TasksApi; materialsApi: MaterialsApi; capabilities: string[]; refresh: number }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const route = useRoute(), router = useRouter(), creating = computed(() => route.path === '/overseas/create'), detailId = computed(() => typeof route.params.id === 'string' ? route.params.id : '')
const canCreate = computed(() => props.capabilities.includes('task.create')), canRead = computed(() => props.capabilities.includes('task.read'))
const draft = ref(emptyTaskDraft()), tasks = ref<TaskSummary[]>([]), detail = ref<TaskDetail>(), total = ref(0), page = ref(1)
const search = ref(''), scope = ref('all'), status = ref(''), error = ref(''), busy = ref(false), saving = ref(false), assigning = ref(false), designerId = ref('')
const editingRequirements = ref(false)
const preReview = computed(() => detail.value && ['pending_review', 'returned'].includes(detail.value.status))
const panelEpoch = ref(0), plansRefresh = ref(0)
const materials = ref<Material[]>([]), materialsBusy = ref(false)
const ready = computed(() => { try { readyMaterialIds(materials.value); return true } catch { return false } })
const materialKeys = createRequestKeys()
const createKeys = createRequestKeys(), assignKeys = createRequestKeys()
let generation = 0, timer: ReturnType<typeof setTimeout> | undefined, active = true
function failure(reason: unknown) { ++generation; materials.value = []; materialsBusy.value = false; tasks.value = []; detail.value = undefined; total.value = 0; emit('failure', reason) }
function failed(reason: unknown) { error.value = taskError(reason); if (reason instanceof IdentityError && [401, 403].includes(reason.status)) failure(reason) }
async function load() {
  editingRequirements.value = false
  const current = ++generation; panelEpoch.value++; materials.value = []; materialsBusy.value = false; tasks.value = []; detail.value = undefined; busy.value = false; error.value = ''; assigning.value = false; designerId.value = ''
  if (creating.value || !canRead.value) return
  busy.value = true
  try {
    if (detailId.value) { const value = await props.api.get(detailId.value); if (current === generation) { const files = await props.materialsApi.list(value.id); if (current === generation) { detail.value = value; materials.value = files } } }
    else { const value = await props.api.list({ search: search.value.trim(), scope: scope.value, status: status.value, page: page.value, pageSize: 20 }); if (current === generation) { tasks.value = value.items; total.value = value.total; if (!value.items.length && page.value > 1 && value.total > 0) page.value = Math.ceil(value.total / 20) } }
  } catch (reason) { if (current === generation) { total.value = 0; failed(reason) } }
  finally { if (current === generation) busy.value = false }
}
function updateDetail(value: TaskDetail) { if (detail.value?.id === value.id && value.version >= detail.value.version) detail.value = value }
async function requirementsChanged(value: TaskDetail) {
  updateDetail(value); editingRequirements.value = false
  const current = generation
  try { const files = await props.materialsApi.list(value.id); if (active && current === generation && detail.value?.id === value.id) materials.value = files }
  catch (reason) { if (active && current === generation) failed(reason) }
}
async function refreshDetail() {
  const id = detail.value?.id, current = generation
  if (!id) return
  try { const value = await props.api.get(id); if (active && current === generation) { updateDetail(value); plansRefresh.value++ } }
  catch (reason) { if (active && current === generation) failed(reason) }
}
async function create() {
  if (saving.value || materialsBusy.value || !ready.value || !canCreate.value) return
  try { validateDraft(draft.value) } catch (reason) { error.value = taskError(reason); return }
  const body = cleanDraft({ ...draft.value, materialIds: readyMaterialIds(materials.value) }), key = createKeys.for(body), origin = route.path, current = generation
  saving.value = true; error.value = ''
  try { const value = await props.api.create(body, key); if (!active || current !== generation || !canCreate.value) return; createKeys.clear(); draft.value = emptyTaskDraft(); if (route.path !== origin) return; await router.push(`/overseas/tasks/${value.id}`) }
  catch (reason) { if (active && current === generation) failed(reason) }
  finally { saving.value = false }
}
async function submitMaterials() {
  if (saving.value || materialsBusy.value || !ready.value || !detail.value?.capabilities.includes('task.materials.submit')) return
  const task = detail.value, ids = readyMaterialIds(materials.value), current = generation
  const key = materialKeys.for({ id: task.id, materialIds: ids, version: task.version })
  saving.value = true; error.value = ''
  try { await props.api.submitMaterials(task.id, ids, task.version, key); if (!active || current !== generation) return; materialKeys.clear(); await load() }
  catch (reason) { if (active && current === generation) { if (reason instanceof IdentityError && reason.status === 409) await load(); failed(reason) } }
  finally { saving.value = false }
}
async function assign() {
  if (saving.value || !detail.value || !designerId.value || !detail.value.capabilities.includes('task.reassign')) return
  const current = detail.value, chosen = designerId.value, key = assignKeys.for({ id: current.id, designerId: chosen, version: current.version })
  saving.value = true; error.value = ''
  try { const value = await props.api.assign(current.id, chosen, current.version, key); if (!active || detailId.value !== current.id) return; detail.value = value; assigning.value = false; designerId.value = ''; assignKeys.clear() }
  catch (reason) {
    if (!active || detailId.value !== current.id) return
    if (reason instanceof IdentityError && reason.status === 409) { await load(); if (detail.value) { error.value = taskError(reason); assigning.value = true } }
    else if (reason instanceof IdentityError && [401, 403].includes(reason.status)) failed(reason)
    else { error.value = taskError(reason); detail.value = undefined }
  } finally { saving.value = false }
}
watch([() => route.path, () => props.refresh, () => props.capabilities.join(',')], load, { immediate: true })
watch([scope, status], () => { if (page.value === 1) void load(); else page.value = 1 })
watch(page, load)
watch(search, () => { ++generation; tasks.value = []; total.value = 0; clearTimeout(timer); timer = setTimeout(() => { if (page.value === 1) void load(); else page.value = 1 }, 250) })
onUnmounted(() => { active = false; materials.value = []; ++generation; clearTimeout(timer) })
</script>
<style scoped>
.hx-heading { flex-wrap: wrap; }
.hx-heading > div { min-width: 0; overflow-wrap: anywhere; }
</style>
