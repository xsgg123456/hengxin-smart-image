import type { Router } from 'vue-router'
import { identity } from './identity'

/** 注销动态路由不会清除 currentRoute.matched，必须在展示新身份前重走守卫。 */
export async function restoreIdentityRoutes(router: Router, epoch: number) {
  identity.assert(epoch)
  const failure = await router.replace({ path: '/image-processing/wallpaper', force: true })
  identity.assert(epoch)
  if (failure) throw new Error('身份已更新，页面权限尚未确认，请重新连接')
}
