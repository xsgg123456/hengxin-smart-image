import type { Picture, User } from '../../types/hengxin'
type Guard<T> = (value: unknown) => value is T
const record = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const text = (value: unknown): value is string => typeof value === 'string'
const id = (value: unknown): value is string => text(value) && value.trim().length > 0
const number = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const picture: Guard<Picture> = (value): value is Picture => record(value) && text(value.name) && text(value.url)
  && (value.version === undefined || (number(value.version) && value.version >= 1))
  && (value.fileId === undefined || id(value.fileId))
export const uploadedPicture: Guard<Picture> = (value): value is Picture => picture(value) && id(value.fileId)
export const user: Guard<User> = (value): value is User => record(value) && id(value.id) && text(value.name)
  && text(value.status) && ['pending', 'active', 'disabled'].includes(value.status)
  && (value.role === null || (text(value.role) && ['super_admin', 'design_manager', 'designer', 'operator'].includes(value.role)))
export const noContent: Guard<void> = (value): value is void => value === undefined
