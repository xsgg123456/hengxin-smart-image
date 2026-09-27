// Local browser contract fixtures. No real API, identity provider or model calls.
export function templates(user) {
  return Array.from({ length: 12 }, (_, index) => ({
    id: `template-${index}`, name: `${user.name}模板${index}`, mode: 'wallpaper',
    skill: '', skillVersionId: null, active: false, version: 1,
    ownerId: user.id, notes: '', updatedAt: '2026-01-01T00:00:00Z',
    images: Array.from({ length: index < 11 ? 4 : 0 }, (_, image) => ({
      fileId: `00000000-0000-4000-8000-${String(index * 4 + image).padStart(12, '0')}`, name: `图片${index}-${image}`,
      url: `/api/v1/files/00000000-0000-4000-8000-${String(index * 4 + image).padStart(12, '0')}/content`
    }))
  }))
}

export async function intercept(context, origin, state) {
  await context.route('**/*', async route => {
    const url = new URL(route.request().url())
    if (url.origin !== origin) return route.abort('blockedbyclient')
    if (!url.pathname.startsWith('/api/')) return route.continue()
    state.apiCalls?.push(url.pathname + url.search)
    const json = (value, status = 200) => route.fulfill({ status,
      contentType: 'application/json', body: JSON.stringify(value) })
    if (url.pathname.endsWith('/auth/me')) {
      state.authCalls++
      if (state.authBarrier) await state.authBarrier
      return state.disabled ? json({ code: 'HTTP_ERROR', message: '账号未授权或已停用' }, 403)
        : json(state.user)
    }
    if (url.pathname.endsWith('/auth/dingtalk/config')) {
      return json({ configured: false, corpId: '', clientId: '', callbackPath: '' })
    }
    if (url.pathname.endsWith('/test-old')) {
      state.oldStarted?.()
      await state.oldBarrier
      try { return await json({ value: 'old-A' }, state.oldStatus || 200) }
      catch { return undefined } // A cancelled read cannot be fulfilled after the epoch changes.
    }
    if (url.pathname.endsWith('/templates')) {
      const items = templates(state.user)
      return json({ items, total: items.length, page: 1, pageSize: 12 })
    }
    if (url.pathname.endsWith('/skills') || url.pathname.endsWith('/skill-catalog')) return json([])
    if (url.pathname.endsWith('/tasks')) {
      return json({ items: [], total: 0, page: 1, pageSize: 12,
        stats: { total: 0, processing: 0, ready: 0, archived: 0 } })
    }
    if (/\/files\/[^/]+\/content$/.test(url.pathname)) {
      state.imageCalls++
      if (state.imageResponse) return state.imageResponse(route, url)
      // Hold the burst so all 44 native requests fail in the same window.
      if (state.imageBarrier) await state.imageBarrier
      return route.fulfill({ status: state.disabled ? 403 : 404, body: '' })
    }
    state.unexpected.push(`${route.request().method()} ${url.pathname}`)
    return json({ code: 'UNEXPECTED_TEST_REQUEST', message: url.pathname }, 501)
  })
}
