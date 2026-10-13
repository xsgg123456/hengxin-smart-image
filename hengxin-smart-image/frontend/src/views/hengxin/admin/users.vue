<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">MEMBER ACCESS</span><h1>用户与角色</h1><p>成员归属与加入申请独立管理；姓名来自已验证企业身份，仅授权本业务权限。</p></div></div><AdminPreview />
    <ElCard class="art-card hx-section hx-admin-table-card">
      <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">MEMBERS</span><h2>国内成员目录</h2><p>只有明确审批通过的成员可以进入国内业务。</p></div></div>
      <ElTabs v-model="directory"><ElTabPane label="成员" name="members" /><ElTabPane label="加入申请" name="applications" /><ElTabPane label="历史待核对" name="legacy" /></ElTabs>
      <MembershipApplications v-if="directory === 'applications'" :adapter="managementApi" business-name="国内" :roles="roles" @failure="failure" />
      <template v-else>
      <ElAlert v-if="directory === 'legacy'" title="历史来源尚未确认，仅供核对；需本人明确申请并审批，普通编辑不能授权。" type="info" :closable="false" class="hx-gap" />
      <div class="hx-filter"><ElInput v-model="search" class="hx-search" clearable placeholder="搜索姓名或部门" aria-label="搜索成员" :disabled="loading && !data" /><ElSelect v-model="status" clearable placeholder="全部状态" style="width: 160px" aria-label="成员状态" :disabled="loading && !data"><ElOption v-for="(label,key) in statuses" :key="key" :label="label" :value="key" /></ElSelect><ElButton :loading="loading" @click="load">刷新成员</ElButton></div>
      <ElAlert v-if="error" :title="error" type="error" :closable="false"><ElButton text @click="load">重试加载</ElButton></ElAlert>
      <ArtTable height="auto" empty-height="340px" :show-table-header="false" :data="data?.items || []" :columns="columns" :loading="loading" :show-pagination="false" empty-text="暂无匹配成员"><template #role="{ row }">{{ row.role ? roles[row.role as Role] : '未分配' }}</template><template #status="{ row }"><ElTag :type="row.status === 'active' ? 'success' : 'info'">{{ statuses[row.status as keyof typeof statuses] }}</ElTag></template><template #lastLoginAt="{ row }">{{ row.lastLoginAt ? new Date(row.lastLoginAt).toLocaleString('zh-CN') : '尚未登录' }}</template><template #action="{ row }"><span v-if="directory === 'legacy'" class="hx-muted">仅供核对</span><ElButton v-else text type="primary" :disabled="loading || saving" @click="edit(row)">分配角色 / 状态</ElButton></template></ArtTable>
      <div class="hx-filter hx-gap"><span>{{ loading ? '正在读取…' : `共 ${total} ${directory === 'legacy' ? '条待核对记录' : '位成员'}` }}</span><ElPagination v-model:current-page="page" :page-size="12" :total="total" layout="prev,pager,next" :disabled="loading" /></div>
      </template>
    </ElCard>
    <ElDialog v-model="open" title="成员授权" width="480px" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving">
      <ElForm label-position="top" :disabled="saving || conflict"><ElFormItem label="成员">{{ name }}</ElFormItem><ElFormItem label="业务角色"><ElSelect v-model="form.role" clearable aria-label="业务角色"><ElOption v-for="(label,key) in roles" :key="key" :label="label" :value="key" /></ElSelect></ElFormItem><ElFormItem label="账号状态"><ElSelect v-model="form.status" aria-label="账号状态"><ElOption v-for="(label,key) in statuses" :key="key" :label="label" :value="key" /></ElSelect></ElFormItem></ElForm>
      <p class="hx-footnote">启用需要分配角色。设计和运营权限相同；角色调整在下一次请求重新校验。</p><ElAlert v-if="saveError" :title="saveError" type="error" :closable="false" />
      <template #footer><ElButton :disabled="saving" @click="open=false">取消</ElButton><ElButton v-if="conflict" @click="open=false; load()">刷新最新资料</ElButton><ElButton type="primary" :loading="saving" :disabled="conflict" @click="save">保存授权</ElButton></template>
    </ElDialog>
  </div>
