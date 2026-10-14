import { test } from 'node:test'
import assert from 'node:assert/strict'
import { renderStudioMarkdown } from '../src/views/overseas/studio/studio-markdown'
import { mergeTranscript } from '../src/views/overseas/studio/studio-transcript'
import type { StudioPicture, StudioTranscript } from '../src/api/overseas/studio'
const picture: StudioPicture = { id:'p',name:'正式',url:'/api/overseas/v1/tasks/t/studio/pictures/p/content',sourcePath:'/workspace/output/final.png',width:800,height:800,turnId:'r',sku:null,archived:false }

test('完整长文保留Markdown段落、代码块、链接且禁用原始HTML',()=>{
  const long='完整长文'.repeat(20000)+'最后一句'
  const html=renderStudioMarkdown(`# 标题\n\n${long}\n\n\`\`\`html\n<script>alert(1)</script>\n\`\`\`\n\n[官网](https://example.com)\n\n<img src="https://evil.test/a" onerror="alert(1)">`)
  assert.ok(html.includes(long));assert.match(html,/<h1>标题<\/h1>/);assert.match(html,/<pre><code/);assert.match(html,/rel="noopener noreferrer"/);assert.doesNotMatch(html,/<script|<img/)
})
test('正文图片引用始终只输出完整文字，图片统一由正式卡片展示',()=>{
  const source=`![正式](${picture.sourcePath})\n![临时](/workspace/temp.png)\n![外网](https://evil.test/x.png)\n![数据](data:image/png;base64,AAAA)\n[下载](/workspace/temp.png)\n[危险](javascript:alert(1))`
  const html=renderStudioMarkdown(source);assert.doesNotMatch(html,/<img /);assert.ok(html.includes(picture.sourcePath!));assert.ok(html.includes('/workspace/temp.png'));assert.doesNotMatch(html,/src="https:|src="data:|href="javascript:|href="\/workspace/)
  assert.doesNotMatch(renderStudioMarkdown(`![正式](${picture.url})`),/<img /)
  assert.doesNotMatch(renderStudioMarkdown('![恶意](https://evil.test/x.png)'),/<img /)
})
test('本地图片、API、相对路径和自定义协议只作文字，正式图片操作由卡片提供',()=>{
  const html=renderStudioMarkdown(`[下载](${picture.sourcePath}) [原件](${picture.url}) [越权](/api/overseas/v1/materials/other/content) [相对](../x.png) [协议](file:///tmp/x)`)
  assert.equal((html.match(/<a /g)||[]).length,0);assert.ok(html.includes(picture.url));assert.ok(html.includes('../x.png'))
})
test('同一路径在过程说明和最终段落复用时，所有正文引用均不加载图片',()=>{
  for(const label of ['过程草稿','非交付段落','正式图片']) {
    const html=renderStudioMarkdown(`![${label}](${picture.sourcePath})`)
    assert.doesNotMatch(html,/<img /);assert.ok(html.includes(label));assert.ok(html.includes(picture.sourcePath!))
  }
})
test('同itemId跨轮次独立合并，旧重复不回退，失败快照保留完整文本',()=>{
  const entry=(id:number,turnId:string,text:string):StudioTranscript=>({id,turnId,itemId:'same',kind:'message',state:'running',text,createdAt:''})
  const first=mergeTranscript([],[entry(1,'a','开头'),entry(2,'b','其他轮次')])
  const merged=mergeTranscript(first,[{...entry(3,'a','完整且失败'),state:'failed'},entry(1,'a','旧内容')])
  assert.deepEqual(merged.map(e=>e.text),['完整且失败','其他轮次']);assert.equal(merged[0].state,'failed');assert.equal(first[0].text,'开头')
})
