export type ReleaseScope = 'domestic' | 'overseas' | 'shared'
type EntryLocation = Pick<Location, 'pathname' | 'search' | 'hash'>

export function isIndependentRelease(): boolean {
  return !!import.meta.env?.VITE_RELEASE_SCOPE
}

export function releaseDestination(scope: ReleaseScope, route: string, search = ''): string {
  return `${isIndependentRelease() ? `/${scope}/` : '/'}${search}#${route}`
}

export function entryDestination(scope: ReleaseScope, location: EntryLocation): string | undefined {
  const path = location.hash.split('?')[0]
  // A bare scoped business URL opens that business; a root legacy URL opens identity.
  const scoped = /^\/(domestic|overseas|shared)(?:\/|$)/.test(location.pathname)
  let target: ReleaseScope = scoped ? scope : 'shared'
  if (path.startsWith('#/auth/') || path === '#/auth') target = 'shared'
  else if (path === '#/overseas' || path.startsWith('#/overseas/')) target = 'overseas'
  else if (path && path !== '#/') target = 'domestic'
  const hash = location.hash && location.hash !== '#/' ? location.hash
    : target === 'overseas' ? '#/overseas/tasks' : target === 'domestic' ? '#/api-image-edits/create' : '#/auth/business'
  const destination = `/${target}/${location.search}${hash}`
  return destination === `${location.pathname}${location.search}${location.hash}` ? undefined : destination
}

export function redirectReleaseEntry(): boolean {
  const scope = import.meta.env?.VITE_RELEASE_SCOPE as ReleaseScope | undefined
  if (!scope) return false
  const destination = entryDestination(scope, window.location)
  if (!destination) return false
  const target = new URL(destination, window.location.href)
  if (target.pathname === window.location.pathname && target.search === window.location.search) {
    // A hash-only replace does not reload this document: let its entrypoint bootstrap.
    window.history.replaceState(window.history.state, '', destination)
    return false
  }
  window.location.replace(destination)
  return true
}
