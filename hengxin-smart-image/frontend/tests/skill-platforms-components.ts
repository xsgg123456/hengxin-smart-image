import * as Transfers from '../src/api/overseas/skill-transfers'
import * as Management from '../src/api/overseas/management'
import { OVERSEAS_PLATFORMS } from '../src/views/overseas/platforms'
import { IdentityError } from '../src/api/identity/request'
import { compile, table, simple } from './membership-test-harness'
export const confirmation = { accept: true }
export const platformDialog = compile('views/shared/skills/OverseasSkillPlatformsDialog.vue', { './platforms': { OVERSEAS_PLATFORMS } })
Object.assign(platformDialog, { components: { ElCheckboxGroup: simple('ElCheckboxGroup'), ElCheckbox: simple('ElCheckbox') } })
export const skillCatalogComponent = compile('views/shared/skills/OverseasSkillCatalog.vue', {
  '@/components/core/tables/art-table/index.vue': { default: table, __esModule: true },
  './SkillFolderActions.vue': { default: simple('SkillFolderActions'), __esModule: true },
  './platforms': { OVERSEAS_PLATFORMS }, './OverseasSkillPlatformsDialog.vue': { default: platformDialog, __esModule: true },
  'element-plus': { ElMessageBox: { confirm: async () => { if (!confirmation.accept) throw Error('cancel') } } }
})
export const liveSkillsComponent = compile('views/shared/skills/OverseasLiveSkills.vue', {
  '@/api/shared/skill-transfers': Transfers, './SkillFolderUpload.vue': { default: simple('SkillFolderUpload'), __esModule: true },
  '@/api/shared/skill-types': Management, '@/api/identity/request': { IdentityError },
  './OverseasSkillCatalog.vue': { default: skillCatalogComponent, __esModule: true }
})
