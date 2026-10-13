import { createIdentityRequest, record } from './request'
import type { Business } from './access'

export interface MembershipApplication {
  id: string; name: string; status: 'pending' | 'approved' | 'rejected' | 'withdrawn'
  version: number; createdAt: string; updatedAt: string; reason?: string | null
}
export interface ApplicationQuery { page: number; pageSize: number; status?: string; search?: string }
export interface ApplicationPage { items: MembershipApplication[]; total: number; page: number; pageSize: number }
export interface ApplicationDecision { decision: 'approve' | 'reject'; role?: string; version: number; reason?: string }
export interface ApplicationsAdapter {
  listApplications(query: ApplicationQuery): Promise<ApplicationPage>
  decideApplication(id: string, input: ApplicationDecision): Promise<MembershipApplication>
}
export const applicationStatuses = { pending: '待审批', approved: '已通过', rejected: '已拒绝', withdrawn: '已撤回' }
export function isApplication(v: unknown): v is MembershipApplication {
  return record(v) && typeof v.id === 'string' && !!v.id && typeof v.name === 'string'
    && typeof v.status === 'string' && Object.hasOwn(applicationStatuses, v.status)
    && Number.isInteger(v.version) && Number(v.version) > 0
    && typeof v.createdAt === 'string' && typeof v.updatedAt === 'string'
    && (v.reason == null || typeof v.reason === 'string')
}
export function isApplicationPage(v: unknown): v is ApplicationPage {
  return record(v) && Array.isArray(v.items) && v.items.every(isApplication)
    && Number.isInteger(v.total) && Number(v.total) >= 0 && Number.isInteger(v.page) && Number(v.page) > 0
    && Number.isInteger(v.pageSize) && Number(v.pageSize) > 0
}
export function createApplicationsApi(business: Business, fetcher: typeof fetch = fetch): ApplicationsAdapter {
  const request = createIdentityRequest(fetcher)
  const base = business === 'domestic' ? '/api/v1/management/users/applications' : '/api/overseas/v1/members/applications'
  return {
    listApplications: query => request(base, isApplicationPage, undefined, { params: { ...query } }),
    decideApplication: (id, input) => request(`${base}/${encodeURIComponent(id)}/decision`, isApplication, input)
  }
}
