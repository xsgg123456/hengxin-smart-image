<template>
  <OverseasShell>
    <template #account><ElTag>海外业务</ElTag><ElButton text @click="$emit('switch')">切换业务</ElButton><ElButton text @click="$emit('logout')">退出登录</ElButton></template>
    <div class="layout-content"><div class="hx-page">
      <div v-if="!taskPage" class="hx-heading"><div><h1>{{ managing ? '用户与角色' : '海外业务' }}</h1><p>{{ member.name }} · {{ member.roles?.map(r => memberRoles[r as MemberRole] || r).join('、') }}</p></div></div>
      <OverseasTasksPage v-if="taskPage" :api="tasksAdapter" :materials-api="materialsAdapter" :capabilities="member.capabilities || []" :refresh="refreshKey" @failure="taskFailure" />
      <OverseasMembers v-else-if="managing && allowed" :key="refreshKey" :adapter="adapter" @failure="fail" />
      <ElCard v-else class="art-card"><h2>企业身份已连接</h2><p class="hx-gap">当前海外角色：{{ member.roles?.map(r => memberRoles[r as MemberRole] || r).join('、') }}</p><ElAlert v-if="managing" title="暂无成员管理权限" type="warning" :closable="false" /><ElButton v-if="allowed" type="primary" class="hx-gap" @click="router.push('/overseas/admin/users')">用户与角色</ElButton></ElCard>
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
import OverseasTasksPage from './OverseasTasksPage.vue'
import { createMaterialsApi, type MaterialsApi } from '@/api/overseas/materials'
import { createTasksApi, type TasksApi } from '@/api/overseas/tasks'
const props = defineProps<{ member: Member }>()
const emit = defineEmits<{ switch: []; logout: []; member: [member: Member]; failure: [reason: unknown] }>()
const route = useRoute(), router = useRouter(), menus = useMenuStore(), tabs = useWorktabStore()
const allowed = computed(() => props.member.capabilities?.includes('members.manage') === true)
const managing = computed(() => route.path === '/overseas/admin/users')
const taskPage = computed(() => /^\/overseas\/(create|tasks)(\/|$)/.test(route.path))
const refreshKey = ref(0)
let active = true
const home: AppRouteRecord = { path: '/overseas', name: 'overseas-home', component: () => import('./OverseasPortal.vue'), meta: { title: '海外业务', icon: 'ri:home-line' } }
watch(() => props.member.capabilities?.join(','), () => {
  const value = allowed.value
  const taskMenus: AppRouteRecord[] = []
  for (const [cap, path, title, icon] of [['task.create', '/overseas/create', '提交图需', 'ri:add-circle-line'], ['task.read', '/overseas/tasks', '工作流任务', 'ri:task-line']]) if (props.member.capabilities?.includes(cap)) taskMenus.push({ path, name: path.split('/').pop(), component: () => import('./OverseasTasksPage.vue'), meta: { title, icon } })
  menus.setMenuList(value ? [home, ...taskMenus, { path: '/overseas/admin', name: 'overseas-admin', meta: { title: '管理中心', icon: 'ri:settings-3-line' }, children: [{ path: '/overseas/admin/users', name: 'overseas-users', component: () => import('./admin/OverseasMembers.vue'), meta: { title: '用户与角色', icon: 'ri:group-line' } }] }] : [home, ...taskMenus])
  tabs.opened = []; tabs.current = {}; tabs.keepAliveExclude = []
}, { immediate: true, flush: 'sync' })
watch(() => [route.path, allowed.value], () => {
  const management = managing.value && allowed.value
  tabs.opened = []; tabs.current = {}
  tabs.openTab({ title: taskPage.value ? String(route.meta.title || '工作流任务') : management ? '用户与角色' : '海外业务', path: taskPage.value ? route.path : management ? '/overseas/admin/users' : '/overseas', name: taskPage.value ? String(route.name) : management ? 'overseas-users' : 'overseas-home', keepAlive: false })
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
watch(() => useSettingStore().refresh, () => { refreshKey.value++ })
onUnmounted(() => { active = false; menus.setMenuList([]); tabs.opened = []; tabs.current = {}; tabs.keepAliveExclude = [] })
</script>
