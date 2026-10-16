import type { HengxinService, User } from '../../types/hengxin'
import type { DemoState } from './demo-state'
import type { ManagementScenario } from '../../types/management'
import { createMockManagement } from './mock-management'
import { getPreviewUser } from './session'

/** 显式预览仅模拟身份和管理配置；API与海外拥有各自独立的预览状态。 */
export function createMockService(options: { snapshot?: DemoState; delayMs?: number; managementScenario?: ManagementScenario; user?: User } = {}): HengxinService & { snapshot: () => DemoState } {
  let user = structuredClone(options.user ?? getPreviewUser())
  const stored = options.snapshot?.users?.find(item => item.id === user.id)
  if (stored) user = structuredClone(stored)
  const management = createMockManagement(() => user, {
    snapshot: options.snapshot, scenario: options.managementScenario,
    wait: () => new Promise(resolve => setTimeout(resolve, options.delayMs ?? 120)),
    onUserChanged(updated) {
      if (updated.id !== user.id) return
      user = structuredClone(updated)
      if (typeof window !== 'undefined') window.dispatchEvent(new Event('hengxin:identity-changed'))
    }
  })
  return {
    ...management,
    async getUser() { return structuredClone(user) },
    dispose() {},
    snapshot: () => ({ schema: 2, ...management.snapshot() })
  }
}
