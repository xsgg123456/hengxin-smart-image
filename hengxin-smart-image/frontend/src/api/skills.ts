import type { Mode } from '../types/hengxin'
import { getService } from './hengxin/client'
export async function listSkills(mode?: Mode) { return (await getService()).listSkills(mode) }
