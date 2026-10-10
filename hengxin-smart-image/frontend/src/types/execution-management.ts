export type ServiceState = 'available' | 'unavailable' | 'unknown'
export interface QueueMetric { phase: string; tasks: number | null; images: number | null; turns: number | null }
export interface ChannelMonitor {
  concurrencyLimit: number | null; imagesPerBatch: number | null
  enabled: boolean; paused: boolean | null; pauseReason: string | null; sharedActiveTurns: number | null; otherActiveTurns: number | null
  channel: 'api' | 'cli'; state: ServiceState; queueState: 'available' | 'unknown'
  workers: { id: string; checkedAt: string; state: ServiceState; capacity: number | null }[]
  metrics: QueueMetric[]
}
export interface ApiMonitorReport {
  checkedAt: string; channels: ChannelMonitor[]; incidentsTruncated: boolean
  incidents: { taskId: string; name: string; channel: 'api' | 'cli'; phase: string; images: number }[]
}
export interface ExecutionSettings {
  api: { enabled: boolean; taskConcurrency: number; imagesPerBatch: number; requestTimeoutSeconds: number; downloadTimeoutSeconds: number; leaseSeconds: number; model: string; quality: string; resolution: string; imagesPerRequest: number; sizePolicy: string }
  cli: { enabled: boolean; concurrency: number; capacity: number; timeoutSeconds: number; timeoutCapacity: number; model: string; reasoningEffort: string; usesSkills: boolean }
  maxUploadBytes: number
  retention: { enabled: boolean; cacheIdleDays: number; historyIdleDays: number }
}
