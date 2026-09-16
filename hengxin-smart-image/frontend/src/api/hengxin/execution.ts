import { isMockMode } from './client'
import { ApiError, createRequest } from './http'
import { isExecutionData } from './execution-data'

export async function getExecution(taskId: string, roundId: string) {
  if (isMockMode) throw new ApiError('MOCK_EXECUTION', '演示模式不提供真实执行过程')
  const request = createRequest(import.meta.env.VITE_API_URL || '/api/v1')
  return request(`/tasks/${encodeURIComponent(taskId)}/execution?roundId=${encodeURIComponent(roundId)}`, isExecutionData)
}
