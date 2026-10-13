import { members, saveMember, removeRecord, type Member } from './management-adapter'
import type { MembersAdapter, OverseasMember } from '@/api/overseas/members'
const convert = (m: Member): OverseasMember => ({ id: m.id, name: m.name, department: m.department,
  roles: [m.role === 'admin' ? 'super_admin' : m.role], status: m.enabled ? 'active' : 'disabled', version: 1, createdAt: '', updatedAt: '' })
export const previewMembers: MembersAdapter = {
  preview: true,
  async list(query) {
    const rows = members.map(convert).filter(m => `${m.name} ${m.department}`.toLowerCase().includes(query.search.trim().toLowerCase())
      && (!query.status || m.status === query.status) && (!query.role || m.roles.includes(query.role as OverseasMember['roles'][number])))
    return { items: rows.slice((query.page - 1) * query.pageSize, query.page * query.pageSize), total: rows.length, page: query.page, pageSize: query.pageSize }
  },
  async get(id) { const m = members.find(m => m.id === id); if (!m) throw new Error('成员不存在'); return convert(m) },
  async save(m) {
    const role = m.roles[0]
    saveMember({ id: m.id, name: m.name, department: m.department, role: role === 'super_admin' ? 'admin' : role === 'designer' ? 'designer' : 'operator', enabled: m.status === 'active' })
    return m
  },
  async remove(id) { removeRecord(members, id) }
}
