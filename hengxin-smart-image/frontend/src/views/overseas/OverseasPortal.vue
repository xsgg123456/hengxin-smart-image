<template>
  <OverseasShell>
    <template #account><ElTag>海外业务</ElTag><ElButton text @click="$emit('switch')">切换业务</ElButton><ElButton text @click="$emit('logout')">退出登录</ElButton></template>
    <div class="layout-content"><div class="hx-page">
      <div v-if="!taskPage && !archivePage" class="hx-heading"><div><h1>{{ managementPage ? managementPages[managementPage] : '海外业务' }}</h1><p>{{ member.name }} · {{ member.roles?.map(r => memberRoles[r as MemberRole] || r).join('、') }}</p></div></div>
      <OverseasTasksPage v-if="taskPage" :api="tasksAdapter" :materials-api="materialsAdapter" :capabilities="member.capabilities || []" :refresh="refreshKey" @failure="taskFailure" />
      <OverseasArchivePage v-else-if="archivePage && member.capabilities?.includes('task.read')" :refresh="refreshKey" @failure="taskFailure" />
      <OverseasLiveManagement v-else-if="managementPage && managementPage !== 'users' && managementAllowed" :key="managementPage + refreshKey" :page="managementPage" :api="managementAdapter" @failure="managementFailure" />
      <OverseasMembers v-else-if="managing && allowed" :key="refreshKey" :adapter="adapter" @failure="fail" />
      <ElCard v-else class="art-card"><h2>企业身份已连接</h2><p class="hx-gap">当前海外角色：{{ member.roles?.map(r => memberRoles[r as MemberRole] || r).join('、') }}</p><ElAlert v-if="managementPage" title="暂无此管理页面权限" type="warning" :closable="false" /><ElButton v-if="allowed" type="primary" class="hx-gap" @click="router.push('/overseas/admin/users')">用户与角色</ElButton></ElCard>
    </div></div>
  </OverseasShell>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { identityApi, IdentityError, type Member } from '@/api/identity/auth'
import { createMembersApi, memberRoles, type MemberRole, type MembersAdapter } from '@/api/overseas/members'
import { useMenuStore } from '@/store/modules/menu'
import { useSettingStore } from '@/store/modules/setting'
import { useWorktabStore } from '@/store/modules/worktab'
import type { AppRouteRecord } from '@/types/router'
import OverseasShell from './OverseasShell.vue'
import OverseasMembers from './admin/OverseasMembers.vue'
import OverseasLiveManagement from './admin/OverseasLiveManagement.vue'
import { createManagementApi, managementPages, managementCapability, type ManagementPage, type ManagementApi } from '@/api/overseas/management'
import OverseasTasksPage from './OverseasTasksPage.vue'
import OverseasArchivePage from './OverseasArchivePage.vue'
import { createMaterialsApi, type MaterialsApi } from '@/api/overseas/materials'
import { createTasksApi, type TasksApi } from '@/api/overseas/tasks'
const props = defineProps<{ member: Member }>()
const emit = defineEmits<{ switch: []; logout: []; member: [member: Member]; failure: [reason: unknown] }>()
const route = useRoute(), router = useRouter(), menus = useMenuStore(), tabs = useWorktabStore()
const allowed = computed(() => props.member.capabilities?.includes('members.manage') === true)
const managementPage = computed(() => { const key = route.path.split('/')[3]; return route.path.startsWith('/overseas/admin/') && Object.hasOwn(managementPages, key) ? key as ManagementPage : undefined })
const managementAllowed = computed(() => !!managementPage.value && props.member.capabilities?.includes(managementCapability(managementPage.value)))
const managing = computed(() => route.path === '/overseas/admin/users')
const taskPage = computed(() => /^\/overseas\/(create|tasks)(\/|$)/.test(route.path))
const archivePage = computed(() => route.path === '/overseas/archive')
const refreshKey = ref(0)
let active = true
const home: AppRouteRecord = { path: '/overseas', name: 'overseas-home', component: () => import('./OverseasPortal.vue'), meta: { title: '海外业务', icon: 'ri:home-line' } }
watch(() => props.member.capabilities?.join(','), () => {
  const taskMenus: AppRouteRecord[] = []
  for (const [cap, path, title, icon] of [['task.create', '/overseas/create', '提交图需', 'ri:add-circle-line'], ['task.read', '/overseas/tasks', '工作流任务', 'ri:task-line'], ['task.read', '/overseas/archive', '成品库', 'ri:folder-check-line']]) if (props.member.capabilities?.includes(cap)) taskMenus.push({ path, name: path.split('/').pop(), component: () => import('./OverseasTasksPage.vue'), meta: { title, icon } })
  const adminMenus: AppRouteRecord[] = (Object.entries(managementPages) as [ManagementPage,string][]).filter(([page]) => props.member.capabilities?.includes(managementCapability(page))).map(([page,title]) => ({ path: '/overseas/admin/' + page, name: 'overseas-' + page, component: () => import('./admin/OverseasLiveManagement.vue'), meta: { title, icon: 'ri:settings-3-line' } }))
  menus.setMenuList([home, ...taskMenus, ...(adminMenus.length ? [{ path: '/overseas/admin', name: 'overseas-admin', meta: { title: '管理中心', icon: 'ri:settings-3-line' }, children: adminMenus }] : [])])
  tabs.opened = []; tabs.current = {}; tabs.keepAliveExclude = []
}, { immediate: true, flush: 'sync' })
watch(() => [route.path, props.member.capabilities?.join(',')], () => {
  const page = managementAllowed.value ? managementPage.value : undefined
  tabs.opened = []; tabs.current = {}
  tabs.openTab({ title: archivePage.value ? '成品库' : taskPage.value ? String(route.meta.title || '工作流任务') : page ? managementPages[page] : '海外业务', path: archivePage.value ? '/overseas/archive' : taskPage.value ? route.path : page ? '/overseas/admin/' + page : '/overseas', name: String(route.name || 'overseas-home'), keepAlive: false })
}, { immediate: true })
function fail(reason: unknown) {
  if (!active) return
  menus.setMenuList([home])
  // 已成功刷新到无管理能力的身份，保留真实身份首页。
  if (reason instanceof IdentityError && reason.status === 403 && !allowed.value) return
  emit('failure', reason)
}
async function authorize() {
  try {
    const member = await identityApi.overseasMe()
    if (!active) throw new IdentityError(0, '页面已离开')
    emit('member', member)
    if (!member.capabilities?.includes('members.manage')) { await router.replace('/overseas'); throw new IdentityError(403, '成员管理权限已被移除') }
  } catch (reason) { fail(reason); throw reason }
}
const api = createMembersApi()
const adapter: MembersAdapter = {
  async list(query) { await authorize(); return api.list(query) },
  async get(id) { await authorize(); return api.get(id) },
  async save(member) { await authorize(); const result = await api.save(member); await authorize(); return result }
}

