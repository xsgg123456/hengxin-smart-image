import { redirectReleaseEntry } from './navigation'
window.addEventListener('hashchange', redirectReleaseEntry)
if (!redirectReleaseEntry()) void import('../identity-bootstrap').then(({ mountIdentityPortal }) => mountIdentityPortal())
