import type { ManagementService } from './management'
export type Role = 'super_admin' | 'design_manager' | 'designer' | 'operator'
export interface User {
  id: string
  name: string
  identitySessionId: string | null
  role: Role | null
  status: 'pending' | 'active' | 'disabled'
}
export interface FileRecord {
  id: string
  name: string
  mimeType: string
  size: number
  width: number
  height: number
  ownerId: string
  url: string
  urlExpiresAt: string | null
}
export interface Picture { name: string; url: string; version?: number; fileId?: string }
export interface SystemConfig {
  version: number
  concurrency: number
  timeoutSeconds: number
  maxUploadBytes: number
}
export interface PageQuery { page: number; pageSize: number; search?: string }
export interface PageResult<T> { items: T[]; page: number; pageSize: number; total: number }
export interface ApiErrorBody { code: string; message: string; requestId?: string }
export interface HengxinService extends ManagementService {
  getUser(): Promise<User>
  dispose(): void
}
