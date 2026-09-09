// Frontend prototype fixtures. Replace with real authentication before production.
export async function fetchLogin(_params: Api.Auth.LoginParams): Promise<Api.Auth.LoginResponse> {
  throw new Error('此页面是本地原型，不提供真实登录')
}
export async function fetchGetUserInfo(): Promise<Api.Auth.UserInfo> {
  return { userId: 1, userName: '运营同事', email: '', roles: ['R_SUPER'], buttons: [] }
}
