import { redirectReleaseEntry } from './navigation'
window.addEventListener('hashchange', redirectReleaseEntry)
if (!redirectReleaseEntry()) void import('../identity-main')
