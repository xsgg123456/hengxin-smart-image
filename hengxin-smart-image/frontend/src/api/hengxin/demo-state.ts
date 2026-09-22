import type { Accepted, Picture, ResultSlot, Round, SkillVersion, Task, Template, Workspace } from '../../types/hengxin'
import type { CatalogSkill, ManagedSettings, ManagedSkill, ManagedUser, SkillSync } from '../../types/management'
export interface DemoState {
  schema: 1
  workspace: Workspace
  files?: [string, Picture][]
  templateHistory?: [string, Template[]][]
  skills?: SkillVersion[]
  slots?: [string, ResultSlot[]][]
  rounds?: [string, Round[]][]
  taskHistory?: [string, Task][]
  submissions?: [string, { fingerprint: string; accepted: Accepted }][]
  revisions?: [string, { fingerprint: string; receipt: Accepted }][]
  failures?: [string, boolean][]
  scenarioUsed?: boolean
  catalogConsumed?: string[]
  archiveFailureUsed?: boolean
  users?: ManagedUser[]
  settings?: ManagedSettings
  skillMetadata?: [string, Omit<ManagedSkill, keyof SkillVersion>][]
  skillJobs?: [string, number][]
  skillFailedOnce?: string[]
  skillCatalogMetadata?: [string, CatalogSkill][]
  skillCatalogSource?: SkillVersion[]
  skillCatalogSync?: SkillSync
  skillCatalogDeadlineAt?: number
  skillCatalogDisabled?: string[]
  skillCatalogFailedOnce?: boolean
}
