import type { Plugin } from 'vite'

export type ReleaseScope = 'domestic' | 'overseas' | 'shared'
export function parseReleaseScope(value?: string): ReleaseScope | undefined {
  if (!value) return undefined
  if (value === 'domestic' || value === 'overseas' || value === 'shared') return value
  throw new Error(`Invalid VITE_RELEASE_SCOPE: ${value}`)
}

// Select a single module graph before Rollup resolves imports, retaining index.html.
export function releaseScopePlugin(scope?: ReleaseScope): Plugin {
  return {
    name: 'hengxin-release-scope',
    transformIndexHtml: {
      order: 'pre',
      handler(html) {
        return scope ? html.replace('/src/main.ts', `/src/release/${scope}-entry.ts`) : html
      }
    },
    generateBundle(_options, bundle) {
      if (!scope) return
      const modules = [...new Set(Object.values(bundle).flatMap(item => item.type === 'chunk' ? Object.keys(item.modules) : []))]
        .map(id => id.replaceAll('\\', '/')).filter(id => id.includes('/src/'))
        .map(id => id.slice(id.lastIndexOf('/src/') + 1)).sort()
      const forbidden = modules.filter(id => scope !== 'overseas' && (id.startsWith('src/views/overseas/') || id.startsWith('src/api/overseas/')))
      if (scope !== 'domestic') forbidden.push(...modules.filter(id => id.startsWith('src/views/hengxin/') && !id.startsWith('src/views/hengxin/components/') && id.endsWith('.vue')))
      if (forbidden.length) this.error(`${scope} release includes other business implementation: ${forbidden.join(', ')}`)
      this.emitFile({ type: 'asset', fileName: 'release-scope.json', source: JSON.stringify({ scope, base: `/${scope}/`, modules }, null, 2) })
    }
  }
}
