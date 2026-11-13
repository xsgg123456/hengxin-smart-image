import { createIdentityRequest, record } from '@/api/identity/request'
import { isManagedSkill, type SkillCatalog, type SkillPlatformUpdate } from '@/api/shared/skill-types'
import { createSkillTransferApi } from '@/api/shared/skill-transfers'

export const studioSkillsRoot = '/api/v1/management/domestic-studio'
export const workspaceKeys = ['camera', 'case', 'product', 'scene', 'phone'] as const
export type WorkspaceKey = typeof workspaceKeys[number]
export type WorkspaceBindings = Record<WorkspaceKey, string | null>
const isBindings = (value: unknown): value is { bindings: WorkspaceBindings } => record(value)
  && record(value.bindings) && Object.keys(value.bindings).length === workspaceKeys.length
  && workspaceKeys.every(key => record(value.bindings) && (value.bindings[key] === null || typeof value.bindings[key] === 'string'))
const isItems = (value: unknown): value is { items: SkillCatalog['items'] } => record(value)
  && Array.isArray(value.items) && value.items.every(isManagedSkill)

export function createDomesticStudioSkillsApi(fetcher: typeof fetch = fetch) {
  const request = createIdentityRequest(fetcher)
  const catalog = (value: { items: SkillCatalog['items'] }): SkillCatalog => ({ ...value, canToggle: true, canManagePlatforms: false })
  return {
    transfers: createSkillTransferApi(fetcher, studioSkillsRoot),
    async skills() { return catalog(await request(`${studioSkillsRoot}/skills`, isItems)) },
    async setSkillAvailability(id: string, enabled: boolean, version: number) {
      return catalog(await request(`${studioSkillsRoot}/skills/${encodeURIComponent(id)}/availability`, isItems,
        { enabled, version }, { method: 'PATCH' }))
    },
    async setSkillPlatforms(_items: SkillPlatformUpdate[]): Promise<SkillCatalog> { throw new Error('国内 Skill 不使用平台分组') },
    getBindings: () => request(`${studioSkillsRoot}/bindings`, isBindings),
    setBindings: (bindings: WorkspaceBindings, expected: WorkspaceBindings) => request(`${studioSkillsRoot}/bindings`, isBindings, { bindings, expected }, { method: 'PUT' }),
  }
}
export type DomesticStudioSkillsApi = ReturnType<typeof createDomesticStudioSkillsApi>
