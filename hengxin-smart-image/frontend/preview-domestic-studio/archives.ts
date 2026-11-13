import { reactive } from 'vue'
import type { Asset, Conversation, Message } from './state'
import type { WorkspaceConfig } from './workspaces'

export const libraryPath = '/product-library'
export type ProductArchive = {
  id: number; productName: string; sourceTitle: string; sourcePath: string
  conversationName: string; createdAt: string; messages: Message[]; assets: Asset[]
}
export const archives = reactive<ProductArchive[]>([])

// Independent local copies keep archived attachments alive after a conversation is deleted.
export async function archiveConversation(config: WorkspaceConfig, conversation: Conversation, productName: string) {
  if (config.group !== 'new') throw new Error('只有新品生成工作台支持归档')
  if (conversation.running || !conversation.messages.some(message => message.role === 'assistant')) throw new Error('请等待本轮回复完成后归档')
  const name = productName.trim()
  if (!name || name.length > 60) throw new Error('请输入 1–60 个字的产品名称')
  const snapshot = conversation.messages.map(message => ({ ...message, files: message.files?.map(asset => ({ ...asset })) }))
  const originals = [...new Map(snapshot.flatMap(message => message.files || []).map(asset => [asset.id, asset])).values()]
  const copies: Asset[] = []
  try {
    for (const asset of originals) {
      const response = await fetch(asset.url)
      if (!response.ok) throw new Error(`无法复制附件：${asset.name}`)
      copies.push({ ...asset, url: URL.createObjectURL(await response.blob()) })
    }
    const item: ProductArchive = {
      id: Date.now() + Math.random(), productName: name, sourceTitle: config.title, sourcePath: config.path,
      conversationName: conversation.name, createdAt: new Date().toISOString(), assets: copies,
      messages: snapshot.map(message => ({ ...message, files: message.files?.map(asset => copies.find(copy => copy.id === asset.id)!) })),
    }
    archives.unshift(item)
    return item
  } catch (error) { copies.forEach(asset => URL.revokeObjectURL(asset.url)); throw error }
}
export function removeArchive(item: ProductArchive) {
  const index = archives.findIndex(archive => archive.id === item.id)
  if (index < 0) return
  archives[index].assets.forEach(asset => URL.revokeObjectURL(asset.url))
  archives.splice(index, 1)
}
export function archiveTime(value: string) { return new Date(value).toLocaleString('zh-CN', { hour12: false }) }
