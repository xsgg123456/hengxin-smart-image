<template>
  <div class="wm-detail">
    <div class="wm-detail-heading"><ElButton @click="$emit('back')">← 返回会话列表</ElButton><span>{{ session.person }} / {{ workspaceName(session.workspace) }}</span><ElButton @click="materialsOpen = true">附件与结果</ElButton></div>
    <div class="wm-workbench">
      <aside class="wm-conversations"><div class="wm-sidebar-title"><strong>{{ session.person }}</strong><span>{{ siblingSessions.length }} 个会话</span></div><p>该成员的工作台会话</p><button v-for="item in siblingSessions" :key="item.id" :class="['wm-conversation', { active: item.id === session.id }]" @click="$emit('select', item)"><span>{{ item.name }}</span><small>{{ workspaceName(item.workspace) }}</small><div><i :class="['wm-dot', item.status]" />{{ labels[item.status] }}<time>{{ item.time }}</time></div></button><div class="wm-sidebar-note">以管理员身份只读查看<br>用户的会话继续独立执行</div></aside>
      <main class="wm-chat">
        <header class="wm-chat-heading"><div><strong>{{ session.name }}</strong><span>{{ workspaceName(session.workspace) }} · {{ session.turns }} 轮对话</span></div><ElTag :type="tagType(session.status)">{{ labels[session.status] }}</ElTag></header>
        <div v-if="session.status === 'empty'" class="wm-empty"><ElEmpty description="这个会话还没有提交消息" /><p>用户发送消息后，这里将显示对话与执行进度。</p></div>
        <div v-else ref="messageArea" class="studio-messages wm-messages">
          <div class="studio-conversation-divider">今天 · 北京时间 · 演示内容</div>
          <article class="studio-message user"><div class="studio-message-name">{{ session.person }}<small>10:20:08</small></div><div class="studio-bubble"><ElTag v-if="session.skill !== '未选择 Skill'" size="small">{{ session.skill }}</ElTag><p>{{ session.prompt }}</p><div class="wm-attachments"><button @click="materialsOpen = true"><span class="wm-file-icon">图</span><span>产品参考图.svg<small>示例素材 · 点击预览</small></span></button><button @click="noteOpen = true"><span class="wm-file-icon text">TXT</span><span>图需说明.txt<small>演示文本 · 点击查看</small></span></button></div></div></article>
          <article class="studio-message assistant"><div class="studio-message-name">Codex<small>{{ session.turns > 1 ? '已回复 · 10:24:12' : labels[session.status] }}</small></div><div class="studio-bubble">
            <details class="studio-execution" :open="session.turns === 1"><summary>执行过程 · {{ session.status === 'queued' ? '等待处理' : '查看记录' }}</summary><div class="wm-process"><p><i class="wm-dot succeeded" />已接收本轮需求与附件</p><p v-if="session.status !== 'queued'"><i class="wm-dot succeeded" />已读取产品资料，核对修改范围</p><p v-if="session.status === 'failed'" class="wm-error"><i class="wm-dot failed" />本轮执行失败，尚未生成结果</p><p v-else-if="session.status === 'queued'"><i class="wm-dot queued" />正在排队，尚未开始执行</p><p v-else><i class="wm-dot succeeded" />完成首轮方案整理</p></div></details>
            <ElAlert v-if="session.status === 'failed'" title="本轮执行未完成。用户可在自己的工作台检查并重试。" type="error" :closable="false" />
            <p v-else-if="session.status !== 'queued'">已核对产品资料与修改范围。{{ session.turns > 1 ? '首轮内容已整理，后续修改将在当前会话继续。' : '正在按本轮需求处理。' }}</p>
          </div></article>
          <template v-if="session.turns > 1">
            <article class="studio-message user"><div class="studio-message-name">{{ session.person }}<small>{{ session.time }}:06</small></div><div class="studio-bubble"><p>继续按刚才的方向处理。保留产品原有结构，画面更简洁一些，不要增加额外文字。</p></div></article>
            <article class="studio-message assistant"><div class="studio-message-name">Codex<small>{{ session.status === 'running' ? '执行中' : '已回复' }}</small><small v-if="session.status === 'succeeded'">{{ session.time }}:48</small></div><div class="studio-bubble">
              <details class="studio-execution" :open="session.status === 'running'"><summary>执行过程 · {{ 2 + (session.status === 'running' ? steps : 1) }} 条记录</summary><div class="wm-process"><p><i class="wm-dot succeeded" />已接收本轮修改要求</p><p><i :class="['wm-dot', session.status === 'running' ? 'running' : 'succeeded']" />{{ session.status === 'running' ? '正在处理图片，保留产品结构与配色' : '图片处理完成' }}</p><p v-if="session.status === 'running' && steps >= 1"><i class="wm-dot succeeded" />已完成产品结构核对</p><p v-if="session.status === 'running' && steps >= 2"><i class="wm-dot running" />正在检查画面细节与输出尺寸</p><p v-if="session.status === 'running' && steps >= 3"><i class="wm-dot running" />正在收取结果文件</p><p v-if="session.status === 'succeeded'"><i class="wm-dot succeeded" />结果文件已保存</p></div></details>
              <p v-if="session.status === 'succeeded'">已完成本轮处理，请查看下方结果。</p><p v-else class="wm-pending"><i class="wm-dot running" />正在执行，新的过程记录会显示在这里…</p>
              <div v-if="session.status === 'succeeded'" class="wm-results"><div v-for="(url, index) in resultImages" :key="url"><ElImage :src="url" :preview-src-list="resultImages" :initial-index="index" preview-teleported fit="contain" :alt="`演示结果图 ${index + 1}`" /><div><span>结果示意 {{ index + 1 }}</span><a :href="url" :download="`演示结果-${index + 1}.svg`">下载示例图</a></div></div></div>
              <small v-if="session.status === 'succeeded'" class="wm-subtext">以上为项目自带的占位示意图，仅用于预览图片展示交互。</small>
            </div></article>
          </template>
        </div>
        <footer class="wm-readonly"><span><span class="wm-lock">◇</span> 管理员只读查看 · 无法代发消息或修改用户内容</span><ElButton v-if="session.status === 'running'" text type="primary" :disabled="scene === 'offline' || steps >= 3" @click="advance">{{ steps >= 3 ? '演示进度已展示' : '演示一条新进度' }}</ElButton></footer>
      </main>
    </div>
    <ElDrawer v-model="materialsOpen" title="附件与结果" size="min(460px, 94vw)" append-to-body><p class="wm-muted">{{ session.person }} · {{ session.name }}</p><ElTabs v-model="assetTab"><ElTabPane label="用户附件" name="inputs"><div v-if="session.turns" class="wm-material"><ElImage src="/samples/product-0.svg" :preview-src-list="['/samples/product-0.svg']" preview-teleported fit="contain" alt="产品参考示意图" /><strong>产品参考图.svg</strong><p>演示素材</p><a href="/samples/product-0.svg" download="产品参考示意图.svg">下载示例图</a><ElDivider /><ElButton @click="noteOpen = true">查看图需说明.txt</ElButton></div><ElEmpty v-else description="还没有已提交的附件" /></ElTabPane><ElTabPane label="生成结果" name="results"><div v-if="session.images" class="wm-material"><ElImage v-for="(url, i) in resultImages" :key="url" :src="url" :preview-src-list="resultImages" :initial-index="i" preview-teleported fit="contain" :alt="`结果示意 ${i + 1}`" /><p>预览占位图 · 非真实生成结果</p></div><ElEmpty v-else :description="session.status === 'running' ? '正在执行，暂无已保存结果' : '暂无生成结果'" /></ElTabPane></ElTabs></ElDrawer>
    <ElDialog v-model="noteOpen" title="图需说明.txt · 演示文件" width="min(600px, 94vw)" append-to-body><p class="wm-note-text">{{ session.prompt }}</p><p>本文件为独立交互预览中的演示资料。</p><template #footer><ElButton @click="noteOpen = false">关闭</ElButton><ElButton type="primary" @click="downloadNote">下载演示文件</ElButton></template></ElDialog>
  </div>
</template>
<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { labels, scene, sessions, simulate, progress, tagType, workspaceName, type Session } from './data'
const props = defineProps<{ session: Session }>()
defineEmits<{ back: []; select: [session: Session] }>()
const materialsOpen = ref(false), noteOpen = ref(false), assetTab = ref('inputs'), messageArea = ref<HTMLElement>()
const steps = computed(() => progress.value[props.session.id] || 0)
const siblingSessions = computed(() => sessions.value.filter(s => s.person === props.session.person))
const resultImages = computed(() => props.session.workspace === 'phone' ? ['/samples/wallpaper-0.svg', '/samples/wallpaper-1.svg'] : ['/samples/product-1.svg', '/samples/product-2.svg'])
onMounted(() => { if (messageArea.value) messageArea.value.scrollTop = messageArea.value.scrollHeight })
async function advance() { simulate(props.session.id); await nextTick(); messageArea.value?.scrollTo({ top: messageArea.value.scrollHeight, behavior: 'smooth' }) }
function downloadNote() {
  const blob = new Blob([props.session.prompt + '\n\n本文件为独立交互预览中的演示资料。'], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob), link = document.createElement('a')
  link.href = url; link.download = '图需说明-演示.txt'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
}
</script>
