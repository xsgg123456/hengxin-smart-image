import * as Management from '../src/api/overseas/management'
import { OVERSEAS_PLATFORMS } from '../src/views/overseas/platforms'
import { IdentityError } from '../src/api/identity/request'
import { compile, table, simple } from './membership-test-harness'
export const confirmation = { accept: true }
export const platformDialog = compile('views/overseas/admin/OverseasSkillPlatformsDialog.vue', { '../platforms': { OVERSEAS_PLATFORMS } })
Object.assign(platformDialog, { components: { ElCheckboxGroup: simple('ElCheckboxGroup'), ElCheckbox: simple('ElCheckbox') } })
export const skillCatalogComponent = compile('views/overseas/admin/OverseasSkillCatalog.vue', {
  '@/components/core/tables/art-table/index.vue': { default: table, __esModule: true },
  '../platforms': { OVERSEAS_PLATFORMS }, './OverseasSkillPlatformsDialog.vue': { default: platformDialog, __esModule: true },
  'element-plus': { ElMessageBox: { confirm: async () => { if (!confirmation.accept) throw Error('cancel') } } }
})
export const liveSkillsComponent = compile('views/overseas/admin/OverseasLiveSkills.vue', {
  '@/api/overseas/management': Management, '@/api/identity/request': { IdentityError },
  './OverseasSkillCatalog.vue': { default: skillCatalogComponent, __esModule: true }
})
