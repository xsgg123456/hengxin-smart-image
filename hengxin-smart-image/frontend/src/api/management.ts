import type { ManagementService } from '../types/management'
import { getService } from './hengxin/client'
import { createRequest } from './hengxin/http'
import * as guard from './hengxin/validate-management'
import { isApplication, isApplicationPage } from './identity/applications'
export function createHttpManagement(baseUrl: string, fetcher: typeof fetch = fetch): ManagementService {
  const request = createRequest(baseUrl, fetcher)
  const queryString = (q: object) => { const p = new URLSearchParams(); Object.entries(q).forEach(([k, v]) => { if (v !== undefined) p.set(k, String(v)) }); return p.toString() }
  return {
    listApplications: q => request(`/management/users/applications?${queryString(q)}`, isApplicationPage),
    decideApplication: (id, input) => request(`/management/users/applications/${encodeURIComponent(id)}/decision`, isApplication, 'POST', input, 10000, { 'X-HX-Request': '1' }),
    listUsers: q => request(`/management/users?${queryString(q)}`, guard.userPage),
    saveUser: input => request(`/management/users/${encodeURIComponent(input.id)}`, guard.managedUser, 'PUT', input),
    getSettings: () => request('/management/settings', guard.settings),
    saveSettings: input => request('/management/settings', guard.settings, 'PUT', input)
  }
}
export const managementApi: ManagementService = {
  listApplications: async q => (await getService()).listApplications(q),
  decideApplication: async (id, input) => (await getService()).decideApplication(id, input),

  listUsers: async q => (await getService()).listUsers(q),
  saveUser: async input => (await getService()).saveUser(input),
  getSettings: async () => (await getService()).getSettings(),
  saveSettings: async input => (await getService()).saveSettings(input)
}


export const { listUsers, saveUser, getSettings, saveSettings } = managementApi
