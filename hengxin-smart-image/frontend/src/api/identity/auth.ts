import { createIdentityRequest, IdentityError, record } from './request'
import type { Business } from './access'
export { IdentityError }
export interface IdentityConfig { configured: boolean; corpId: string; clientId: string }
export interface Member { id: string; name: string; status: string; role?: string; roles?: string[]; capabilities?: string[] }
export type AccessResult = { state: 'allowed'; member: Member } | { state: 'denied' | 'error'; message: string }
const isName = (v: unknown): v is { name: string } => record(v) && typeof v.name === 'string'
const noContent = (v: unknown): v is undefined => v === undefined
const base = '/api/identity/v1'
const businessBase = (business: Business) => business === 'domestic' ? '/api/v1' : '/api/overseas/v1'
const memberGuard = (business: Business) => (v: unknown): v is Member => record(v) && typeof v.id === 'string' && typeof v.name === 'string' && v.status === 'active' && (business === 'domestic' ? typeof v.role === 'string' : Array.isArray(v.roles) && v.roles.length > 0 && v.roles.every(x => typeof x === 'string') && Array.isArray(v.capabilities) && v.capabilities.every(x => typeof x === 'string'))
export function createIdentityApi(fetcher: typeof fetch = fetch) {
  const request = createIdentityRequest(fetcher)
  return {
    config: () => request(`${base}/config`, (v): v is IdentityConfig => record(v) && typeof v.configured === 'boolean' && typeof v.corpId === 'string' && typeof v.clientId === 'string'),
    me: () => request(`${base}/me`, isName),
    container: (code: string) => request(`${base}/dingtalk/container`, isName, { code }),
    async access(business: Business): Promise<AccessResult> {
      try {
        const { ticket } = await request(`${base}/tickets`, (v): v is { ticket: string } => record(v) && typeof v.ticket === 'string' && !!v.ticket, { business })
        const member = await request(`${businessBase(business)}/auth/identity/session`, memberGuard(business), { ticket })
        return { state: 'allowed', member }
      } catch (error) {
        if (error instanceof IdentityError && error.status === 401) throw error
        return { state: error instanceof IdentityError && error.status === 403 ? 'denied' : 'error', message: error instanceof Error ? error.message : '服务暂不可用，请重试' }
      }
    },
    overseasMe: () => request('/api/overseas/v1/auth/me', memberGuard('overseas')),
    async logout() {
      await request(`${base}/logout`, noContent, {})
      const results = await Promise.allSettled(['domestic', 'overseas'].map(business => request(`${businessBase(business as Business)}/auth/logout`, noContent, {})))
      if (results.some(result => result.status === 'rejected')) throw new IdentityError(0, '统一身份已退出，部分业务退出未完成，请重试')
    }
  }
}
export const identityApi = createIdentityApi()
