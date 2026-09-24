import { onBeforeUnmount, onMounted, ref } from 'vue'

export function useAnnotationShortcuts(
  disabled: () => boolean,
  cancel: () => void,
) {
  const space = ref(false)
  const cancelGesture = () => {
    space.value = false
    cancel()
  }
  function key(event: KeyboardEvent) {
    if (event.code !== 'Space') return
    if (event.type === 'keyup') {
      space.value = false
      return
    }
    const target = event.target instanceof Element ? event.target : null
    if (
      disabled() ||
      target?.closest(
        'input,textarea,select,button,[role="button"],[contenteditable="true"],[role="textbox"]',
      )
    )
      return
    space.value = true
    event.preventDefault()
  }
  const visibility = () => {
    if (document.hidden) cancelGesture()
  }
  onMounted(() => {
    window.addEventListener('blur', cancelGesture)
    window.addEventListener('resize', cancelGesture)
    window.addEventListener('keydown', key)
    window.addEventListener('keyup', key)
    document.addEventListener('visibilitychange', visibility)
  })
  onBeforeUnmount(() => {
    cancelGesture()
    window.removeEventListener('blur', cancelGesture)
    window.removeEventListener('resize', cancelGesture)
    window.removeEventListener('keydown', key)
    window.removeEventListener('keyup', key)
    document.removeEventListener('visibilitychange', visibility)
  })
  return { space, cancelGesture }
}
