<template>
  <div class="hx-page">
    <div class="hx-heading">
      <div><span class="hx-eyebrow">SYSTEM SETTINGS</span><h1>系统配置</h1><p>分开说明 API 与 CLI 配置的执行范围、单位及生效时机。</p></div>
      <ElButton :loading="loading" @click="reload">重新读取示例</ElButton>
    </div>
    <ElAlert class="hx-admin-banner" title="只读方案预览 · 执行参数为 2026-10-10 已核查配置快照，保留规则单独注明；不实时读取、不修改生产配置。" type="warning" :closable="false" show-icon />
    <p class="hx-muted" role="status">{{ loading ? '正在重载本地配置示例…' : '用户角色与 Skill 管理沿用现状；此页不提供生产保存。' }}</p>
    <div class="hx-stack">
      <ElCard class="art-card hx-section hx-admin-settings-card">
        <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">API GENERATION</span><h2>API 生图与文字修改</h2><p>控制 API 执行通道；不控制 CLI 图片修改的并发和整轮时限。</p></div><ElTag type="info">只读快照</ElTag></div>
        <ElTable :data="apiSettings">
          <ElTableColumn prop="name" label="配置" min-width="165" /><ElTableColumn prop="value" label="快照值 / 单位" min-width="160" /><ElTableColumn prop="scope" label="作用范围" min-width="300" />
        </ElTable>
        <p class="hx-footnote">配置属于部署与调度层。退避和收图期间仍保留任务准入名额，终态后释放；修改 / 重试重新排队。同任务在途追加不额外占名额。</p>
      </ElCard>
      <ElCard class="art-card hx-section hx-admin-settings-card">
        <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">CLI IMAGE EDIT</span><h2>CLI 图片修改</h2><p>API 成品多轮图片修改通过 CLI 执行；一次执行轮次不等于一套 API 生图任务。</p></div><ElTag type="info">执行参数已核查</ElTag></div>
        <ElTable :data="cliSettings">
          <ElTableColumn prop="name" label="配置" min-width="165" /><ElTableColumn prop="value" label="快照值 / 单位" min-width="160" /><ElTableColumn prop="scope" label="作用范围" min-width="300" />
        </ElTable>
        <p class="hx-footnote">并发受 CLI 执行节点容量约束，调整配置不会增加节点。时限在轮次提交时冻结，后续变更只影响新轮次；API 请求时限不随之改变。</p>
      </ElCard>
      <ElCard class="art-card hx-section hx-admin-settings-card">
        <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">RETENTION POLICY</span><h2>会话清理与数据保留</h2><p>拟议规则 · 展示待确认的管理口径，不代表生产清理调度已开启。</p></div><ElTag type="warning">拟议规则</ElTag></div>
        <ElTable :data="retention">
          <ElTableColumn prop="kind" label="数据类别" min-width="170" /><ElTableColumn prop="rule" label="保留规则" min-width="150" /><ElTableColumn prop="detail" label="范围与保护" min-width="310" />
        </ElTable>
        <ElAlert class="hx-gap" title="清理前须确认没有排队、运行、收图、取消中或待核实执行；未知状态保留现场。" type="info" :closable="false" />
        <p class="hx-muted">有效提交、回复、重试、采用及执行终态更新活动时间；查看、刷新、轮询不续期。过期后新修改使用正式图片及必要输入开启新会话，旧对话不恢复。</p>
        <p class="hx-footnote">统计摘要需独立保存，清理过程数据不应改变历史任务、图片与请求 / 轮次统计。生产接入与历史回填仍需正式实施验收。</p>
      </ElCard>
    </div>
  </div>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { ElAlert, ElButton, ElCard, ElTable, ElTableColumn, ElTag } from 'element-plus'
const loading = ref(false)
let reloadTimer: ReturnType<typeof setTimeout> | undefined
const apiSettings = [
  { name: '全站任务准入', value: '5 套任务并发', scope: '全站按 API 任务计数，不按用户分配；超出后按创建顺序排队' },
  { name: '每任务图片并行', value: '10 张图片 / 批', scope: '严格按批次执行；全站最多 50 张 API 图片在途' },
  { name: 'API 请求超时', value: '180 秒 / 请求', scope: '作用于 API 图片请求；重试沿用原冻结输入，不套用 CLI 整轮时限' },
  { name: '图片下载超时', value: '60 秒', scope: 'API 返回后下载图片的时限' },
  { name: '执行租约', value: '360 秒', scope: 'API Worker 执行租约，与请求时限独立' },
  { name: 'Skill', value: '不加载', scope: 'API 生图、文字修改与文案修复不加载 Skill' }
]
const cliSettings = [
  { name: '执行并发', value: '全站最多 5 个执行轮次', scope: '2026-10-10 16:19 核查快照：生效并发与节点容量均为5；同一图片会话串行，不与 API 5 套任务混算' },
  { name: '整轮总时限', value: '7200 秒 / 轮次', scope: '限制 CLI 整轮执行，若有自动干预也共用该额度' },
  { name: '模型 / 推理强度', value: 'gpt-6-astra / high', scope: 'CLI 图片修改的核查快照，不表示 API 生图模型' },
  { name: 'Skill', value: '不加载', scope: 'CLI 图片修改不加载 Skill；原 Skill 管理入口保留' }
]
const retention = [
  { kind: '私有缓存 / 插件', rule: '闲置 1 天后清理', detail: '仅任务私有缓存与插件；不清理共享凭据、CLI 安装或 Skill' },
  { kind: '会话 / 执行过程', rule: '连续闲置 7 天后清理', detail: '旧 CLI 任务与 API 图片修改会话的对话、提示词、执行明细及无引用未采用候选' },
  { kind: '正式图片 / 必要素材', rule: '保留', detail: '已采用、当前、已归档图片、原图、共用素材及仍有引用的文件不随会话过期删除' },
  { kind: '独立统计摘要', rule: '保留（拟议）', detail: '保留操作者、日期、渠道、请求 / 轮次 / 图片计数与清理回执；不保留大段过程内容' }
]
function reload() {
  loading.value = true
  reloadTimer = setTimeout(() => { loading.value = false }, 600)
}
onBeforeUnmount(() => { if (reloadTimer) clearTimeout(reloadTimer) })
</script>
