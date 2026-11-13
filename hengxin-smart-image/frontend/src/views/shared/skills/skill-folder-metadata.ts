import MarkdownIt from 'markdown-it'
import { parseDocument } from 'yaml'

const markdown = new MarkdownIt('commonmark')
const titleParts = new Set(['text', 'code_inline', 'image', 'softbreak', 'hardbreak'])
function oversizedMetadata(value: string) {
  // Python's len counts Unicode code points; stop early without allocating a large array.
  let count = 0
  for (const _character of value) if (++count > 65536) return true
  return false
}

/** Presentation only: the server validates the original bytes before installation. */
export function previewSkillMetadata(source: string, rootName: string) {
  // Match the installed package validator's frontmatter boundaries (including whitespace).
  const front = source.match(/^\uFEFF?---\s*\r?\n([\s\S]*?)\r?\n---(?:\s*\r?\n|$)/)
  if (!front || oversizedMetadata(front[1])) throw new Error('SKILL.md 缺少有效或长度合规的 name / description frontmatter')
  let name = '', description = '元数据待服务器校验后显示'
  try {
    // PyYAML safe_load uses YAML 1.1, accepts merge keys and keeps the last duplicate key.
    // No custom tags or constructors: package content can never execute code.
    const document = parseDocument(front[1], { version: '1.1', uniqueKeys: false, merge: true, logLevel: 'silent' })
    if (document.errors.length || document.warnings.length) throw new Error('Unsupported local metadata')
    const metadata: unknown = document.toJS({ mapAsMap: true, maxAliasCount: 100 })
    if (metadata instanceof Map && typeof metadata.get('name') === 'string' && typeof metadata.get('description') === 'string') {
      name = metadata.get('name').trim()
      description = metadata.get('description').trim()
    }
  } catch {
    // Parser differences or the local alias budget must not reject server-valid packages.
    // The pending preview is explicit; upload still sends untouched source for authoritative validation.
  }
  const tokens = markdown.parse(source.slice(front[0].length), {})
  let displayName = name || rootName
  for (let index = 0; index < tokens.length; index++) {
    if (tokens[index].type !== 'heading_open' || tokens[index].tag !== 'h1') continue
    const children = tokens[index + 1]?.children || []
    displayName = children.filter(child => titleParts.has(child.type))
      .map(child => child.type === 'softbreak' || child.type === 'hardbreak' ? ' ' : child.content)
      .join('').trim() || displayName
    break
  }
  return { name, description, displayName }
}
