export const MAX_UPLOAD_BYTES = 500_000_000
export const MAX_TURN_ATTACHMENTS = 100
export const MAX_TURN_REFERENCES = 100

export function turnLimitError(attachments: number, references: number): string {
  if (attachments > MAX_TURN_ATTACHMENTS) return '每条消息最多添加 100 个附件（含图需资料），请移除多余附件后再发送'
  if (references > MAX_TURN_REFERENCES) return '每条消息最多引用 100 张生成图片，请移除多余图片后再发送'
  return ''
}
