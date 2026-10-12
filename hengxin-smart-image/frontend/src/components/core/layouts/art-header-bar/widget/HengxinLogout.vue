<template>
  <ElButton v-if="!isMockMode" text :disabled="busy" @click="switchBusiness">切换业务</ElButton>
  <ElButton text :loading="busy" @click="logout">退出登录</ElButton>
</template>

<script setup lang="ts">
import { broadcastLogout } from '@/api/hengxin/identity-lifecycle'
import { ref } from 'vue'
import { identityApi, IdentityError } from '@/api/identity/auth'
import { ElMessage } from 'element-plus'
import { isMockMode } from '@/api/hengxin/client'
import { logoutDestination, logoutSession } from '@/api/hengxin/logout'
import { useUserStore } from '@/store/modules/user'
import { useWorktabStore } from '@/store/modules/worktab'

const busy = ref(false)
function switchBusiness() { window.location.assign('/?workspace=identity#/auth/business') }
async function logout() {
  if (busy.value) return
  busy.value = true
  try {
    if (!isMockMode) {
      let legacy = false
      try { await identityApi.config() } catch (reason) {
        if (reason instanceof IdentityError && reason.status === 404) legacy = true
        else throw reason
      }
      if (legacy) await logoutSession(import.meta.env.VITE_API_URL || '/api/v1')
      else { await identityApi.logout(); broadcastLogout() }
    }
    else broadcastLogout()
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
