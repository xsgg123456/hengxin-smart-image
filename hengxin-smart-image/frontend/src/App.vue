<template>
  <ElConfigProvider
    size="default"
    :locale="locales[language]"
    :z-index="3000"
    :card="{
      shadow: 'never'
    }"
  >
    <DingtalkLogin v-if="bootstrap.authRequired" />
    <template v-else-if="bootstrap.ready">
      <RouterView />
    </template>
    <div v-else class="hx-page">
      <ElCard class="art-card hx-section">
        <h1>恒信 AI 换套图</h1>
        <p v-if="bootstrap.loading" role="status">正在连接工作区…</p>
        <template v-else>
          <ElAlert :title="bootstrap.error || '工作区尚未就绪'" type="error" :closable="false" show-icon />
          <ElButton class="hx-gap" type="primary" @click="retryBootstrap.run">重新连接</ElButton>
        </template>
      </ElCard>
    </div>
  </ElConfigProvider>
</template>

<script setup lang="ts">
  import { RouterView } from 'vue-router'
  import DingtalkLogin from './views/auth/dingtalk-login.vue'
  import { useUserStore } from './store/modules/user'
  import { bootstrap, retryBootstrap } from './api/hengxin/bootstrap'
  import zh from 'element-plus/es/locale/lang/zh-cn'
  import en from 'element-plus/es/locale/lang/en'
  import { systemUpgrade } from './utils/sys'
  import { toggleTransition } from './utils/ui/animation'
  import { checkStorageCompatibility } from './utils/storage'
  import { initializeTheme } from './hooks/core/useTheme'

  const userStore = useUserStore()
  const { language } = storeToRefs(userStore)

  const locales = {
    zh: zh,
    en: en
  }

  onBeforeMount(() => {
    toggleTransition(true)
    initializeTheme()
  })

  onMounted(() => {
    checkStorageCompatibility()
    toggleTransition(false)
    systemUpgrade()
  })
</script>
