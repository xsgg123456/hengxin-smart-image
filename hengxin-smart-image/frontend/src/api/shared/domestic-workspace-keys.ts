export const newProductKeys = ['camera', 'case', 'film', 'cable', 'earbud', 'accessory'] as const
export const replacementKeys = ['product', 'scene', 'phone', 'edit'] as const
export const workspaceKeys = [...newProductKeys, ...replacementKeys] as const
export type WorkspaceKey = typeof workspaceKeys[number]
export type NewProductKey = typeof newProductKeys[number]

export const isWorkspaceKey = (value: unknown): value is WorkspaceKey => workspaceKeys.some(key => key === value)
export const isNewProductKey = (value: unknown): value is NewProductKey => newProductKeys.some(key => key === value)
