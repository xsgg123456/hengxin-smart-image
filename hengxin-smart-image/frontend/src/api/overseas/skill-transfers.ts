import { createSkillTransferApi as createSharedSkillTransferApi } from '../shared/skill-transfers'
export * from '../shared/skill-transfers'

export function createSkillTransferApi(fetcher: typeof fetch = fetch, base = '/api/overseas/v1/management') {
  return createSharedSkillTransferApi(fetcher, base)
}
