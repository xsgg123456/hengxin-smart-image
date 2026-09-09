import type { ManagementService } from '../types/management'
import { getService } from './hengxin/client'
import { createRequest } from './hengxin/http'
import * as guard from './hengxin/validate-management'
export function createHttpManagement(baseUrl: string, fetcher: typeof fetch = fetch): ManagementService {
  const request = createRequest(baseUrl, fetcher)
  const queryString = (q: object) => { const p = new URLSearchParams(); Object.entries(q).forEach(([k, v]) => { if (v !== undefined) p.set(k, String(v)) }); return p.toString() }
  return {
    getUsage: q => request(`/management/usage?${queryString(q)}`, guard.usage),
    getMonitor: () => request('/management/monitor', guard.monitor),
    listUsers: q => request(`/management/users?${queryString(q)}`, guard.userPage),
    saveUser: input => request(`/management/users/${encodeURIComponent(input.id)}`, guard.managedUser, 'PUT', input),
    listManagedSkills: () => request('/management/skills', guard.managedSkills),
    uploadSkill: (file, mode, version) => { const data = new FormData(); data.append('file', file); data.append('mode', mode); data.append('version', version); return request('/management/skills', guard.managedSkill, 'POST', data) },
    installSkill: id => request(`/management/skills/${encodeURIComponent(id)}/install`, guard.managedSkill, 'POST'),
    setSkillStatus: (id, status) => request(`/management/skills/${encodeURIComponent(id)}/status`, guard.managedSkill, 'PUT', { status }),
    getSettings: () => request('/management/settings', guard.settings),
    saveSettings: input => request('/management/settings', guard.settings, 'PUT', input)
  }
}
export const managementApi: ManagementService = {
  getUsage: async q => (await getService()).getUsage(q),
  getMonitor: async () => (await getService()).getMonitor(),
  listUsers: async q => (await getService()).listUsers(q),
  saveUser: async input => (await getService()).saveUser(input),
  listManagedSkills: async () => (await getService()).listManagedSkills(),
  uploadSkill: async (file, mode, version) => (await getService()).uploadSkill(file, mode, version),
  installSkill: async id => (await getService()).installSkill(id),
  setSkillStatus: async (id, status) => (await getService()).setSkillStatus(id, status),
  getSettings: async () => (await getService()).getSettings(),
  saveSettings: async input => (await getService()).saveSettings(input)
}
export const { getUsage, getMonitor, listUsers, saveUser, listManagedSkills, uploadSkill, installSkill, setSkillStatus, getSettings, saveSettings } = managementApi
