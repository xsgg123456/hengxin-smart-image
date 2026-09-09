import { getService } from './hengxin/client'
import type { CreateTaskInput, TaskQuery } from '@/types/hengxin'
export const createTask = async (input: CreateTaskInput, idempotencyKey?: string) => (await getService()).createTask(input, idempotencyKey)
export const listTasks = async (query: TaskQuery) => (await getService()).listTasks(query)
export const getTask = async (id: string) => (await getService()).getTask(id)
export const deleteTask = async (id: string) => (await getService()).deleteTask(id)
