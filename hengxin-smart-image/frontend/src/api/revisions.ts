import { getService } from './hengxin/client'
import type { RevisionInput } from '@/types/hengxin'
export const submitRevision = async (input: RevisionInput) => (await getService()).revise(input)
