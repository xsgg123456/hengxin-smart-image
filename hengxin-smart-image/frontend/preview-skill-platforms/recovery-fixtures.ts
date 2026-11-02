import type { createStudioOutputsApi, RecoverableFile } from '@/api/overseas/studio-outputs'

// Local UI fixtures only; no production files or requests.
const files: RecoverableFile[] = [
  { id: 'archive', name: 'OUTON_H-ZGD0008_第02-09页成品.zip', path: '/work/output/OUTON_H-ZGD0008_第02-09页成品.zip', source: 'snapshot', sizeBytes: 23068672, version: '1' },
  { id: 'prepare', name: 'prepare.cpython-312.pyc', path: '/work/outon_task/__pycache__/prepare.cpython-312.pyc', source: 'work', sizeBytes: 2662, version: '1' },
  { id: 'typeset', name: 'typeset.cpython-312.pyc', path: '/work/outon_task/__pycache__/typeset.cpython-312.pyc', source: 'work', sizeBytes: 4096, version: '1' },
  { id: 'page03', name: 'page03_refs4-5.png', path: '/work/outon_task/boards/page03_refs4-5.png', source: 'work', sizeBytes: 3565158, version: '1' },
  { id: 'page05', name: 'page05_refs5-6.png', path: '/work/outon_task/boards/page05_refs5-6.png', source: 'work', sizeBytes: 1572864, version: '1' },
  { id: 'page06', name: 'page06_refs5-6.png', path: '/work/outon_task/boards/page06_refs5-6.png', source: 'work', sizeBytes: 1887436, version: '1' },
  { id: 'main', name: '02_白底主图与配件.jpg', path: '/work/output/02_白底主图与配件.jpg', source: 'native', sizeBytes: 2097152, version: '1' },
  { id: 'scene', name: '03_窗边沙发场景主图.jpg', path: '/work/output/03_窗边沙发场景主图.jpg', source: 'native', sizeBytes: 3145728, version: '1' },
]

export const recoveryPreviewApi: ReturnType<typeof createStudioOutputsApi> = {
  list: async () => ({ items: files.map(file => ({ ...file })), busy: false }),
  recover: async (_taskId, _conversationId, selected) => ({
    saved: selected.map(file => ({ id: file.id, kind: 'file' as const })), errors: [],
  }),
}
