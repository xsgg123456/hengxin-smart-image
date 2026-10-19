export function handleSendKey(event: KeyboardEvent, send: () => void) {
  // IME 确认选字的回车交给输入法；229 兼容组合输入结束边界。
  if (event.key !== 'Enter' || event.isComposing || event.keyCode === 229 || event.shiftKey || event.altKey) return
  event.preventDefault()
  if (!event.repeat) send()
}
