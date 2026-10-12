const path = window.location.hash.split('?')[0]
const mock = ['mock', 'demo'].includes(import.meta.env.MODE)
const unified = !mock && (!path || path === '#/' || path.startsWith('#/auth/') || path.startsWith('#/overseas'))
if (unified) void import('./identity-main')
else void import('./domestic-main')
