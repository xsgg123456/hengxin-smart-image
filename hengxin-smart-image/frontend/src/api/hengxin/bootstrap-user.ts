import { identity } from './identity'

/** 仅供本次已认证启动中的路由初始化消费一次；不跨启动或身份代次缓存。 */
export function createBootstrapUserHandoff<T>() {
  let entry: { epoch: number; user: T } | undefined
  return {
    offer(user: T) { entry = { epoch: identity.epoch, user } },
    take() {
      const current = entry; entry = undefined
      return current && identity.current(current.epoch) ? current.user : undefined
    },
    clear() { entry = undefined }
  }
}
export const bootstrapUser = createBootstrapUserHandoff<Api.Auth.UserInfo>()