async function taskFailure(reason: unknown) {
  if (!active) return
  if (reason instanceof IdentityError && reason.status === 403) {
    try { const current = await identityApi.overseasMe(); if (!active) return; emit('member', current); await router.replace('/overseas'); return }
    catch (error) { if (active) emit('failure', error); return }
  }
  fail(reason)
}
async function taskAuthorize(capability: string) {
  try {
    const current = await identityApi.overseasMe()
    if (!active) throw new IdentityError(0, '页面已离开')
    emit('member', current)
    if (!current.capabilities?.includes(capability)) throw new IdentityError(403, '业务权限已变化')
  } catch (reason) { await taskFailure(reason); throw reason }
}
const tasksApi = createTasksApi()
const tasksAdapter: TasksApi = {
  async list(query) { await taskAuthorize('task.read'); return tasksApi.list(query) },
  async get(id) { await taskAuthorize('task.read'); return tasksApi.get(id) },
  async create(draft, key) { await taskAuthorize('task.create'); return tasksApi.create(draft, key) },
  async submitMaterials(id, ids, version, key) { await taskAuthorize('task.create'); return tasksApi.submitMaterials(id, ids, version, key) },
  async assign(id, designerId, version, key) { await taskAuthorize('task.reassign'); return tasksApi.assign(id, designerId, version, key) },
  async reviewRequirements(id, decision, comment, version, key) { await taskAuthorize('task.design'); return tasksApi.reviewRequirements(id, decision, comment, version, key) },
  async resubmit(id, draft, version, key) { await taskAuthorize('task.create'); return tasksApi.resubmit(id, draft, version, key) },
  async designers(query) { await taskAuthorize(route.path === '/overseas/create' ? 'task.create' : 'task.reassign'); return tasksApi.designers(query) }
}
const materialsApi = createMaterialsApi()
const materialsAdapter: MaterialsApi = {
  async upload(file, kind, progress, signal) { await taskAuthorize('task.create'); return materialsApi.upload(file, kind, progress, signal) },
  async get(id) { await taskAuthorize('task.read'); return materialsApi.get(id) },
  async list(id) { await taskAuthorize('task.read'); return materialsApi.list(id) },
  async retry(id) { await taskAuthorize('task.create'); return materialsApi.retry(id) },
  async remove(id) { await taskAuthorize('task.create'); return materialsApi.remove(id) },
  async content(id, download, signal) { await taskAuthorize('task.read'); return materialsApi.content(id, download, signal) }
}
async function managementFailure(reason: unknown) {
  if (reason instanceof IdentityError && [401,403].includes(reason.status)) await taskFailure(reason)
}
const managementApi = createManagementApi()
async function managementCall<T>(cap: string, action: () => Promise<T>, write = false): Promise<T> {
  await taskAuthorize(cap)
  try { const result = await action(); if (write) await taskAuthorize(cap); return result }
  catch (reason) { await managementFailure(reason); throw reason }
}
const managementAdapter: ManagementApi = {
  usage: query => managementCall('stats.read', () => managementApi.usage(query)),
  jobs: query => managementCall('stats.read', () => managementApi.jobs(query)),
  skills: () => managementCall('skills.manage', () => managementApi.skills()),
  createSkill: (name, stage, files) => managementCall('skills.manage', () => managementApi.createSkill(name,stage,files), true),
  publish: (id, version, files) => managementCall('skills.manage', () => managementApi.publish(id,version,files), true),
  toggle: (id, version, enabled) => managementCall('skills.manage', () => managementApi.toggle(id,version,enabled), true),
  settings: () => managementCall('settings.manage', () => managementApi.settings()),
  saveSettings: value => managementCall('settings.manage', () => managementApi.saveSettings(value), true)
}
watch(() => useSettingStore().refresh, () => { refreshKey.value++ })
onUnmounted(() => { active = false; menus.setMenuList([]); tabs.opened = []; tabs.current = {}; tabs.keepAliveExclude = [] })
</script>
