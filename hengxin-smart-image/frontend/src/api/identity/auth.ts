import { createIdentityRequest, IdentityError, record } from './request'
import type { Business } from './access'
import { isApplication, type MembershipApplication } from './applications'
export { IdentityError }
export interface IdentityConfig { configured: boolean; corpId: string; clientId: string }
export interface Identity { name: string; sessionId: string }
export interface Member { id: string; name: string; status: string; identitySessionId: string; role?: string; roles?: string[]; capabilities?: string[] }
export type AccessResult = { state: 'allowed'; member: Member } | { state: 'unregistered' | 'pending' | 'rejected' | 'disabled' | 'legacy_unconfirmed'; application?: MembershipApplication } | { state: 'error'; message: string }
const isName = (v: unknown): v is Identity => record(v) && typeof v.name === 'string' && typeof v.sessionId === 'string' && !!v.sessionId
const noContent = (v: unknown): v is undefined => v === undefined
const base = '/api/identity/v1'
const businessBase = (business: Business) => business === 'domestic' ? '/api/v1' : '/api/overseas/v1'
const memberGuard = (business: Business) => (v: unknown): v is Member => record(v) && typeof v.id === 'string' && typeof v.name === 'string' && typeof v.identitySessionId === 'string' && !!v.identitySessionId && v.status === 'active' && (business === 'domestic' ? ['super_admin', 'design_manager', 'designer', 'operator'].includes(String(v.role)) : Array.isArray(v.roles) && v.roles.length === 1 && v.roles.every(x => ['super_admin', 'design_manager', 'designer', 'operator', 'operator_manager'].includes(String(x))) && Array.isArray(v.capabilities) && v.capabilities.every(x => typeof x === 'string'))
const accessGuard = (business: Business) => (v: unknown): v is AccessResult => record(v) && (v.state === 'allowed' ? memberGuard(business)(v.member)
  : ['unregistered', 'pending', 'rejected', 'disabled', 'legacy_unconfirmed'].includes(String(v.state)) && (v.application === undefined || isApplication(v.application)))
export function createIdentityApi(fetcher: typeof fetch = fetch) {
  const request = createIdentityRequest(fetcher)
  const ticket = async (business: Business, purpose: 'access' | 'session' | 'application', expectedSessionId?: string) => request(`${base}/tickets`, (v): v is { ticket: string } => record(v) && typeof v.ticket === 'string' && !!v.ticket, { business, purpose, ...(expectedSessionId ? { expectedSessionId } : {}) })
  return {
    config: () => request(`${base}/config`, (v): v is IdentityConfig => record(v) && typeof v.configured === 'boolean' && typeof v.corpId === 'string' && typeof v.clientId === 'string'),
    me: () => request(`${base}/me`, isName),
    container: (code: string) => request(`${base}/dingtalk/container`, isName, { code }),
    async access(business: Business, expectedSessionId?: string): Promise<AccessResult> {
      try {
        return await request(`${businessBase(business)}/auth/identity/access`, accessGuard(business), await ticket(business, 'access', expectedSessionId))
      } catch (error) {
        if (error instanceof IdentityError && error.status === 401) throw error
        return { state: 'error', message: error instanceof Error ? error.message : '服务暂不可用，请重试' }
      }
    },
    session: async (business: Business, expectedSessionId?: string) => request(`${businessBase(business)}/auth/identity/session`, memberGuard(business), await ticket(business, 'session', expectedSessionId)),
    apply: async (business: Business, expectedSessionId?: string) => request(`${businessBase(business)}/auth/identity/application`, isApplication, await ticket(business, 'application', expectedSessionId)),
    withdraw: async (business: Business, expectedSessionId?: string) => request(`${businessBase(business)}/auth/identity/application/withdraw`, isApplication, await ticket(business, 'application', expectedSessionId)),
    overseasMe: () => request('/api/overseas/v1/auth/me', memberGuard('overseas')),
    async logout() {
      await request(`${base}/logout`, noContent, {})
      const results = await Promise.allSettled(['domestic', 'overseas'].map(business => request(`${businessBase(business as Business)}/auth/logout`, noContent, {})))
      if (results.some(result => result.status === 'rejected')) throw new IdentityError(0, '统一身份已退出，部分业务退出未完成，请重试')
    }
  }
}
export const identityApi = createIdentityApi()
