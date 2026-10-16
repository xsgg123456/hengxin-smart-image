import type { ManagedSettings, SettingsInput } from '../../types/management'
import { ApiError } from './http'
export function validateSettings(input: SettingsInput, current: ManagedSettings) {
  const ranges = [[input.concurrency, 1, current.capacity], [input.timeoutSeconds, 60, current.timeoutCapacity], [input.maxUploadBytes, 1048576, 10485760]]
  if (ranges.some(([value, min, max]) => !Number.isInteger(value) || value < min || value > max)) throw new ApiError('VALIDATION', `并发 1–${current.capacity}，超时 60–${current.timeoutCapacity} 秒，上传 1–10 MiB，必须为整数`, 422)
  if ((['corpId', 'appId', 'callbackDomain'] as const).some(key => input.dingtalk[key] !== current.dingtalk[key])) throw new ApiError('VALIDATION', '钉钉接入由部署环境管理，网页只读', 422)
}
