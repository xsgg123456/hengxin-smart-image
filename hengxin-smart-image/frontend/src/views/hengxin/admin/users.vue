<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">MEMBER ACCESS</span><h1>用户与角色</h1><p>为企业成员分配业务角色；新成员保持待授权，不自动获得访问权限。</p></div></div><AdminPreview />
    <ElCard class="art-card hx-section">
      <div class="hx-filter"><ElInput v-model="search" class="hx-search" clearable placeholder="搜索姓名或部门" aria-label="搜索成员" /><ElSelect v-model="status" clearable placeholder="全部状态" style="width: 160px" aria-label="成员状态"><ElOption v-for="(label,key) in statuses" :key="key" :label="label" :value="key" /></ElSelect><ElButton :loading="loading" @click="load">刷新成员</ElButton></div>
      <ElAlert v-if="error" :title="error" type="error" :closable="false"><ElButton text @click="load">重试加载</ElButton></ElAlert>
      <ArtTable :data="data?.items || []" :columns="columns" :loading="loading" :show-pagination="false" empty-text="暂无匹配成员"><template #role="{ row }">{{ row.role ? roles[row.role as Role] : '未分配' }}</template><template #status="{ row }"><ElTag :type="row.status === 'active' ? 'success' : 'info'">{{ statuses[row.status as keyof typeof statuses] }}</ElTag></template><template #lastLoginAt="{ row }">{{ row.lastLoginAt ? new Date(row.lastLoginAt).toLocaleString('zh-CN') : '尚未登录' }}</template><template #action="{ row }"><ElButton text type="primary" @click="edit(row)">分配角色 / 状态</ElButton></template></ArtTable>
      <ElPagination v-model:current-page="page" class="hx-gap" :page-size="12" :total="data?.total || 0" layout="prev,pager,next,total" :disabled="loading" />
    </ElCard>
    <ElDialog v-model="open" title="成员授权" width="480px" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving">
      <ElForm label-position="top" :disabled="saving"><ElFormItem label="成员">{{ name }}</ElFormItem><ElFormItem label="业务角色"><ElSelect v-model="form.role" clearable aria-label="业务角色"><ElOption v-for="(label,key) in roles" :key="key" :label="label" :value="key" /></ElSelect></ElFormItem><ElFormItem label="账号状态"><ElSelect v-model="form.status" aria-label="账号状态"><ElOption v-for="(label,key) in statuses" :key="key" :label="label" :value="key" /></ElSelect></ElFormItem></ElForm>
      <p class="hx-footnote">启用需要分配角色。设计和运营权限相同；角色调整在下一次请求重新校验。</p><ElAlert v-if="saveError" :title="saveError" type="error" :closable="false" />
      <template #footer><ElButton :disabled="saving" @click="open=false">取消</ElButton><ElButton type="primary" :loading="saving" @click="save">保存授权</ElButton></template>
    </ElDialog>
  </div>
</template>
<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { listUsers, saveUser } from '@/api/management'
import type { Role, User } from '@/types/hengxin'
import type { ManagedUser, UserInput } from '@/types/management'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import AdminPreview from './AdminPreview.vue'
import { useAdminQuery } from './use-admin-query'
const search=ref(''), status=ref<User['status']|''>(''), page=ref(1)
const { data, loading, error, load } = useAdminQuery(() => listUsers({page:page.value,pageSize:12,search:search.value,status:status.value||undefined}))
watch([search,status],()=>{ page.value=1; void load() }); watch(page,load)
const roles:Record<Role,string>={super_admin:'超级管理员',design_manager:'设计主管',designer:'设计人员',operator:'运营人员'},statuses={pending:'待授权',active:'启用',disabled:'禁用'}
const form=reactive<UserInput>({id:'',role:null,status:'pending'}),open=ref(false),name=ref(''),saving=ref(false),saveError=ref('')
function edit(user:ManagedUser){ Object.assign(form,{id:user.id,role:user.role,status:user.status});name.value=user.name;saveError.value='';open.value=true }
async function save(){if(saving.value)return;if(form.status==='active'&&!form.role){saveError.value='启用账号前请选择业务角色';return}saving.value=true;saveError.value='';try{await saveUser({...form,role:form.role||null});open.value=false;ElMessage.success('成员授权已更新');await load()}catch(e){saveError.value=e instanceof Error?e.message:'保存失败，请重试'}finally{saving.value=false}}
const columns=[{prop:'name',label:'姓名',minWidth:120},{prop:'department',label:'部门',minWidth:120},{prop:'role',label:'角色',minWidth:130,useSlot:true},{prop:'status',label:'状态',width:100,useSlot:true},{prop:'lastLoginAt',label:'最近登录',minWidth:180,useSlot:true},{prop:'action',label:'操作',width:165,useSlot:true}]
</script>
