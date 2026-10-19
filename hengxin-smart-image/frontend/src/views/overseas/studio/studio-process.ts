import type { StudioTranscript, StudioTurn } from '@/api/overseas/studio'

export function splitStudioReply(turn: Pick<StudioTurn, 'status' | 'reply'>, entries: StudioTranscript[]) {
  if (turn.status !== 'succeeded') {
    return { entries, reply: entries.some(entry => entry.kind === 'message' && entry.text === turn.reply) ? '' : turn.reply || '' }
  }
  // reply is the authoritative final output. Older rows can have only public messages.
  const messages = entries.filter(entry => entry.kind === 'message')
  const reply = turn.reply || messages.at(-1)?.text || ''
  const final = messages.findLast(entry => entry.text === reply)
  return { entries: entries.filter(entry => entry !== final), reply }
}
