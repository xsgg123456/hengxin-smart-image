// Minimal stateful API fixture for the real card form and its autosave.
export function designCenterDraft() {
  const draft = { id: 'draft', version: 1, submitKey: 'draft-key', updatedAt: '2026-11-20',
    source: null, materials: [], imports: [], fields: { name: '', productName: '', brand: '',
      platform: '', market: '', language: '', designerId: '', skus: [{ code: '' }] } }
  return request => {
    if (request.method() === 'PUT') {
      draft.fields = request.postDataJSON().fields
      draft.version++
    }
    return draft
  }
}
