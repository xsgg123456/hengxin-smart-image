import { getService } from './hengxin/client'
import type { RevisionInput } from '@/types/hengxin'
export const submitRevision = async (input: RevisionInput, idempotencyKey?: string) => (await getService()).revise(input, idempotencyKey)
