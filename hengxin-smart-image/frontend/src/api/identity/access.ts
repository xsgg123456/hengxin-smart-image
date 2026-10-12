export type Business = 'domestic' | 'overseas'
export interface BusinessAccess { authenticated: boolean; domestic: boolean; overseas: boolean }
export function mayEnter(identity: BusinessAccess, business: Business): boolean {
  return identity.authenticated && identity[business]
}
