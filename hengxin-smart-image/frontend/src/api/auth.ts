import { getService } from './hengxin/client'
export async function fetchLogin(_params: Api.Auth.LoginParams): Promise<Api.Auth.LoginResponse> {
  throw new Error('钉钉登录将在后续阶段接入')
}
export async function fetchGetUserInfo(): Promise<Api.Auth.UserInfo> {
  const user = await (await getService()).getUser()
  if (user.status !== 'active' || !user.role) throw new Error('账号未授权或已禁用')
  // 原 Art 展示适配；真实身份、权限及钉钉接入在 Phase 12 完成。
  return { userId: user.id, userName: user.name, email: '', roles: [user.role], buttons: [] }
}
