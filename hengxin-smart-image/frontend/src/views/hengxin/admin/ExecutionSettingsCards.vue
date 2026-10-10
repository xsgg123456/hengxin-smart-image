<template>
  <ElCard class="art-card hx-section hx-admin-settings-card">
    <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">API GENERATION</span><h2>API 生图与文字修改</h2><p>部署与调度配置，只读；不控制 CLI 修改的整轮时限。</p></div><ElTag type="info">{{ data.api.enabled ? '已启用' : '未启用' }}</ElTag></div>
    <ElTable :data="apiRows"><ElTableColumn prop="name" label="配置" min-width="165" /><ElTableColumn prop="value" label="生效值 / 单位" min-width="180" /><ElTableColumn prop="scope" label="作用范围" min-width="240" /></ElTable>
    <p class="hx-footnote">退避与收图期间保留任务准入名额，终态后释放；修改和重试重新排队。同任务在途追加不额外占名额。</p>
  </ElCard>
  <ElCard class="art-card hx-section hx-admin-settings-card">
    <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">CLI IMAGE EDIT</span><h2>CLI 图片修改 · 当前生效配置</h2><p>同图片会话串行；全局名额与旧 CLI 任务共享。</p></div><ElTag type="info">{{ data.cli.enabled ? '已启用' : '未启用' }}</ElTag></div>
    <ElTable :data="cliRows"><ElTableColumn prop="name" label="配置" min-width="165" /><ElTableColumn prop="value" label="生效值 / 单位" min-width="180" /><ElTableColumn prop="scope" label="作用范围" min-width="240" /></ElTable>
    <p class="hx-footnote">并发和整轮时限在提交时冻结，下方配置保存只影响后续轮次。默认 Skill 绑定保留用于原业务，API 图片修改不加载 Skill。</p>
  </ElCard>
  <ElCard class="art-card hx-section hx-admin-settings-card">
    <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">RETENTION POLICY</span><h2>会话清理与数据保留</h2><p>读取当前部署策略；配置开关不代表清理服务已在线。</p></div><ElTag type="info">{{ data.retention.enabled ? '配置已启用' : '配置未启用' }}</ElTag></div>
    <p>闲置 {{ data.retention.cacheIdleDays }} 天清理任务私有缓存与插件；闲置 {{ data.retention.historyIdleDays }} 天清理会话与过程数据。</p>
    <p class="hx-footnote">已采用的正式图片、必要素材及独立统计事实保留。排队、运行、收图、取消中或待核实执行保留现场；查看、刷新与轮询不续期。过期后可基于正式图片开启新会话。</p>
  </ElCard>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import type { ExecutionSettings } from '@/types/execution-management'
const props = defineProps<{data: ExecutionSettings}>()
const apiRows = computed(() => [
  {name:'全站任务准入',value:`${props.data.api.taskConcurrency} 套任务`,scope:'按任务准入，不是当前运行数量'},
  {name:'每任务图片批次',value:`${props.data.api.imagesPerBatch} 张 / 批`,scope:'每套按批执行'},
  {name:'请求时限',value:`${props.data.api.requestTimeoutSeconds} 秒`,scope:'单次 API 图片请求'},
  {name:'下载时限',value:`${props.data.api.downloadTimeoutSeconds} 秒`,scope:'收取上游返回图片'},
  {name:'执行租约',value:`${props.data.api.leaseSeconds} 秒`,scope:'持久化执行所有权'},
  {name:'图片模型',value:props.data.api.model,scope:'服务端冻结参数'},
  {name:'质量 / 分辨率',value:`${props.data.api.quality} / ${props.data.api.resolution}`,scope:'服务端冻结参数'},
  {name:'单次输出 / 尺寸',value:`${props.data.api.imagesPerRequest} 张 / ${props.data.api.sizePolicy}`,scope:'请求尺寸使用原图实际宽高'}
])
const cliRows = computed(() => [
  {name:'全局执行并发',value:`${props.data.cli.concurrency} 个轮次`,scope:`部署容量上限 ${props.data.cli.capacity}；不等同 Worker 实时容量`},
  {name:'整轮时限',value:`${props.data.cli.timeoutSeconds} 秒 / 轮`,scope:`部署上限 ${props.data.cli.timeoutCapacity} 秒`},
  {name:'模型 / 推理强度',value:`${props.data.cli.model} / ${props.data.cli.reasoningEffort}`,scope:'API 成品多轮修改'},
  {name:'Skill 加载',value:props.data.cli.usesSkills ? '加载' : '不加载',scope:'仅指 API 图片修改 CLI 会话'}
])
</script>
