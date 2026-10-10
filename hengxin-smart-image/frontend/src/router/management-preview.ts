/** Explicit local mock preview; query parameters can never switch production pages. */
export function managementComponent(page: string, mode: string | undefined, search: string) {
  const previews: Record<string, string> = {
    usage: 'UsagePreview', monitor: 'MonitorPreview', settings: 'SettingsPreview'
  }
  return mode === 'mock' && new URLSearchParams(search).get('managementPreview') === 'api' && previews[page]
    ? `/hengxin/admin/preview/${previews[page]}` : `/hengxin/admin/${page}`
}
