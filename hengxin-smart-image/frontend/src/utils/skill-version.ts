// SemVer 2.0.0: https://semver.org/ (ASCII only; registration limit: 100 characters).
const SEMVER = /^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$/

export function isSkillVersion(value: string): boolean {
  if (value.length > 100 || /[^0-9A-Za-z.+-]/.test(value)) return false
  const match = SEMVER.exec(value)
  if (!match) return false
  return !match[4]?.split('.').some(part => /^[0-9]+$/.test(part) && part.length > 1 && part.startsWith('0'))
}
