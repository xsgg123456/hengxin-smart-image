import { createIdentityRequest, record } from '../identity/request'

export const memberRoles = { operator: '运营', operator_manager: '运营主管', designer: '设计', design_manager: '设计主管', super_admin: '超级管理员' }
export type MemberRole = keyof typeof memberRoles
export type MemberStatus = 'active' | 'pending' | 'disabled'
export interface OverseasMember {
  id: string; name: string; department: string; roles: MemberRole[]; status: MemberStatus
  version: number; createdAt: string; updatedAt: string
}
export interface MemberQuery { search: string; status: string; role: string; page: number; pageSize: number }
export interface MemberPage { items: OverseasMember[]; total: number; page: number; pageSize: number }
export interface MembersAdapter {
  preview?: boolean
  list(query: MemberQuery): Promise<MemberPage>
  get(id: string): Promise<OverseasMember>
  save(member: OverseasMember): Promise<OverseasMember>
  remove?(id: string): Promise<void>
}
export function isOverseasMember(v: unknown): v is OverseasMember {
  return record(v) && typeof v.id === 'string' && typeof v.name === 'string' && typeof v.department === 'string'
    && Array.isArray(v.roles) && v.roles.every(r => typeof r === 'string' && Object.hasOwn(memberRoles, r))
    && ['active', 'pending', 'disabled'].includes(String(v.status)) && Number.isInteger(v.version) && Number(v.version) >= 1
    && typeof v.createdAt === 'string' && typeof v.updatedAt === 'string'
}
export function createMembersApi(fetcher: typeof fetch = fetch): MembersAdapter {
  const request = createIdentityRequest(fetcher), base = '/api/overseas/v1/members'
  return {
    list: query => request(base, (v): v is MemberPage => record(v) && Array.isArray(v.items) && v.items.every(isOverseasMember)
      && Number.isInteger(v.total) && Number(v.total) >= 0 && Number.isInteger(v.page) && Number(v.page) > 0
      && Number.isInteger(v.pageSize) && Number(v.pageSize) > 0, undefined, { params: { ...query } }),
    get: id => request(`${base}/${encodeURIComponent(id)}`, isOverseasMember),
    save: member => request(`${base}/${encodeURIComponent(member.id)}`, isOverseasMember,
      { roles: [...new Set(member.roles)], status: member.status, version: member.version }, { method: 'PATCH' })
  }
}
