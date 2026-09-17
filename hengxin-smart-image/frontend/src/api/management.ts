import type { ManagementService } from '../types/management'
import { getService } from './hengxin/client'
import { createRequest } from './hengxin/http'
import { noContent } from './hengxin/validate'
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
    getSkillDefaults: () => request('/management/skills/defaults', guard.skillDefaults),
    saveSkillDefaults: input => request('/management/skills/defaults', guard.skillDefaults, 'PUT', input),
    registerSkill: input => request('/management/skills/register', guard.managedSkill, 'POST', input),
    checkSkill: id => request(`/management/skills/${encodeURIComponent(id)}/check`, guard.managedSkill, 'POST'),
    removeSkill: id => request(`/management/skills/${encodeURIComponent(id)}`, noContent, 'DELETE'),
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
  getSkillDefaults: async () => (await getService()).getSkillDefaults(),
  saveSkillDefaults: async input => (await getService()).saveSkillDefaults(input),
  registerSkill: async input => (await getService()).registerSkill(input),
  checkSkill: async id => (await getService()).checkSkill(id),
  removeSkill: async id => (await getService()).removeSkill(id),
  setSkillStatus: async (id, status) => (await getService()).setSkillStatus(id, status),
  getSettings: async () => (await getService()).getSettings(),
  saveSettings: async input => (await getService()).saveSettings(input)
}
export const { getUsage, getMonitor, listUsers, saveUser, listManagedSkills, getSkillDefaults, saveSkillDefaults, registerSkill, checkSkill, removeSkill, setSkillStatus, getSettings, saveSettings } = managementApi
