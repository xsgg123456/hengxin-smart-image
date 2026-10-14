import * as BeijingTime from '../src/utils/beijing-time'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as Vue from 'vue'
import * as Materials from '../src/api/overseas/materials'
import * as Data from '../src/views/overseas/material-reader-data'
import { IdentityError } from '../src/api/identity/request'
interface N {tag:string;children:N[];parent:N|null;props:Record<string,unknown>;text:string}
const n=(text='',tag=''):N=>({tag,text,children:[],parent:null,props:{}})
const renderer=Vue.createRenderer<N,N>({createElement:t=>n('',t),createText:n,createComment:n,insert(c,p){c.parent=p;p.children.push(c)},remove(c){if(c.parent)c.parent.children.splice(c.parent.children.indexOf(c),1)},parentNode:c=>c.parent,nextSibling:()=>null,patchProp:(e,k,_o,v)=>{e.props[k]=v},setText:(e,t)=>{e.text=t},setElementText:(e,t)=>{e.text=t}})
const flatten=(e:N):N[]=>[e,...e.children.flatMap(flatten)], text=(e:N):string=>e.text+e.children.map(text).join('')
const flush=async()=>{for(let i=0;i<15;i++){await Promise.resolve();await Vue.nextTick()}}
const stub=(name:string)=>Vue.defineComponent({inheritAttrs:false,setup(_, {attrs,slots}){return()=>Vue.h(name,attrs,Object.values(slots).flatMap(s=>s?.()||[]))}})
function mount(name:string,props:Record<string,unknown>){
 const descriptor=parse(readFileSync(new URL(`../src/views/overseas/${name}.vue`,import.meta.url),'utf8')).descriptor
 const code=ts.transpileModule(compileScript(descriptor,{id:'reader-test',inlineTemplate:true}).content,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
 const module={exports:{} as {default:Vue.Component}}
 const require=(p:string):unknown=>{if(p==='vue')return Vue;if(p==='@/utils/beijing-time')return BeijingTime;if(p.endsWith('/materials'))return Materials;if(p.endsWith('/request'))return {IdentityError};if(p==='./material-reader-data')return Data;if(p.endsWith('.vue'))return {default:stub(p),__esModule:true};throw Error(p)}
 new Function('require','module','exports',code)(require,module,module.exports)
 const app=renderer.createApp(module.exports.default,props)
 for(const s of ['ElCard','ElEmpty','ElTabs','ElTabPane','ElButton','ElSelect','ElOption','ElRadioGroup','ElRadioButton','ElAlert','ElDialog'])app.component(s,stub(s))
 const root=n();app.mount(root)
 return {app,root,find:(tag:string)=>flatten(root).find(e=>e.tag===tag)!,click:async(label:string)=>{const b=flatten(root).find(e=>e.tag==='ElButton'&&text(e)===label);assert.ok(b,label);assert.ok(!b.props.disabled);(b.props.onClick as ()=>void)();await flush()}}
}
const version={version:1,status:'ready' as const,parserVersion:'test',text:'<script>evil()</script>\n完整资料',error:null,createdAt:'2026-10-13'}
const file:Materials.Material={...version,id:'m',kind:'requirement',name:'需求.docx',sizeBytes:30,contentType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',taskId:'t',versions:[version]}
test('资料分页不截断Unicode，工作表/空单元格/公式保留纯文本',()=>{
 const source='图需😀'.repeat(8001);assert.equal(Data.materialTextPages(source).join(''),source);assert.ok(Data.materialTextPages('').length)
 assert.deepEqual(Data.materialSheets('[A] 品名\t\t=1+1\n[B] <img onerror=x>\t值'),[{name:'A',rows:[['品名','','=1+1']]},{name:'B',rows:[['<img onerror=x>','值']]}])
})
test('实际阅读SFC：表格完整翻页，Word安全文字且可翻到尾页',async()=>{
 const table=mount('MaterialTextReader',{name:'竞品.xlsx',text:Array.from({length:101},(_,i)=>`[Sheet] 商品${i}\t数据${i}`).join('\n')})
 assert.ok(text(table.root).includes('商品49'));assert.ok(!text(table.root).includes('商品50'));await table.click('下一页');assert.ok(text(table.root).includes('商品99'));await table.click('下一页');assert.ok(text(table.root).includes('商品100'));table.app.unmount()
 const word=mount('MaterialTextReader',{name:'需求.docx',text:'<script>evil()</script>'+'字'.repeat(8000)+'尾页'})
 assert.equal(flatten(word.root).filter(e=>e.tag==='script').length,0);assert.ok(text(word.root).includes('<script>evil()</script>'));await word.click('下一页');assert.ok(text(word.root).includes('尾页'));word.app.unmount()
})
test('实际资料SFC：下载权限拒绝回传，卸载后迟到响应不创建URL',async()=>{
 let failure=0,resolve!:(b:Blob)=>void,signal:AbortSignal|undefined,created=0
 const oldCreate=URL.createObjectURL;URL.createObjectURL=()=>{created++;return 'blob:test'}
 try{
 const denied=mount('OverseasMaterialReader',{files:[file],api:{content:async()=>{throw new IdentityError(403,'暂无权限')}},onFailure:()=>failure++});await denied.click('下载原文件');assert.equal(failure,1);denied.app.unmount()
 const pending=mount('OverseasMaterialReader',{files:[file],api:{content:(_id:string,_d:boolean,s:AbortSignal)=>{signal=s;return new Promise<Blob>(r=>resolve=r)}}});await pending.click('下载原文件');pending.app.unmount();assert.ok(signal?.aborted);resolve(new Blob(['test']));await flush();assert.equal(created,0)
 }finally{URL.createObjectURL=oldCreate}
})
