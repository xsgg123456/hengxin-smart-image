import type { MockScenario } from './mock-catalog'
import type { HengxinService } from '../../types/hengxin'
import { createHttpService } from './http'
import { createHttpManagement } from '../management'

// 只有显式 mock 模式加载模拟模块；生产构建采用真实 HTTP，不回退。
export const isMockMode = import.meta.env?.MODE === 'mock'
let service: Promise<HengxinService> | undefined
export function getService(): Promise<HengxinService> {
  service ??= isMockMode
    ? import('./mock').then(({ createMockService }) => {
      const value = new URLSearchParams(window.location.search).get('scenario') ?? 'default'
      const scenario = ['default', 'empty', 'no-skills', 'upload-error', 'save-error', 'submit-error', 'list-error', 'execution-error', 'partial-result', 'revision-error', 'archive-error'].includes(value) ? value as MockScenario : 'default'
      const managementValue = new URLSearchParams(window.location.search).get('managementScenario') || 'default'
      const managementScenario = ['default', 'empty', 'unknown', 'idle', 'unavailable', 'list-error', 'save-error', 'install-error', 'worker-lost', 'auth-rejected', 'rate-limited', 'timeout'].includes(managementValue) ? managementValue as import('../../types/management').ManagementScenario : 'default'
      return createMockService({ scenario, managementScenario })
    })
    : Promise.resolve({ ...createHttpService(import.meta.env.VITE_API_URL || '/api/v1'), ...createHttpManagement(import.meta.env.VITE_API_URL || '/api/v1') })
  return service
}
