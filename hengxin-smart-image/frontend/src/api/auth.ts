import { getService } from './hengxin/client'
import { ApiError } from './hengxin/http'
export async function fetchLogin(_params: Api.Auth.LoginParams): Promise<Api.Auth.LoginResponse> {
  throw new Error('钉钉登录将在后续阶段接入')
}
export async function fetchGetUserInfo(): Promise<Api.Auth.UserInfo> {
  const user = await (await getService()).getUser()
  if (user.status !== 'active' || !user.role) throw new ApiError(user.status === 'disabled' ? 'ACCOUNT_DISABLED' : 'AUTH_PENDING', user.status === 'disabled' ? '账号已禁用，请联系超级管理员' : '账号待授权，请联系超级管理员分配角色', 401)
  // 原 Art 展示适配；真实身份、权限及钉钉接入在 Phase 12 完成。
  return { userId: user.id, userName: user.name, email: '', roles: [user.role], buttons: [] }
}
