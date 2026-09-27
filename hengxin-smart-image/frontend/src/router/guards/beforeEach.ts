import { bootstrapUser } from '@/api/hengxin/bootstrap-user'
import { identity } from '@/api/hengxin/identity'
import type { Router, RouteLocationNormalized, NavigationGuardNext, RouteRecordRaw } from 'vue-router'
import { nextTick } from 'vue'
import NProgress from 'nprogress'
import { useSettingStore } from '@/store/modules/setting'
import { useUserStore } from '@/store/modules/user'
import { useMenuStore } from '@/store/modules/menu'
import { setWorktab } from '@/utils/navigation'
import { setPageTitle } from '@/utils/router'
import { RoutesAlias } from '../routesAlias'
import { staticRoutes } from '../routes/staticRoutes'
import { loadingService } from '@/utils/ui'
import { useCommon } from '@/hooks/core/useCommon'
import { useWorktabStore } from '@/store/modules/worktab'
import { fetchGetUserInfo } from '@/api/auth'
import { ApiStatus } from '@/utils/http/status'
import { isHttpError } from '@/utils/http/error'
import { RouteRegistry, MenuProcessor, IframeRouteManager } from '../core'
import { isDeniedBusinessRoute } from '../business-route-access'
// 路由注册器实例
let routeRegistry: RouteRegistry | null = null
// 菜单处理器实例
const menuProcessor = new MenuProcessor()
// 跟踪是否需要关闭 loading
let pendingLoading = false
// 路由初始化失败标记，防止死循环
// 一旦设置为 true，只有刷新页面或重新登录才能重置
let routeInitFailed = false
// 路由初始化进行中标记，防止并发请求
let routeInitInProgress = false
export function getPendingLoading(): boolean {
  return pendingLoading
}
export function resetPendingLoading(): void {
  pendingLoading = false
}
export function getRouteInitFailed(): boolean {
  return routeInitFailed
}
export function resetRouteInitState(): void {
  routeInitFailed = false
  routeInitInProgress = false
}
export function setupBeforeEachGuard(router: Router): void {
  // 初始化路由注册器
  routeRegistry = new RouteRegistry(router)
  router.beforeEach(
    async (
      to: RouteLocationNormalized,
      from: RouteLocationNormalized,
      next: NavigationGuardNext
    ) => {
      try {
        await handleRouteGuard(to, from, next, router)
      } catch (error) {
        console.error('[RouteGuard] 路由守卫处理失败:', error)
        closeLoading()
        next({ name: 'Exception500' })
      }
    }
  )
}
function closeLoading(): void {
  if (pendingLoading) {
    nextTick(() => {
      loadingService.hideLoading()
      pendingLoading = false
    })
  }
}
async function handleRouteGuard(
  to: RouteLocationNormalized,
  from: RouteLocationNormalized,
  next: NavigationGuardNext,
  router: Router
): Promise<void> {
  const settingStore = useSettingStore()
  const userStore = useUserStore()
  // 启动进度条
  if (settingStore.showNprogress) {
    NProgress.start()
  }
  // 1. 检查登录状态
  if (!handleLoginStatus(to, userStore, next)) {
    return
  }
  // 2. 检查路由初始化是否已失败（防止死循环）
  if (routeInitFailed) {
    // 已经失败过，直接放行到错误页面，不再重试
    if (to.matched.length > 0) {
      next()
    } else {
      // 未匹配到路由，跳转到 500 页面
      next({ name: 'Exception500', replace: true })
    }
    return
  }
  // 3. 处理动态路由注册
  if (!routeRegistry?.isRegistered() && userStore.isLogin) {
    // 防止并发请求（快速连续导航场景）
    if (routeInitInProgress) {
      // 正在初始化中，等待完成后重新导航
      next(false)
      return
    }
    await handleDynamicRoutes(to, next, router)
    return
  }
  // 4. 处理根路径重定向
  if (handleRootPathRedirect(to, next)) {
    return
  }
  // 已知受限页面提供可见的权限说明，不落入父菜单或 404。
  if (isDeniedBusinessRoute(to.path, useMenuStore().menuList)) {
    closeLoading()
    next({ name: 'Exception403', replace: true })
    return
  }
  // 5. 处理已匹配的路由
  if (to.matched.length > 0) {
    setWorktab(to)
    setPageTitle(to)
    next()
    return
  }
  // 6. 未匹配到路由，跳转到 404
  next({ name: 'Exception404' })
}
function handleLoginStatus(
  to: RouteLocationNormalized,
  userStore: ReturnType<typeof useUserStore>,
  next: NavigationGuardNext
): boolean {
  // 已登录或访问登录页或静态路由，直接放行
  if (userStore.isLogin || to.path === RoutesAlias.Login || isStaticRoute(to.path)) {
    return true
  }
  // 未登录且访问需要权限的页面，跳转到登录页并携带 redirect 参数
  userStore.logOut()
  next({
    name: 'Login',
    query: { redirect: to.fullPath }
  })
  return false
}
function isStaticRoute(path: string): boolean {
  const checkRoute = (routes: RouteRecordRaw[], targetPath: string): boolean => {
    return routes.some((route) => {
      // 404 catch-all 路由不应视为可匿名访问的静态页，
      // 否则未登录时手动输入任意地址会直接落到 404，无法跳转登录页。
      if (route.name === 'Exception404') {
        return false
      }
      // 处理动态路由参数匹配
      const routePath = route.path
      const pattern = routePath.replace(/:[^/]+/g, '[^/]+').replace(/\*/g, '.*')
      const regex = new RegExp(`^${pattern}$`)
      if (regex.test(targetPath)) {
        return true
      }
      if (route.children && route.children.length > 0) {
        return checkRoute(route.children, targetPath)
      }
      return false
    })
  }
  return checkRoute(staticRoutes, path)
}
async function handleDynamicRoutes(
  to: RouteLocationNormalized,
  next: NavigationGuardNext,
  router: Router
): Promise<void> {
  const epoch = identity.epoch
  // 标记初始化进行中
  routeInitInProgress = true
  // 显示 loading
  pendingLoading = true
  loadingService.showLoading()
  try {
    // 1. 获取用户信息
    await fetchUserInfo()
    // 2. 获取菜单数据
    const menuList = await menuProcessor.getMenuList()
    identity.assert(epoch)
    // 3. 验证菜单数据
    if (!menuProcessor.validateMenuList(menuList)) {
      throw new Error('获取菜单列表失败，请重新登录')
    }
    // 4. 注册动态路由
    routeRegistry?.register(menuList)
    // 5. 保存菜单数据到 store
    const menuStore = useMenuStore()
    menuStore.setMenuList(menuList)
    menuStore.addRemoveRouteFns(routeRegistry?.getRemoveRouteFns() || [])
    // 6. 保存 iframe 路由
    IframeRouteManager.getInstance().save()
    // 7. 验证工作标签页
    useWorktabStore().validateWorktabs(router)
    // 8. 静态路由不依赖菜单权限，初始化后直接恢复目标地址。
    if (isStaticRoute(to.path)) {
      routeInitInProgress = false
      next({
        path: to.path,
        query: to.query,
        hash: to.hash,
        replace: true
      })
      return
    }
    if (isDeniedBusinessRoute(to.path, menuList)) {
      routeInitInProgress = false
      closeLoading()
      next({ name: 'Exception403', replace: true })
      return
    }
    // 初始化成功，重置进行中标记
    routeInitInProgress = false
    // 已知受限页面已处理；其余交给已注册路由，未知地址由 404 兜底。
    next({ path: to.path, query: to.query, hash: to.hash, replace: true })
  } catch (error) {
    if (!identity.current(epoch)) { next(false); return }
    console.error('[RouteGuard] 动态路由注册失败:', error)
    // 关闭 loading
    closeLoading()
    // 401 错误：axios 拦截器已处理退出登录，取消当前导航
    if (isUnauthorizedError(error)) {
      // 重置状态，允许重新登录后再次初始化
      routeInitInProgress = false
      next(false)
      return
    }
    // 标记初始化失败，防止死循环
    routeInitFailed = true
    routeInitInProgress = false
    // 输出详细错误信息，便于排查
    if (isHttpError(error)) {
      console.error(`[RouteGuard] 错误码: ${error.code}, 消息: ${error.message}`)
    }
    // 跳转到 500 页面，使用 replace 避免产生历史记录
    next({ name: 'Exception500', replace: true })
  }
}
async function fetchUserInfo(): Promise<void> {
  const epoch = identity.epoch
  const userStore = useUserStore()
  const data = bootstrapUser.take() ?? await fetchGetUserInfo()
  identity.assert(epoch)
  userStore.setUserInfo(data)
  // 检查并清理工作台标签页（如果是不同用户登录）
  userStore.checkAndClearWorktabs()
}
export function resetRouterState(delay: number): void {
  const reset = () => {
    routeRegistry?.unregister()
    IframeRouteManager.getInstance().clear()
    const menuStore = useMenuStore()
    menuStore.removeAllDynamicRoutes()
    menuStore.setMenuList([])
    // 重置路由初始化状态，允许重新登录后再次初始化
    resetRouteInitState()
  }
  if (delay <= 0) reset()
  else setTimeout(reset, delay)
}
function handleRootPathRedirect(to: RouteLocationNormalized, next: NavigationGuardNext): boolean {
  if (to.path !== '/') {
    return false
  }
  const { homePath } = useCommon()
  if (homePath.value && homePath.value !== '/') {
    next({ path: homePath.value, replace: true })
    return true
  }
  return false
}
function isUnauthorizedError(error: unknown): boolean {
  return isHttpError(error) && error.code === ApiStatus.unauthorized
}
