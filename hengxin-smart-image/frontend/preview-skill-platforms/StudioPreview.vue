<template>
  <section class="studio-page" style="--studio-height:max(610px,calc(100dvh - 310px))">
    <div class="task-scenario"><span>预览任务平台</span><ElSelect v-model="taskPlatform" aria-label="预览任务平台" style="width:230px"><ElOption v-for="p in platforms" :key="p.value" :label="p.label" :value="p.value" /></ElSelect><small>仅用于演示切换；正式工作台自动读取任务平台。</small></div>
    <div class="hx-heading"><div><h1>1030-拉通测试-张帅</h1><p>1030-拉通测试-张帅 · OUTON · {{ taskPlatform }} · H-ZGD0008 · 负责设计：张帅</p></div><ElButton size="small" @click="router.push('/overseas/admin/skills')">返回 Skill 管理</ElButton></div>
    <div class="studio-steps"><span class="done">① 运营提交图需</span><i /><span class="done">② 设计人工审核</span><i /><span class="active">③ AI 设计工作台</span><i /><span>④ 归档成品库</span></div>
    <ElCard shadow="never" class="art-card studio-chat-card">
      <div class="studio-chat-heading"><strong>与 Codex 协作</strong><div class="studio-actions"><ElButton size="small" @click="sessionsOpen = !sessionsOpen">会话 · 1/10</ElButton><ElButton size="small" @click="materialsOpen = !materialsOpen">任务素材 · 0</ElButton><ElButton size="small" @click="explain">刷新</ElButton><ElButton size="small" disabled>查看本任务成品</ElButton><ElButton size="small" disabled>完成任务</ElButton></div></div>
      <div class="studio-workspace">
        <StudioSessionList v-if="sessionsOpen" :sessions="sessions" active-id="preview-session" :disabled="false" :can-create="false" @close="sessionsOpen = false" @select="explain" @action="explain" />
        <section class="studio-conversation">
          <div class="session-current"><div><strong>OUTON_H-ZGD0008_主图与A+</strong><small>独立上下文 · 独立工作文件</small></div><div class="studio-actions"><ElButton size="small" @click="recoveryOpen = true">取回文件</ElButton><ElButton text size="small" @click="explain">重命名</ElButton></div></div>
          <StudioTurns :turns="[]" :transcript="[]" :selected="[]" :disabled="false" />
          <div class="session-archive-bar"><span>勾选当前会话图片，可下载或归档到本任务</span><div class="studio-actions"><ElButton size="small" disabled>下载所选图片（0）</ElButton><ElButton size="small" type="primary" disabled>归档所选图片（0）</ElButton></div></div>
          <div class="studio-composer">
            <div class="platform-scope"><ElTag size="small" effect="plain">{{ taskPlatform }}</ElTag><span>当前平台可用 Skill · {{ available.length }} 个</span></div>
            <p v-if="!available.length" class="scope-empty" role="status">当前平台暂无可用 Skill，可不选 Skill 继续交流，或联系管理员配置。</p>
            <p v-if="invalidNotice" class="scope-empty" role="status">{{ invalidNotice }}</p>
            <button class="studio-dropzone" @click="explain">拖拽图片或文件到这里，或点击上传 <small>仅加入当前会话 · 最多 100 个附件 · 单个最大 500 MB</small></button>
            <ElInput v-model="text" type="textarea" :rows="2" resize="none" aria-label="设计要求" placeholder="描述设计要求，或继续提出修改意见…" @keydown="handleStudioSendKey($event, showSend)" />
            <div class="studio-compose-tools"><div class="studio-input-tools"><StudioSkillSelect v-model="skill" :skills="available" :disabled="false" /></div><div class="studio-send-tools"><StudioTextEditor v-model="text" :disabled="false" session-name="OUTON_H-ZGD0008_主图与A+" /><ElButton type="primary" :disabled="!text.trim()" @click="sendOpen = true">发送</ElButton></div></div>
            <p class="studio-compose-note">发送到：OUTON_H-ZGD0008_主图与A+ · Enter 发送，Shift + Enter 换行 · 切换会话保留草稿</p>
          </div>
        </section>
        <StudioMaterials v-if="materialsOpen" :assets="[]" :disabled="false" @close="materialsOpen = false" />
      </div>
    </ElCard>
    <StudioRecoveryPreview v-if="recoveryOpen" task-id="preview-task" conversation-id="preview-session" :readonly="false" :busy="false" @close="recoveryOpen = false" />
    <ElDialog v-model="sendOpen" title="预览本轮选择" width="min(560px,94vw)" append-to-body><p>任务平台：{{ taskPlatform }}</p><p>所选 Skill：{{ available.find(s => s.id === skill)?.displayName || '不指定 Skill' }}</p><p class="preview-message">{{ text }}</p><p class="hx-muted">这是交互预览，不提交真实任务或调用生图。</p><template #footer><ElButton type="primary" @click="sendOpen = false">返回编辑</ElButton></template></ElDialog>
  </section>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import StudioSessionList from '@/views/overseas/studio/StudioSessionList.vue'
import StudioMaterials from '@/views/overseas/studio/StudioMaterials.vue'
import StudioTurns from '@/views/overseas/studio/StudioTurns.vue'
import StudioSkillSelect from './StudioSkillSelectPreview.vue'
import StudioRecoveryPreview from './StudioRecoveryPreview.vue'
import StudioTextEditor from '@/views/overseas/studio/StudioTextEditor.vue'
import type { SessionView } from '@/views/overseas/studio/studio-session-state'
import { handleStudioSendKey } from '@/views/overseas/studio/studio-send-key'
import '@/views/overseas/studio/studio.css'
import '@/views/overseas/studio/studio-sessions.css'
import { skills, platforms, taskPlatform } from './state'
const router = useRouter(), skill = ref(''), text = ref(''), invalidNotice = ref('')
const sessionsOpen = ref(true), materialsOpen = ref(true), sendOpen = ref(false), recoveryOpen = ref(false)
const sessions: SessionView[] = [{ id: 'preview-session', name: 'OUTON_H-ZGD0008_主图与A+', version: 1, createdAt: '2026-11-02T08:00:00Z', updatedAt: '2026-11-02T08:00:00Z', activeTurnId: null, turnCount: 0, status: 'empty', unread: false, draft: false }]
const available = computed(() => skills.filter(s => s.enabled && s.platforms.includes(taskPlatform.value)))
watch(available, list => { invalidNotice.value = ''; if (skill.value && !list.some(s => s.id === skill.value)) { skill.value = ''; invalidNotice.value = '原选 Skill 不适用于当前平台，已清空选择，输入内容保留。' } })
function explain() { ElMessage.info('本预览聚焦平台筛选，可编辑输入内容并选择 Skill；其他任务操作未接入。') }
function showSend() { if (text.value.trim()) sendOpen.value = true }
</script>
<style scoped>
.task-scenario { display:flex; align-items:center; gap:12px; flex-wrap:wrap; margin-bottom:20px; font-size:13px; }
.task-scenario small { color:var(--art-gray-500); }
.platform-scope { display:flex; align-items:center; flex-wrap:wrap; gap:8px; margin:0 0 12px; font-size:12px; color:var(--art-gray-600); }
.scope-empty { margin:0 0 10px; color:var(--el-color-warning); font-size:12px; line-height:1.6; }
.preview-message { white-space:pre-wrap; overflow-wrap:anywhere; }
</style>
