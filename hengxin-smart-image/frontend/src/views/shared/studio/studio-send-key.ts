export function handleStudioSendKey(event: Event | KeyboardEvent, send: () => unknown) {
  // Leave IME confirmation and line breaks to the textarea, including IME's 229 boundary.
  if (!('key' in event) || event.key !== 'Enter' || event.isComposing || event.keyCode === 229 || event.shiftKey || event.altKey) return
  event.preventDefault()
  if (!event.repeat) void send()
}
