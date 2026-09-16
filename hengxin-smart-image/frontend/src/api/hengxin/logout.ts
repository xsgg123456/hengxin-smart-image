import { createRequest } from './http'
import { noContent } from './validate'
import { safeReturnPath } from './session'

export async function logoutSession(baseUrl: string, fetcher: typeof fetch = fetch): Promise<void> {
  await createRequest(baseUrl, fetcher)('/auth/logout', noContent, 'POST')
}

export function logoutDestination(href: string): string {
  const url = new URL(href)
  const redirect = safeReturnPath(url.hash.slice(1))
  url.pathname = '/'
  url.search = ''
  url.hash = `/auth/login?redirect=${encodeURIComponent(redirect)}`
  return url.href
}
