import MarkdownIt from 'markdown-it'

const markdown = new MarkdownIt({ html: false, linkify: false, breaks: true })
const escape = (text: string) => markdown.utils.escapeHtml(text)
const externalUrl = (href: string) => /^https?:\/\//i.test(href) && !/[\u0000-\u0020\\]/.test(href)
markdown.renderer.rules.image = (tokens, index) => {
  const token = tokens[index], source = String(token.attrGet('src') || '')
  // Only the formal Picture cards render images. A reused path cannot upgrade an old message.
  return `<span class="studio-image-reference">${escape(`![${token.content}](${source})`)}</span>`
}
markdown.renderer.rules.link_open = (tokens, index) => {
  const href = String(tokens[index].attrGet('href') || '')
  return externalUrl(href) ? `<a href="${escape(href)}" target="_blank" rel="noopener noreferrer">` : '<span>'
}
markdown.renderer.rules.link_close = (tokens, index) => {
  let depth = 0
  for (let i = index - 1; i >= 0; i--) {
    if (tokens[i].type === 'link_close') depth++
    if (tokens[i].type === 'link_open') {
      if (depth-- > 0) continue
      const href = String(tokens[i].attrGet('href') || '')
      return externalUrl(href) ? '</a>' : ` (${escape(href)})</span>`
    }
  }
  return '</span>'
}
export function renderStudioMarkdown(text: string) { return markdown.render(text) }
