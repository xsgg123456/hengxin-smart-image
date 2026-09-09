import { getService } from './hengxin/client'
import type { PageQuery } from '@/types/hengxin'
export const listArchives = async (query: PageQuery) => (await getService()).listArchives(query)
export const getArchive = async (id: string) => (await getService()).getArchive(id)
export const archiveTask = async (taskId: string) => (await getService()).archive(taskId)
export const deleteArchive = async (id: string) => (await getService()).deleteArchive(id)
