<template>
  <ElButton text :loading="busy" @click="logout">退出登录</ElButton>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { isMockMode } from '@/api/hengxin/client'
import { logoutDestination, logoutSession } from '@/api/hengxin/logout'
import { useUserStore } from '@/store/modules/user'
import { useWorktabStore } from '@/store/modules/worktab'

const busy = ref(false)
async function logout() {
  if (busy.value) return
  busy.value = true
  try {
    if (!isMockMode) await logoutSession(import.meta.env.VITE_API_URL || '/api/v1')
    const user = useUserStore()
    user.setLoginStatus(false)
    user.info = {}
    user.accessToken = ''
    user.refreshToken = ''
    user.setSearchHistory([])
    user.setLockStatus(false)
    user.setLockPassword('')
    useWorktabStore().opened = []
    useWorktabStore().current = {}
    useWorktabStore().keepAliveExclude = []
    sessionStorage.removeItem('iframeRoutes')
    // 整页离开销毁业务缓存和轮询；登录页启动逻辑不会自动恢复会话。
    window.location.replace(logoutDestination(window.location.href))
  } catch (error) {
    ElMessage.error(error instanceof Error ? `退出失败：${error.message}` : '退出失败，请重试')
  } finally {
    busy.value = false
  }
}
</script>
