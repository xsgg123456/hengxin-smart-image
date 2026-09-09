import { getService } from './hengxin/client'
import type { TaskQuery } from '@/types/hengxin'
export const listTasks = async (query: TaskQuery) => (await getService()).listTasks(query)
export const getTask = async (id: string) => (await getService()).getTask(id)
export const deleteTask = async (id: string) => (await getService()).deleteTask(id)