</template>
<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listUsers, saveUser, managementApi } from '@/api/management'
import type { PageResult, Role, User } from '@/types/hengxin'
import type { ManagedUser, UserInput } from '@/types/management'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import AdminPreview from './AdminPreview.vue'
import MembershipApplications from '@/views/auth/MembershipApplications.vue'
import { ApiError } from '@/api/hengxin/http'
const search=ref(''), status=ref<User['status']|''>(''), page=ref(1)
const directory = ref<'members' | 'applications' | 'legacy'>('members')
const data=ref<PageResult<ManagedUser>>(), total=ref(0), loading=ref(false), error=ref(''), conflict=ref(false)
let generation=0, active=true, confirming=false
function failure(reason: unknown) { data.value=undefined; total.value=0; open.value=false; error.value=reason instanceof Error ? reason.message : '读取失败，请重试' }
async function load() {
  const epoch=++generation; data.value=undefined; error.value=''; open.value=false
  if(directory.value==='applications'){loading.value=false;return}
  loading.value=true
  try { const result=await listUsers({page:page.value,pageSize:12,search:search.value,status:status.value||undefined,directory:directory.value}); if(active&&epoch===generation){data.value=result;total.value=result.total} }
  catch(reason){if(active&&epoch===generation)failure(reason)}finally{if(active&&epoch===generation)loading.value=false}
}
function filter(){ if(page.value!==1)page.value=1;else void load() }
watch([search,status,directory],filter); watch(page,load)
const roles:Record<Role,string>={super_admin:'超级管理员',design_manager:'设计主管',designer:'设计人员',operator:'运营人员'},statuses={pending:'待授权',active:'启用',disabled:'禁用'}
const form=reactive<UserInput>({id:'',role:null,status:'pending'}),open=ref(false),name=ref(''),saving=ref(false),saveError=ref('')
function edit(user:ManagedUser){if(directory.value==='legacy'||user.directoryState==='legacy_unconfirmed')return;Object.assign(form,{id:user.id,role:user.role,status:user.status});name.value=user.name;saveError.value='';conflict.value=false;open.value=true}
async function save(){
  if(saving.value||conflict.value)return
  if(form.status==='active'&&!form.role){saveError.value='启用账号前请选择业务角色';return}
  saving.value=true;saveError.value=''
  try{
    if(form.status!=='active'||!form.role){confirming=true;try{await ElMessageBox.confirm(`确认撤销「${name.value}」的国内访问权限？当前国内会话将失效。`,'确认撤销权限',{type:'warning',confirmButtonText:'确认',cancelButtonText:'取消'})}catch{return}finally{confirming=false}}
    if(!active)return
    await saveUser({...form,role:form.role||null});if(!active)return
    open.value=false;ElMessage.success('成员授权已更新');await load()
  }catch(e){if(!active)return;if(e instanceof ApiError&&[401,403].includes(e.status))failure(e);else{saveError.value=e instanceof Error?e.message:'保存失败，请重试';conflict.value=e instanceof ApiError&&e.status===409}}finally{saving.value=false}
}
const columns=[{prop:'name',label:'姓名',minWidth:120},{prop:'department',label:'部门',minWidth:120},{prop:'role',label:'角色',minWidth:130,useSlot:true},{prop:'status',label:'状态',width:100,useSlot:true},{prop:'lastLoginAt',label:'最近登录',minWidth:180,useSlot:true},{prop:'action',label:'操作',width:165,useSlot:true}]
onMounted(load)
onUnmounted(()=>{active=false;++generation;if(confirming)ElMessageBox.close()})
</script>
