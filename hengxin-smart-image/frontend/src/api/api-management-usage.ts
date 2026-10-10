import { createRequest } from './hengxin/http'
import { apiUsageReport } from './api-management-usage-validate'
import type { ApiUsageQuery } from '../types/api-management-usage'
export function createApiUsageClient(baseUrl: string, fetcher: typeof fetch = fetch) {
  const request = createRequest(baseUrl, fetcher)
  return (query: ApiUsageQuery) => {
    const params = new URLSearchParams()
    Object.entries(query).forEach(([key, value]) => { if (value !== undefined && value !== '') params.set(key, String(value)) })
    return request(`/management/api-usage?${params}`, apiUsageReport)
  }
}
export const getApiUsage = createApiUsageClient(import.meta.env?.VITE_API_URL || '/api/v1')
